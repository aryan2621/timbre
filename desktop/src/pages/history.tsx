import { useEffect, useMemo, useRef, useState } from "react";
import { History, Pause, Play, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { mockHistory } from "@/lib/mock";
import type { HistoryEntry } from "@/lib/types";

interface HistoryPageProps {
  online: boolean | null;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function HistoryPage({ online }: HistoryPageProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [query, setQuery] = useState("");
  const [playingId, setPlayingId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = async (term = query) => {
    if (!online) {
      setEntries(mockHistory);
      return;
    }
    try {
      setEntries(await api.listHistory(term));
    } catch {
      setEntries(mockHistory);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  useEffect(
    () => () => {
      audioRef.current?.pause();
    },
    [],
  );

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return entries;
    return entries.filter(
      (entry) =>
        entry.prompt_text.toLowerCase().includes(term) ||
        entry.voice_name.toLowerCase().includes(term) ||
        entry.engine_name.toLowerCase().includes(term),
    );
  }, [entries, query]);

  const preview = (entry: HistoryEntry) => {
    if (!online) {
      toast.error("Playback needs the Python engine");
      return;
    }
    if (playingId === entry.id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    audioRef.current?.pause();
    const audio = new Audio(api.audioUrl(`/api/history/${entry.id}/audio`));
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => {
      setPlayingId(null);
      toast.error("The rendered file is missing");
    };
    audioRef.current = audio;
    void audio
      .play()
      .then(() => setPlayingId(entry.id))
      .catch(() => toast.error("Playback failed"));
  };

  const remove = async (entry: HistoryEntry) => {
    if (!window.confirm("Delete this history entry and its audio file?")) return;
    if (!online) {
      setEntries((previous) => previous.filter((item) => item.id !== entry.id));
      return;
    }
    try {
      await api.deleteHistory(entry.id);
      setEntries((previous) => previous.filter((item) => item.id !== entry.id));
      toast.success("History entry deleted");
    } catch (error) {
      toast.error("Delete failed", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const clearAll = async () => {
    if (!window.confirm("Delete every history entry and rendered audio file?")) {
      return;
    }
    if (!online) {
      setEntries([]);
      return;
    }
    try {
      const result = await api.clearHistory();
      setEntries([]);
      toast.success(`Cleared ${result.deleted} entries`);
    } catch (error) {
      toast.error("Could not clear history", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-[28px] font-medium tracking-tight">History</h1>
          <p className="text-sm text-muted-foreground">
            Every render, its parameters and the seed used.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search prompts or voices"
              className="w-60 pl-8"
            />
          </div>
          <Button variant="outline" onClick={() => void load(query)}>
            Search
          </Button>
          <Button variant="destructive" onClick={() => void clearAll()}>
            <Trash2 />
            Clear all
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Created</TableHead>
                <TableHead>Speaker Voice</TableHead>
                <TableHead>Voice Model</TableHead>
                <TableHead className="max-w-[420px]">Spoken Script</TableHead>
                <TableHead>Audio Length</TableHead>
                <TableHead>Take Seed</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDate(entry.created_at)}
                  </TableCell>
                  <TableCell className="font-medium">{entry.voice_name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{entry.engine_name}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[420px] truncate text-muted-foreground">
                    {entry.prompt_text}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {entry.duration_seconds.toFixed(2)}s
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {entry.seed}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => preview(entry)}
                      >
                        {playingId === entry.id ? <Pause /> : <Play />}
                        Play
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => void remove(entry)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!filtered.length && (
                <TableRow>
                  <TableCell colSpan={7} className="py-14 text-center">
                    <History className="mx-auto mb-3 size-8 text-muted-foreground/50" />
                    <p className="font-serif text-lg font-medium text-foreground">No generations yet</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Renders from the Studio appear here automatically.
                    </p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
