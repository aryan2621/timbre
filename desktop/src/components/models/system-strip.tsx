import type { SystemSpecs } from "@/lib/types";

export function SystemStrip({ specs }: { specs: SystemSpecs }) {
  const memory =
    specs.accelerator === "cuda"
      ? `${specs.memory_budget_gb} GB`
      : `${specs.ram_gb} GB`;
  return (
    <p className="text-xs text-muted-foreground">
      {specs.accelerator_name.replace(/ GPU| \(.*\)/g, "")} · {memory} · {Math.round(specs.disk_free_bytes / 1024 ** 3)} GB free
    </p>
  );
}
