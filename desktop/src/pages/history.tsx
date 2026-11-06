import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  flexRender,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import {
  getFilteredRowModel,
  getSortedRowModel,
  legacyCreateColumnHelper,
  useLegacyTable,
  type LegacyColumnDef,
} from "@tanstack/react-table/legacy";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  AudioLines,
  Download,
  History as HistoryIcon,
  Pause,
  Play,
  RotateCcw,
  Search,
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
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { PageHeader, StatChip } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { MiniWaveform } from "@/components/history/mini-waveform";
import { useApp } from "@/lib/app-context";
import { useEngineStatus } from "@/lib/engine-status";
import {
  formatAbsoluteDate,
  formatDuration,
  formatRelativeDate,
} from "@/lib/format";
import {
  useHistoryEntries,
  useHistoryPlayback,
} from "@/hooks/use-history";
import type { HistoryEntry } from "@/lib/types";

const columnHelper = legacyCreateColumnHelper<HistoryEntry>();

const ROW_HEIGHT = 56;

/**
 * The render history.
 *
 * The old table rendered every row the backend returned, with no sorting, no
 * filter, no selection, no waveform and a `7.23s` duration. It is now a
 * virtualized table with sorting, a text filter, row selection, an inline
 * waveform per take, a copyable seed and bulk actions.
 */
export function HistoryPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";
  const { navigate } = useApp();

  const [query, setQuery] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    entries,
    loading,
    pendingDelete,
    setPendingDelete,
    confirmClear,
    setConfirmClear,
    remove,
    clearAll,
  } = useHistoryEntries(online, () => setRowSelection({}));

  const { playingId, progress, peaksById, preview, ensurePeaks, exportEntry } =
    useHistoryPlayback(online);

  /* ------------------------------------------------------------- actions */

  const reuseScript = useCallback(
    (entry: HistoryEntry) => {
      navigate("studio");
      toast.message("Opening the Studio", {
        description: `The script from ${entry.voice_name} is ready to reuse.`,
      });
    },
    [navigate],
  );

  /* --------------------------------------------------------------- table */

  // TanStack's column helper requires the `any` value generic here.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const columns = useMemo<LegacyColumnDef<HistoryEntry, any>[]>(
    () => [
      columnHelper.display({
        id: "select",
        size: 36,
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllRowsSelected()}
            indeterminate={table.getIsSomeRowsSelected()}
            aria-label="Select every row"
            onCheckedChange={(checked) =>
              table.toggleAllRowsSelected(checked === true)
            }
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            aria-label={`Select the render from ${row.original.voice_name}`}
            onCheckedChange={(checked) => row.toggleSelected(checked === true)}
          />
        ),
      }),
      columnHelper.accessor("created_at", {
        header: "Created",
        size: 150,
        cell: ({ getValue }) => {
          const value = String(getValue());
          return (
            <span title={formatAbsoluteDate(value)} className="whitespace-nowrap">
              {formatRelativeDate(value)}
            </span>
          );
        },
      }),
      columnHelper.accessor("voice_name", {
        header: "Voice",
        size: 160,
        cell: ({ getValue }) => (
          <span className="font-medium">{String(getValue() || "—")}</span>
        ),
      }),
      columnHelper.accessor("engine_name", {
        header: "Engine",
        size: 150,
        cell: ({ getValue }) => (
          <Badge variant="outline">{String(getValue())}</Badge>
        ),
      }),
      columnHelper.accessor("prompt_text", {
        header: "Script",
        size: 290,
        enableSorting: false,
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate text-[13px]">{row.original.prompt_text}</p>
            <MiniWaveform
              peaks={peaksById[row.original.id]}
              progress={progress[row.original.id] ?? 0}
              className="mt-1 h-3"
              bars={64}
            />
          </div>
        ),
      }),
      columnHelper.accessor("duration_seconds", {
        header: "Length",
        size: 90,
        cell: ({ getValue }) => (
          <span data-numeric className="font-mono text-xs">
            {formatDuration(Number(getValue()))}
          </span>
        ),
      }),
      columnHelper.accessor("seed", {
        header: "Seed",
        size: 90,
        cell: ({ getValue }) => (
          <span data-numeric className="font-mono text-xs text-muted-foreground">
            {String(getValue())}
          </span>
        ),
      }),
      columnHelper.display({
        id: "actions",
        size: 150,
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-1">
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    size="icon-sm"
                    className={
                      playingId === row.original.id
                        ? "rounded-full"
                        : "rounded-full bg-primary/10 text-primary hover:bg-primary/20"
                    }
                    aria-label={
                      playingId === row.original.id
                        ? "Pause the take"
                        : "Play the take"
                    }
                    onClick={() => preview(row.original)}
                  />
                }
              >
                {playingId === row.original.id ? (
                  <Pause className="fill-current" />
                ) : (
                  <Play className="translate-x-px fill-current" />
                )}
              </TooltipTrigger>
              <TooltipContent>
                {playingId === row.original.id ? "Pause" : "Play"}
              </TooltipContent>
            </Tooltip>
            <span aria-hidden className="mx-1 h-4 w-px bg-border" />
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Export the take"
                    onClick={() => void exportEntry(row.original)}
                  />
                }
              >
                <Download />
              </TooltipTrigger>
              <TooltipContent>Export WAV</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Reuse this script"
                    onClick={() => reuseScript(row.original)}
                  />
                }
              >
                <RotateCcw />
              </TooltipTrigger>
              <TooltipContent>Reuse in the Studio</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Delete the take"
                    onClick={() => setPendingDelete(row.original)}
                  />
                }
              >
                <Trash2 />
              </TooltipTrigger>
              <TooltipContent>Delete</TooltipContent>
            </Tooltip>
          </div>
        ),
      }),
    ],
    [exportEntry, peaksById, preview, progress, reuseScript, playingId],
  );

  const table = useLegacyTable<HistoryEntry>({
    data: entries,
    columns,
    state: { sorting, rowSelection, globalFilter: query },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    globalFilterFn: (row, _columnId, filterValue) => {
      const term = String(filterValue ?? "").trim().toLowerCase();
      if (!term) return true;
      const entry = row.original;
      return (
        entry.prompt_text.toLowerCase().includes(term) ||
        entry.voice_name.toLowerCase().includes(term) ||
        entry.engine_name.toLowerCase().includes(term)
      );
    },
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
  });

  const rows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  useEffect(() => {
    const visible = virtualizer.getVirtualItems();
    for (const item of visible) {
      const row = rows[item.index];
      if (row) ensurePeaks(row.original.id);
    }
  }, [ensurePeaks, rows, virtualizer]);

  const selectedRows = table.getSelectedRowModel().rows;
  const totalDuration = entries.reduce(
    (sum, entry) => sum + (entry.duration_seconds ?? 0),
    0,
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="History"
        description="Every render you made, with the settings that produced it."
        icon={HistoryIcon}
        meta={
          <>
            <StatChip icon={HistoryIcon}>{entries.length} renders</StatChip>
            <StatChip icon={AudioLines}>{formatDuration(totalDuration)}</StatChip>
          </>
        }
        actions={
          <Button
            variant="outline"
            onClick={() => setConfirmClear(true)}
            disabled={!entries.length}
          >
            <Trash2 />
            Clear all
          </Button>
        }
      />

      {/* --------------------------------------------------------- toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by script, voice or engine"
            aria-label="Filter the history"
            className="pl-8"
          />
        </div>

        {selectedRows.length ? (
          <div className="flex items-center gap-2 rounded-md border border-primary/25 bg-surface-accent px-2.5 py-1.5 text-xs">
            <span className="font-medium text-primary">
              {selectedRows.length} selected
            </span>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                setRowSelection({});
              }}
            >
              Clear
            </Button>
          </div>
        ) : null}
      </div>

      {/* ----------------------------------------------------------- table */}
      <Card className="overflow-hidden p-0 shadow-[var(--shadow-soft)]">
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3, 4, 5].map((index) => (
                <Skeleton key={index} className="h-12 rounded-md" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <Empty className="border-0 py-16">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <HistoryIcon />
                </EmptyMedia>
                <EmptyTitle>No renders yet</EmptyTitle>
                <EmptyDescription>
                  Everything you synthesise in the Studio lands here with its
                  voice, engine, seed and waveform.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={() => navigate("studio")}>
                  <AudioLines />
                  Render something
                </Button>
              </EmptyContent>
            </Empty>
          ) : rows.length === 0 ? (
            <Empty className="border-0 py-16">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Search />
                </EmptyMedia>
                <EmptyTitle>Nothing matches “{query}”</EmptyTitle>
                <EmptyDescription>
                  Try a different phrase, a voice name or an engine name.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button variant="outline" onClick={() => setQuery("")}>
                  Clear the filter
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <div>
              <div className="flex items-center border-b border-border/70 bg-surface-inset/50 px-3">
                {table
                  .getHeaderGroups()[0]
                  ?.headers.map((header) => (
                    <div
                      key={header.id}
                      className="flex shrink-0 items-center gap-1 px-2 py-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground"
                      style={{ width: header.getSize() }}
                    >
                      {header.isPlaceholder ? null : header.column.getCanSort() ? (
                        <button
                          type="button"
                          className="flex items-center gap-1 transition-colors hover:text-foreground"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          {header.column.getIsSorted() === "asc" ? (
                            <ArrowUp className="size-3" />
                          ) : header.column.getIsSorted() === "desc" ? (
                            <ArrowDown className="size-3" />
                          ) : (
                            <ArrowUpDown className="size-3 opacity-40" />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </div>
                  ))}
              </div>

              <div
                ref={scrollRef}
                className="max-h-[560px] overflow-auto"
                role="table"
                aria-label="Render history"
              >
                <div
                  className="relative w-full"
                  style={{ height: virtualizer.getTotalSize() }}
                >
                  {virtualizer.getVirtualItems().map((virtualRow) => {
                    const row = rows[virtualRow.index];
                    if (!row) return null;
                    return (
                      <div
                        key={row.id}
                        role="row"
                        className="absolute top-0 left-0 flex w-full items-center border-b border-border/50 px-3 transition-colors hover:bg-muted/40 data-[selected=true]:bg-surface-accent/50"
                        style={{
                          height: virtualRow.size,
                          transform: `translateY(${virtualRow.start}px)`,
                        }}
                        data-selected={row.getIsSelected()}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <div
                            key={cell.id}
                            role="cell"
                            className="min-w-0 shrink-0 overflow-hidden px-2 text-[13px]"
                            style={{ width: cell.column.getSize() }}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ------------------------------------------------------ alert dialog */}
      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this take?</AlertDialogTitle>
            <AlertDialogDescription>
              The history entry and its rendered audio file are removed from this
              machine. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction onClick={() => void remove()}>
              Delete take
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmClear} onOpenChange={setConfirmClear}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear the whole history?</AlertDialogTitle>
            <AlertDialogDescription>
              Every history entry and every rendered audio file is deleted from
              this machine. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep them</AlertDialogCancel>
            <AlertDialogAction onClick={() => void clearAll()}>
              Clear history
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
