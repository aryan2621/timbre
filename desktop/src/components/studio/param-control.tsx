import { RotateCcw, Dice1 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface ParamControlProps {
  label: string;
  description?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  digits?: number;
  /** The engine default, used by the reset button. */
  resetValue?: number;
  onChange: (value: number) => void;
  /** Optional: show a randomize button (for seed fields). */
  showRandomize?: boolean;
  onRandomize?: () => void;
}

/**
 * A single tunable parameter.
 *
 * The value is displayed above the slider, no number input.
 */
export function ParamControl({
  label,
  description,
  value,
  min,
  max,
  step,
  suffix,
  digits = 2,
  resetValue,
  onChange,
  showRandomize,
  onRandomize,
}: ParamControlProps) {
  const display = digits === 0 ? Math.round(value).toString() : value.toFixed(digits);
  const canReset = resetValue !== undefined && Math.abs(resetValue - value) > 1e-6;

  return (
    <Field className="gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <FieldLabel className="text-[13px] font-medium leading-tight">
            {label}
          </FieldLabel>
          {description ? (
            <FieldDescription className="mt-0.5 text-[11.5px] leading-snug">
              {description}
            </FieldDescription>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <span className="w-[68px] text-right font-mono text-xs text-foreground">
            {display}{suffix ? <span className="text-muted-foreground">{suffix}</span> : null}
          </span>
          {showRandomize && onRandomize ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label="Randomize seed"
                    onClick={onRandomize}
                  >
                    <Dice1 className="size-3.5" />
                  </Button>
                }
              >
                <Dice1 className="size-3.5" />
              </TooltipTrigger>
              <TooltipContent>Randomize</TooltipContent>
            </Tooltip>
          ) : null}
          {canReset ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Reset ${label}`}
                    onClick={() => onChange(resetValue)}
                  />
                }
              >
                <RotateCcw />
              </TooltipTrigger>
              <TooltipContent>Reset to {resetValue}</TooltipContent>
            </Tooltip>
          ) : null}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Slider
          value={[value]}
          min={min}
          max={max}
          step={step}
          aria-label={label}
          onValueChange={(next) =>
            onChange(typeof next === "number" ? next : (next[0] ?? min))
          }
          className="flex-1"
        />
        <span className="w-8 shrink-0 text-right font-mono text-[10px] text-muted-foreground/70">
          {min}
        </span>
      </div>
    </Field>
  );
}
