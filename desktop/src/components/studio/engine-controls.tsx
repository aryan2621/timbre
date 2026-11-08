import { Field, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ParamControl } from "@/components/studio/param-control";
import type { ParamExtra, ParamSpec } from "@/lib/types";

interface Values {
  extra?: ParamExtra;
}

interface Props<T extends Values> {
  controls: ParamSpec[] | undefined;
  group: ParamSpec["group"];
  params: T;
  defaults: T | undefined;
  onChange: (patch: Partial<T>) => void;
}

const digitsFor = (step: number) => (step >= 1 ? 0 : step >= 0.1 ? 1 : 2);

export function EngineControls<T extends Values>({ controls, group, params, defaults, onChange }: Props<T>) {
  const record = params as Record<string, unknown>;
  const defaultRecord = (defaults ?? {}) as Record<string, unknown>;
  const read = (source: Record<string, unknown>, spec: ParamSpec) =>
    (spec.key in source ? source[spec.key] : (source.extra as ParamExtra | undefined)?.[spec.key]) ?? spec.default;
  const write = (spec: ParamSpec, value: number | string) =>
    onChange(
      spec.key in record
        ? ({ [spec.key]: value } as Partial<T>)
        : ({ extra: { ...params.extra, [spec.key]: value } } as unknown as Partial<T>),
    );

  return (
    <>
      {(controls ?? []).filter((spec) => spec.group === group).map((spec) =>
        spec.kind === "select" ? (
          <Field key={spec.key} className="gap-2">
            <FieldLabel>{spec.label}</FieldLabel>
            <Select value={String(read(record, spec))} onValueChange={(value) => value !== null && write(spec, value)}>
              <SelectTrigger className="w-full">
                <SelectValue>{(value) => (value ? String(value) : "Auto")}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {spec.options.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option || "Auto"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        ) : (
          <ParamControl
            key={spec.key}
            label={spec.label}
            description={spec.description || undefined}
            value={Number(read(record, spec))}
            min={spec.min}
            max={spec.max}
            step={spec.step}
            digits={digitsFor(spec.step)}
            resetValue={Number(read(defaultRecord, spec))}
            onChange={(value) => write(spec, value)}
          />
        ),
      )}
    </>
  );
}
