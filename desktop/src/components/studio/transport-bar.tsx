import {
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "cn";
import { formatTimecode } from "@/lib/format";

interface TransportBarProps {
  playing: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  muted: boolean;
  disabled?: boolean;
  onPlayPause: () => void;
  onStop: () => void;
  onSkip: (seconds: number) => void;
  onVolumeChange: (volume: number) => void;
  onMuteToggle: () => void;
}

/**
 * The transport controls.
 *
 * One row, one hierarchy: the primary transport on the left, the clock next
 * to it, the secondary controls on the right.
 */
export function TransportBar({
  playing,
  currentTime,
  duration,
  volume,
  muted,
  disabled,
  onPlayPause,
  onStop,
  onSkip,
  onVolumeChange,
  onMuteToggle,
}: TransportBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <ButtonGroup>
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="icon"
                variant="default"
                aria-label={playing ? "Pause" : "Play"}
                disabled={disabled}
                onClick={onPlayPause}
              />
            }
          >
            {playing ? <Pause /> : <Play />}
          </TooltipTrigger>
          <TooltipContent>{playing ? "Pause" : "Play"}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="icon"
                variant="outline"
                aria-label="Stop and rewind"
                disabled={disabled}
                onClick={onStop}
              />
            }
          >
            <Square />
          </TooltipTrigger>
          <TooltipContent>Stop</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="icon"
                variant="outline"
                aria-label="Back 5 seconds"
                disabled={disabled}
                onClick={() => onSkip(-5)}
              />
            }
          >
            <SkipBack />
          </TooltipTrigger>
          <TooltipContent>Back 5s</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="icon"
                variant="outline"
                aria-label="Forward 5 seconds"
                disabled={disabled}
                onClick={() => onSkip(5)}
              />
            }
          >
            <SkipForward />
          </TooltipTrigger>
          <TooltipContent>Forward 5s</TooltipContent>
        </Tooltip>
      </ButtonGroup>

      <div
        data-numeric
        className="font-mono text-sm tabular-nums text-foreground"
        aria-live="off"
      >
        {formatTimecode(currentTime)}
        <span className="text-muted-foreground"> / {formatTimecode(duration)}</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={muted ? "Unmute" : "Mute"}
                onClick={onMuteToggle}
              />
            }
          >
            {muted ? <VolumeX /> : <Volume2 className={cn(volume < 40 && "opacity-70")} />}
          </TooltipTrigger>
          <TooltipContent>{muted ? "Unmute" : "Mute"}</TooltipContent>
        </Tooltip>

        <Slider
          value={[muted ? 0 : volume]}
          min={0}
          max={100}
          step={1}
          aria-label="Output volume"
          onValueChange={(next) =>
            onVolumeChange(typeof next === "number" ? next : (next[0] ?? 100))
          }
          className="w-24"
        />
        <span
          data-numeric
          className="w-9 text-right font-mono text-xs text-muted-foreground"
        >
          {muted ? "—" : `${Math.round(volume)}%`}
        </span>
      </div>
    </div>
  );
}
