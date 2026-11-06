/**
 * Shared motion vocabulary.
 *
 * Every animation in the app comes from this file so timing stays consistent:
 * 120ms for micro feedback, 180ms for standard transitions, 240ms for the
 * expressive ones (page changes, progress). Everything collapses to an
 * opacity-only variant when the user asked for reduced motion.
 */
import type { Variants } from "motion/react";

const EASE_OUT = [0.22, 1, 0.36, 1] as const;
const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

const DURATION_BASE = 0.18;

/** Route / page content. */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION_BASE, ease: EASE_OUT },
  },
  exit: {
    opacity: 0,
    y: -4,
    transition: { duration: 0.1, ease: EASE_IN_OUT },
  },
};
