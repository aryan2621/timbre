import { useEffect, useRef, useState } from "react";
import { FileUp, Layers, Play, Square, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
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
import { api } from "@/lib/api";
import { mockEngines } from "@/lib/mock";
import type { EngineInfo } from "@/lib/types";

interface BatchPageProps {
  online: boolean | null;
}

interface QueueItem {
  index: number;
  text: string;
  filename: string;
  status: "pending" | "running" | "done" | "failed";
  duration?: number;
}

function parseScript(name: string, content: string): QueueItem[] {
  const extension = name.split(".").pop()?.toLowerCase();

  if (extension === "csv") {
    return content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(1)
      .map((line, index) => {
        const [text = "", custom = ""] = line.split(",");
        return {
          index: index + 1,
          text: text.trim(),
          filename: (custom.trim() || `batch_${String(index + 1).padStart(4, "0")}.wav`),
          status: "pending" as const,
        };
      })
      .filter((item) => item.text);
  }

  if (extension === "srt") {
    return content
      .split(/\r?\n\s*\r?\n/)
      .map((block) => {
        const lines = block
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((line) => line && !/^\d+$/.test(line) && !line.includes("-->"));
        return lines.join(" ");
      })
      .filter(Boolean)
      .map((text, index) => ({
        index: index + 1,
        text,
        filename: `subtitle_${String(index + 1).padStart(4, "0")}.wav`,
        status: "pending" as const,
      }));
  }

  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text, index) => ({
      index: index + 1,
      text,
      filename: `line_${String(index + 1).padStart(4, "0")}.wav`,
      status: "pending" as const,
    }));
}

export function BatchPage({ online }: BatchPageProps) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!online) {
      setEngines(mockEngines);
      return;
    }
    let cancelled = false;
    void api
      .listEngines()
      .then((next) => {
        if (cancelled) return;
        setEngines(next);
        const current = next.find((engine) => engine.name === engineName);
        if (!current?.is_available) {
          const preferred = next.find((engine) => engine.is_available) ?? next[0];
          if (preferred) setEngineName(preferred.name);
        }
      })
      .catch(() => {
        if (!cancelled) setEngines(mockEngines);
      });
    return () => {
      cancelled = true;
    };
    // engineName intentionally excluded: we only want to auto-correct on load/availability change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  const importFile = async (file: File) => {
    const content = await file.text();
    const parsed = parseScript(file.name, content);
    setItems(parsed);
    setFileName(file.name);
    setProgress(0);
    toast.success(`Loaded ${parsed.length} lines`, { description: file.name });
  };

  const start = () => {
    if (!items.length) {
      toast.error("Import a script first");
      return;
    }
    toast.message("Batch rendering is wiring into the job queue", {
      description:
        "This screen is ready; the sidecar batch endpoint is the next migration slice.",
    });
  };

  const stop = () => {
    toast.message("Nothing is running");
  };

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Batch Speech Generation</h1>
          <p className="text-sm text-muted-foreground">
            Queue and generate speech for multiple scripts, dialog lines or subtitles automatically.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.csv,.srt"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void importFile(file);
              event.target.value = "";
            }}
          />
          <Button variant="outline" onClick={() => inputRef.current?.click()}>
            <FileUp />
            Import script
          </Button>
          <Button onClick={start}>
            <Play />
            Start batch
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-4 pt-5 md:grid-cols-3">
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Voice and engine</p>
            <Select value={engineName} onValueChange={(value: string | null) => value && setEngineName(value)}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select an engine" />
              </SelectTrigger>
              <SelectContent>
                {engines.map((engine) => (
                  <SelectItem
                    key={engine.name}
                    value={engine.name}
                    disabled={!engine.is_available}
                  >
                    {engine.name}
                    {!engine.is_available && (
                      <span className="text-muted-foreground"> · not installed</span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Output folder</p>
            <div className="flex h-8 items-center rounded-lg border border-input bg-transparent px-2.5 text-sm text-muted-foreground">
              Default exports directory
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Source</p>
            <div className="flex h-8 items-center gap-2 rounded-lg border border-input bg-transparent px-2.5 text-sm">
              <Layers className="size-3.5 text-muted-foreground" />
              <span className={fileName ? "truncate" : "text-muted-foreground"}>
                {fileName || "No script imported"}
              </span>
              {fileName && <Badge variant="secondary">{items.length} lines</Badge>}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Generation Queue</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={stop}>
                <Square />
                Stop
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setItems([]);
                  setFileName("");
                  setProgress(0);
                }}
              >
                <Trash2 />
                Clear
              </Button>
            </div>
          </div>
          <Progress value={progress} className="mt-3" />
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-14">#</TableHead>
                <TableHead>Output Audio File</TableHead>
                <TableHead className="max-w-[640px]">Script to Speak</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Audio Length</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.index}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {item.index}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{item.filename}</TableCell>
                  <TableCell className="max-w-[640px] truncate text-muted-foreground">
                    {item.text}
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.status === "done" ? "default" : "outline"}>
                      {item.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {item.duration ? `${item.duration.toFixed(2)}s` : "--"}
                  </TableCell>
                </TableRow>
              ))}
              {!items.length && (
                <TableRow>
                  <TableCell colSpan={5} className="py-14 text-center">
                    <Layers className="mx-auto mb-3 size-8 text-muted-foreground/50" />
                    <p className="text-sm font-medium">The queue is empty</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Import a .txt, .csv or .srt script to build it.
                    </p>
                    {online === false && (
                      <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                        Python engine offline — import still works locally for preview.
                      </p>
                    )}
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
