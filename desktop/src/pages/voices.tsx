import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  CircleAlert,
  FileAudio,
  Mic,
  Mic2,
  Pause,
  Play,
  Plus,
  Search,
  Square,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Meter } from "@/components/ui/meter";
import { PageHeader, StatChip } from "@/components/ui/page-header";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useApp, useAppActions } from "@/lib/app-context";
import { pickAudioFile } from "@/lib/desktop";
import { MAX_RECORD_SECONDS, useRecorder } from "@/hooks/use-recorder";
import { useEngineStatus } from "@/lib/engine-status";
import { formatDuration } from "@/lib/format";
import { mockEngines, mockVoices, demoList } from "@/lib/mock";
import type { EngineInfo, VoiceProfile } from "@/lib/types";

type ConsentFilter = "all" | "confirmed" | "missing";

const EMPTY_FORM = { name: "", language: "en", referencePath: "", notes: "" };

export function VoicesPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";
  const { intent, consumeIntent } = useApp();

  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>(demoList(mockEngines));
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [consentFilter, setConsentFilter] = useState<ConsentFilter>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [consent, setConsent] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<VoiceProfile | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const languages = useMemo(() => {
    const available = engines.find((e) => e.is_available) ?? engines[0];
    return available?.supported_languages ?? ["en"];
  }, [engines]);

  const load = useCallback(async () => {
    if (!online) {
      setVoices(demoList(mockVoices));
      setEngines(demoList(mockEngines));
      setLoading(false);
      return;
    }
    try {
      const [nextVoices, nextEngines] = await Promise.all([api.listVoices(), api.listEngines()]);
      setVoices(nextVoices);
      setEngines(nextEngines.length > 0 ? nextEngines : demoList(mockEngines));
    } catch {
      setVoices(demoList(mockVoices));
      setEngines(demoList(mockEngines));
    } finally {
      setLoading(false);
    }
  }, [online]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => () => { audioRef.current?.pause(); }, []);

  useEffect(() => {
    if (intent !== "new-voice") return;
    consumeIntent();
    setDialogOpen(true);
  }, [intent, consumeIntent]);

  useAppActions({ createVoice: () => setDialogOpen(true) });

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return voices.filter((v) => {
      if (consentFilter === "confirmed" && !v.consent_confirmed) return false;
      if (consentFilter === "missing" && v.consent_confirmed) return false;
      if (!term) return true;
      return v.name.toLowerCase().includes(term) || v.language.toLowerCase().includes(term) || v.notes.toLowerCase().includes(term);
    });
  }, [consentFilter, query, voices]);

  const confirmedCount = voices.filter(v => v.consent_confirmed).length;
  const totalClips = voices.reduce((s, v) => s + v.clips.length, 0);

  const preview = (voice: VoiceProfile) => {
    if (!online) {
      toast.error("Auditioning needs the Python engine", { description: "Start the sidecar to play reference clips." });
      return;
    }
    if (playingId === voice.id) { audioRef.current?.pause(); setPlayingId(null); return; }
    audioRef.current?.pause();
    const audio = new Audio(api.clipUrl(voice.id));
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => { setPlayingId(null); toast.error("Could not load the reference clip"); };
    audioRef.current = audio;
    void audio.play().then(() => setPlayingId(voice.id)).catch(() => toast.error("Playback failed"));
  };

  const remove = async () => {
    const voice = pendingDelete;
    setPendingDelete(null);
    if (!voice) return;
    if (!online) { setVoices(p => p.filter(i => i.id !== voice.id)); toast.message("Removed from demo list"); return; }
    try {
      await api.deleteVoice(voice.id);
      setVoices(p => p.filter(i => i.id !== voice.id));
      toast.success(`Deleted ${voice.name}`);
    } catch (e) {
      toast.error("Delete failed", { description: e instanceof Error ? e.message : String(e) });
    }
  };

  const recorder = useRecorder(async (wav, duration) => {
    try {
      const path = await api.uploadReference(wav);
      setForm(p => ({ ...p, referencePath: path }));
      toast.success(`Recorded ${duration.toFixed(0)}s`, duration < 5 ? { description: "Under 5 seconds may clone poorly. Try a longer take." } : undefined);
    } catch (e) {
      toast.error("Could not save the recording", { description: e instanceof Error ? e.message : String(e) });
    }
  });

  const toggleRecording = async () => {
    if (recorder.recording) { recorder.stop(); return; }
    if (!online) { toast.error("Recording needs the Python engine running"); return; }
    try { await recorder.start(); } catch (e) {
      toast.error("Microphone unavailable", { description: e instanceof Error ? e.message : "Allow microphone access and try again." });
    }
  };

  const chooseReference = async () => {
    const path = await pickAudioFile();
    if (!path) return;
    setForm(p => ({ ...p, referencePath: path }));
  };

  const create = async () => {
    if (!form.name.trim()) { toast.error("Give the voice a name"); return; }
    if (!consent) { toast.error("Consent confirmation is required"); return; }
    if (!form.referencePath.trim()) { toast.error("Add a reference recording", { description: "5–30 seconds of clean speech." }); return; }
    if (!online) { toast.error("Creating a profile needs the Python engine running"); return; }
    setBusy(true);
    try {
      const created = await api.createVoice({ name: form.name.trim(), language: form.language, notes: form.notes.trim(), reference_path: form.referencePath.trim(), consent_confirmed: consent });
      setVoices(p => [...p, created]);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setConsent(false);
      toast.success(`Created ${created.name}`);
    } catch (e) {
      toast.error("Could not create the voice", { description: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(false); }
  };

  return (
    <div className="flex min-h-screen flex-col gap-6">
      <PageHeader
        title="Voices"
        description="Reference voices, their quality and cloning permissions. Everything stays on this machine."
        icon={Mic2}
        meta={
          <>
            <StatChip icon={Mic2}>{voices.length} profiles</StatChip>
            <StatChip icon={FileAudio}>{totalClips} samples</StatChip>
            <StatChip icon={ShieldCheck} tone={confirmedCount === voices.length && voices.length > 0 ? "success" : "warning"}>
              {confirmedCount}/{voices.length} consented
            </StatChip>
          </>
        }
        actions={<Button onClick={() => setDialogOpen(true)}><Plus className="mr-1.5 size-4" />New voice</Button>}
      />

      <div className="flex w-full flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="relative w-full sm:flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by name, language or notes…" className="pl-9 h-10 w-full" />
        </div>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-1 w-full sm:w-auto rounded-md border bg-surface-raised p-1">
          {[
            { id: "all", label: "All" },
            { id: "confirmed", label: "Consented" },
            { id: "missing", label: "Missing" },
          ].map(opt => (
            <button key={opt.id} onClick={() => setConsentFilter(opt.id as ConsentFilter)} className={`rounded-md px-3 py-1.5 text-sm font-medium transition w-full sm:w-auto ${consentFilter === opt.id ? "bg-surface-inset text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-52 rounded-md" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Empty className="border border-dashed rounded-md bg-surface-inset/60 py-16">
          <EmptyHeader>
            <EmptyMedia variant="icon"><Mic2 /></EmptyMedia>
            <EmptyTitle>{voices.length === 0 ? "No voice profiles yet" : "No voices match"}</EmptyTitle>
            <EmptyDescription>{voices.length === 0 ? "Create a profile with 5–30 seconds of clean reference speech." : "Try a different search or filter."}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            {voices.length === 0 ? <Button onClick={() => setDialogOpen(true)}><Plus className="mr-1.5 size-4" />Create your first voice</Button> : <Button variant="outline" onClick={() => setConsentFilter("all")}>Show all</Button>}
          </EmptyContent>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map(voice => {
            const quality = voice.clips[0]?.quality_score ?? 0;
            const totalSeconds = voice.clips.reduce((s, c) => s + c.duration_seconds, 0);
            return (
              <Card key={voice.id} className="group relative overflow-hidden shadow-[var(--shadow-soft)] transition hover:shadow-[var(--shadow-lifted)]">
                <CardHeader className="pb-3">
                  <div className="flex items-start gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-surface-accent text-primary">
                      <Mic2 className="size-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <CardTitle className="truncate text-[15px]">{voice.name}</CardTitle>
                      <p className="line-clamp-2 mt-0.5 text-xs text-muted-foreground">{voice.notes || "No notes"}</p>
                    </div>
                    <Tooltip>
                      <TooltipTrigger>
                        {voice.consent_confirmed ? (
                          <Badge variant="outline" className="border-status-success/30 text-status-success"><CheckCircle2 className="mr-1 size-3" />Consent</Badge>
                        ) : (
                          <Badge variant="outline" className="border-status-warning/40 text-status-warning"><CircleAlert className="mr-1 size-3" />No consent</Badge>
                        )}
                      </TooltipTrigger>
                      <TooltipContent>{voice.consent_confirmed ? "Consent confirmed" : "Consent missing"}</TooltipContent>
                    </Tooltip>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">{voice.language.toUpperCase()}</Badge>
                    <Badge variant="outline">{voice.clips.length} sample{voice.clips.length !== 1 ? "s" : ""}</Badge>
                    {totalSeconds > 0 && <Badge variant="outline">{formatDuration(totalSeconds)}</Badge>}
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                      <span>Reference quality</span>
                      <span className="font-mono">{quality}/100</span>
                    </div>
                    <Meter value={quality} label={`${voice.name} quality`} />
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <Button variant="outline" size="sm" className="flex-1" onClick={() => preview(voice)}>
                      {playingId === voice.id ? <Pause className="mr-1.5 size-4" /> : <Play className="mr-1.5 size-4" />}
                      {playingId === voice.id ? "Stop" : "Audition"}
                    </Button>
                    <Button variant="ghost" size="icon" aria-label="Delete" onClick={() => setPendingDelete(voice)}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={open => { setDialogOpen(open); if (!open) { setForm(EMPTY_FORM); setConsent(false); } }}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-serif text-2xl">New voice profile</DialogTitle>
            <DialogDescription>Pick a clean reference recording. Quality is checked locally.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <Field>
              <FieldLabel>Voice name</FieldLabel>
              <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Elena Storyteller" />
            </Field>
            <Field>
              <FieldLabel>Language</FieldLabel>
              <Select value={form.language} onValueChange={v => v && setForm(p => ({ ...p, language: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{languages.map(l => <SelectItem key={l} value={l}>{l.toUpperCase()}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>Reference recording</FieldLabel>
              <button type="button" onClick={chooseReference} className="flex w-full items-center justify-between rounded-md border border-dashed p-4 hover:border-primary/50 transition">
                <div className="flex items-center gap-3">
                  <div className="flex size-9 items-center justify-center rounded-md bg-surface-raised text-primary"><FileAudio className="size-4" /></div>
                  <div className="text-left">
                    <div className="text-sm font-medium">{form.referencePath ? form.referencePath.split("/").pop() : "Choose file"}</div>
                    <div className="text-xs text-muted-foreground">WAV, FLAC, OGG, MP3 · 5–30s</div>
                  </div>
                </div>
                <Plus className="size-4 text-muted-foreground" />
              </button>
              <Button type="button" variant={recorder.recording ? "default" : "outline"} onClick={toggleRecording} className="mt-2 w-full">
                {recorder.recording ? <><Square className="fill-current" />Stop · {recorder.seconds.toFixed(0)}s / {MAX_RECORD_SECONDS}s</> : <><Mic />Record with microphone</>}
              </Button>
            </Field>
            <Field>
              <FieldLabel>Notes</FieldLabel>
              <Textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Warm tone, treated room…" className="min-h-20" />
            </Field>
            <label className="flex items-start gap-2.5 text-sm">
              <Checkbox checked={consent} onCheckedChange={checked => setConsent(checked === true)} className="mt-0.5" />
              <span>I own this voice or have the speaker's permission to clone it.</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={create} disabled={busy}>{busy ? "Creating…" : "Create profile"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!pendingDelete} onOpenChange={o => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{pendingDelete?.name}”?</AlertDialogTitle>
            <AlertDialogDescription>Profile and reference clips will be removed permanently.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
