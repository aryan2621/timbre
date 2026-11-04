import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Mic2, Pause, Play, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { mockEngines, mockVoices } from "@/lib/mock";
import type { EngineInfo, VoiceProfile } from "@/lib/types";

interface VoicesPageProps {
  online: boolean | null;
}

function qualityTone(score: number) {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function VoicesPage({ online }: VoicesPageProps) {
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [form, setForm] = useState({
    name: "",
    language: "en",
    referencePath: "",
    notes: "",
  });
  const [consent, setConsent] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const languages = useMemo(() => {
    const available = engines.find((engine) => engine.is_available) ?? engines[0];
    return available?.supported_languages ?? ["en"];
  }, [engines]);

  const load = async () => {
    if (!online) {
      setVoices(mockVoices);
      setEngines(mockEngines);
      return;
    }
    try {
      const [nextVoices, nextEngines] = await Promise.all([
        api.listVoices(),
        api.listEngines(),
      ]);
      setVoices(nextVoices);
      setEngines(nextEngines.length > 0 ? nextEngines : mockEngines);
    } catch {
      setVoices(mockVoices);
      setEngines(mockEngines);
    }
  };

  useEffect(() => {
    void load();
  }, [online]);

  useEffect(
    () => () => {
      audioRef.current?.pause();
    },
    [],
  );

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return voices;
    return voices.filter(
      (voice) =>
        voice.name.toLowerCase().includes(term) ||
        voice.language.toLowerCase().includes(term) ||
        voice.notes.toLowerCase().includes(term),
    );
  }, [query, voices]);

  const preview = (voice: VoiceProfile) => {
    if (!online) {
      toast.error("Preview needs the Python engine", {
        description: "Start the sidecar to audition reference clips.",
      });
      return;
    }
    if (playingId === voice.id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    audioRef.current?.pause();
    const audio = new Audio(api.clipUrl(voice.id));
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => {
      setPlayingId(null);
      toast.error("Could not load the reference clip");
    };
    audioRef.current = audio;
    void audio
      .play()
      .then(() => setPlayingId(voice.id))
      .catch(() => toast.error("Playback failed"));
  };

  const remove = async (voice: VoiceProfile) => {
    if (!window.confirm(`Delete "${voice.name}" and its stored reference clips?`)) {
      return;
    }
    if (!online) {
      setVoices((previous) => previous.filter((item) => item.id !== voice.id));
      toast.message("Removed from the demo list");
      return;
    }
    try {
      await api.deleteVoice(voice.id);
      setVoices((previous) => previous.filter((item) => item.id !== voice.id));
      toast.success(`Deleted ${voice.name}`);
    } catch (error) {
      toast.error("Delete failed", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const create = async () => {
    if (!form.name.trim()) {
      toast.error("Give the voice a name");
      return;
    }
    if (!consent) {
      toast.error("Consent confirmation is required");
      return;
    }
    if (!form.referencePath.trim()) {
      toast.error("Add a reference recording", {
        description: "5–30 seconds of clean speech in WAV, FLAC, OGG or MP3.",
      });
      return;
    }
    if (!online) {
      toast.error("Creating a profile needs the Python engine running");
      return;
    }
    setBusy(true);
    try {
      const created = await api.createVoice({
        name: form.name.trim(),
        language: form.language,
        notes: form.notes.trim(),
        reference_path: form.referencePath.trim(),
      });
      setVoices((previous) => [...previous, created]);
      setOpen(false);
      setForm({ name: "", language: "en", referencePath: "", notes: "" });
      setConsent(false);
      toast.success(`Created ${created.name}`);
    } catch (error) {
      toast.error("Could not create the voice", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Voice Library</h1>
          <p className="text-sm text-muted-foreground">
            Speaker profiles, reference voice samples and cloning permissions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search voice library"
              className="w-56 pl-8"
            />
          </div>
          <Button onClick={() => setOpen(true)}>
            <Plus />
            New voice
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12" />
                <TableHead>Speaker Name</TableHead>
                <TableHead>Language</TableHead>
                <TableHead>Audio Samples</TableHead>
                <TableHead>Cloning Quality</TableHead>
                <TableHead>Permission</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((voice) => {
                const quality = voice.clips[0]?.quality_score ?? 0;
                return (
                  <TableRow key={voice.id}>
                    <TableCell>
                      <div className="flex size-8 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
                        <Mic2 className="size-4" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{voice.name}</div>
                      <div className="max-w-[360px] truncate text-xs text-muted-foreground">
                        {voice.notes || "No notes"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{voice.language.toUpperCase()}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {voice.clips.length}
                    </TableCell>
                    <TableCell>
                      <span className={`font-mono text-sm ${qualityTone(quality)}`}>
                        {quality}/100
                      </span>
                    </TableCell>
                    <TableCell>
                      {voice.consent_confirmed ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="size-3.5" />
                          Confirmed
                        </span>
                      ) : (
                        <span className="text-xs text-red-600 dark:text-red-400">Missing</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => preview(voice)}
                        >
                          {playingId === voice.id ? <Pause /> : <Play />}
                          Preview
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => void remove(voice)}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
              {!filtered.length && (
                <TableRow>
                  <TableCell colSpan={7} className="py-14 text-center">
                    <Mic2 className="mx-auto mb-3 size-8 text-muted-foreground/50" />
                    <p className="text-sm font-medium">No voices match this search</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Create a profile with 5–30 seconds of clean reference audio.
                    </p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Add New Voice Profile</DialogTitle>
            <DialogDescription>
              Import a clean audio recording (3 to 10 seconds). The engine checks audio quality and saves it to your local voice library.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="voice-name">Voice nickname or speaker name</Label>
              <Input
                id="voice-name"
                value={form.name}
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, name: event.target.value }))
                }
                placeholder="e.g. Elena Storyteller"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Primary language</Label>
                <Select
                  value={form.language}
                  onValueChange={(value: string | null) =>
                    value &&
                    setForm((previous) => ({ ...previous, language: value }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue>
                      {(value) => String(value ?? "en").toUpperCase()}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {languages.map((language) => (
                      <SelectItem key={language} value={language}>
                        {language.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="voice-ref">Sample voice recording (Audio file)</Label>
                <Input
                  id="voice-ref"
                  value={form.referencePath}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      referencePath: event.target.value,
                    }))
                  }
                  placeholder="/Users/me/voice_sample.wav"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="voice-notes">Voice character &amp; notes (optional)</Label>
              <Textarea
                id="voice-notes"
                value={form.notes}
                onChange={(event) =>
                  setForm((previous) => ({ ...previous, notes: event.target.value }))
                }
                placeholder="e.g. Warm documentary tone, calm pace, treated room"
              />
            </div>

            <label className="flex items-start gap-3 rounded-lg border p-3 text-sm">
              <Checkbox
                checked={consent}
                onCheckedChange={(checked) => setConsent(checked === true)}
                className="mt-0.5"
              />
              <span className="text-muted-foreground">
                I own this voice or have the speaker's explicit permission to
                clone it. This consent will be timestamped in the local database.
              </span>
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void create()} disabled={busy}>
              {busy ? "Creating" : "Create profile"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
