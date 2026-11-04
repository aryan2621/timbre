/**
 * Global hotkey handling.
 *
 * Combos are written as `mod+shift+e` where `mod` is ⌘ on macOS and Ctrl
 * elsewhere. Typing inside an input, textarea or contenteditable never
 * triggers a shortcut.
 */
import { useEffect, useRef } from "react";

const IS_APPLE =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);

export type HotkeyHandler = (event: KeyboardEvent) => void;

export interface HotkeyOptions {
  enabled?: boolean;
  /** Fire even while a text field has focus. Off by default. */
  allowInInputs?: boolean;
}

function normalizeKey(event: KeyboardEvent): string {
  const key = event.key;
  if (key === " ") return "space";
  if (key === "Escape") return "escape";
  if (key === "Enter") return "enter";
  if (key === "Backspace") return "backspace";
  if (key === "ArrowLeft") return "arrowleft";
  if (key === "ArrowRight") return "arrowright";
  if (key === "?") return "?";
  return key.toLowerCase();
}

function matches(event: KeyboardEvent, combo: string): boolean {
  const parts = combo.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  if (normalizeKey(event) !== key) return false;

  const wantsMeta = parts.includes("mod");
  const wantsShift = parts.includes("shift");
  const wantsAlt = parts.includes("alt");
  const wantsCtrl = parts.includes("ctrl");

  const metaPressed = IS_APPLE ? event.metaKey : event.ctrlKey;
  const ctrlPressed = IS_APPLE ? event.ctrlKey : false;

  if (wantsMeta !== metaPressed) return false;
  if (wantsShift !== event.shiftKey) return false;
  if (wantsAlt !== event.altKey) return false;
  if (wantsCtrl !== ctrlPressed) return false;

  return true;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    target.isContentEditable
  );
}

/**
 * Binds a set of shortcuts for the lifetime of the component.
 *
 * The map is read through a ref so re-renders never re-bind the listener.
 */
export function useHotkeys(
  handlers: Record<string, HotkeyHandler>,
  { enabled = true, allowInInputs = false }: HotkeyOptions = {},
): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      if (!allowInInputs && isTypingTarget(event.target)) return;

      for (const [combo, handler] of Object.entries(handlersRef.current)) {
        if (matches(event, combo)) {
          event.preventDefault();
          handler(event);
          return;
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled, allowInInputs]);
}
