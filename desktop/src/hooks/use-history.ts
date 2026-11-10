/**
 * History page hooks.
 *
 * The History screen lists every render the user has produced. Its behaviour
 * lives in two focused hooks so the page component only handles the table
 * and the dialogs:
 *
 *   - useHistoryEntries   loading, deleting and clearing the list
 *   - useHistoryPlayback  inline preview playback and waveform peaks
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { exportAudio } from "@/lib/export-audio";
import { mockHistory, demoList } from "@/lib/mock";
import type { HistoryEntry } from "@/lib/types";

/* -------------------------------------------------------------------------- */
/* Entries                                                                     */
/* -------------------------------------------------------------------------- */

export interface HistoryEntries {
  entries: HistoryEntry[];
  loading: boolean;
  pendingDelete: HistoryEntry | null;
  setPendingDelete: (entry: HistoryEntry | null) => void;
  confirmClear: boolean;
  setConfirmClear: (value: boolean) => void;
  remove: () => Promise<void>;
  clearAll: () => Promise<void>;
}

/**
 * Loads the render history and owns the delete / clear actions.
 *
 * `onCleared` is invoked after the history has actually been emptied, so the
 * caller can drop any selection state it holds for the removed rows.
 */
export function useHistoryEntries(
  online: boolean,
  active = true,
  onCleared?: () => void,
): HistoryEntries {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<HistoryEntry | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    async function load() {
      if (!online) {
        if (!cancelled) {
          setEntries(demoList(mockHistory));
          setLoading(false);
        }
        return;
      }
      try {
        const next = await api.listHistory();
        if (!cancelled) setEntries(next);
      } catch {
        if (!cancelled) setEntries(demoList(mockHistory));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [online, active]);

  const remove = useCallback(async () => {
    const entry = pendingDelete;
    setPendingDelete(null);
    if (!entry) return;
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
  }, [online, pendingDelete]);

  const clearAll = useCallback(async () => {
    setConfirmClear(false);
    if (!online) {
      setEntries([]);
      onCleared?.();
      return;
    }
    try {
      const result = await api.clearHistory();
      setEntries([]);
      onCleared?.();
      toast.success(`Cleared ${result.deleted} entries`);
    } catch (error) {
      toast.error("Could not clear history", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [online, onCleared]);

  return {
    entries,
    loading,
    pendingDelete,
    setPendingDelete,
    confirmClear,
    setConfirmClear,
    remove,
    clearAll,
  };
}

/* -------------------------------------------------------------------------- */
/* Playback                                                                    */
/* -------------------------------------------------------------------------- */

export interface HistoryPlayback {
  playingId: number | null;
  progress: Record<number, number>;
  peaksById: Record<number, number[]>;
  preview: (entry: HistoryEntry) => void;
  ensurePeaks: (entryId: number) => void;
  exportEntry: (entry: HistoryEntry) => Promise<void>;
  audioRef: RefObject<HTMLAudioElement | null>;
}

/**
 * Inline preview playback plus the lazily loaded waveform peaks.
 */
export function useHistoryPlayback(online: boolean): HistoryPlayback {
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [progress, setProgress] = useState<Record<number, number>>({});
  const [peaksById, setPeaksById] = useState<Record<number, number[]>>({});

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(
    () => () => {
      audioRef.current?.pause();
    },
    [],
  );

  const preview = useCallback(
    (entry: HistoryEntry) => {
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
      audio.ontimeupdate = () => {
        const duration = audio.duration || entry.duration_seconds || 1;
        setProgress((previous) => ({
          ...previous,
          [entry.id]: audio.currentTime / duration,
        }));
      };
      audio.onended = () => {
        setPlayingId(null);
        setProgress((previous) => ({ ...previous, [entry.id]: 0 }));
      };
      audio.onerror = () => {
        setPlayingId(null);
        toast.error("The rendered file is missing");
      };
      audioRef.current = audio;
      void audio
        .play()
        .then(() => setPlayingId(entry.id))
        .catch(() => toast.error("Playback failed"));
    },
    [online, playingId],
  );

  /** Loads the waveform of a take the first time its row becomes visible. */
  const requestedPeaks = useRef<Set<number>>(new Set());
  const ensurePeaks = useCallback(
    (entryId: number) => {
      if (peaksById[entryId] || !online || requestedPeaks.current.has(entryId)) return;
      requestedPeaks.current.add(entryId);
      void api
        .getHistoryPeaks(entryId)
        .then((result) => {
          setPeaksById((previous) => ({
            ...previous,
            [entryId]: result.peaks ?? [],
          }));
        })
        .catch(() => {
          /* a take without a waveform still renders a placeholder strip */
        });
    },
    [online, peaksById],
  );

  const exportEntry = useCallback(async (entry: HistoryEntry) => {
    exportAudio(api.audioUrl(`/api/history/${entry.id}/audio`), entry.voice_name || "voiceclone");
  }, []);

  return { playingId, progress, peaksById, preview, ensurePeaks, exportEntry, audioRef };
}