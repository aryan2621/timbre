/**
 * Shared motion vocabulary.
 *
 * Every animation in the app comes from this file so timing stays consistent:
 * 120ms for micro feedback, 180ms for standard transitions, 240ms for the
 * expressive ones (page changes, progress). Everything collapses to an
 * opacity-only variant when the user asked for reduced motion.
 */
import type { Transition, Variants } from "motion/react";

export const EASE_OUT = [0.22, 1, 0.36, 1] as const;
export const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

export const DURATION_FAST = 0.12;
export const DURATION_BASE = 0.18;
export const DURATION_SLOW = 0.24;

export const springSoft: Transition = {
  type: "spring",
  stiffness: 420,
  damping: 34,
  mass: 0.8,
};

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

/** Cards / rows that mount in a list. */
export const listItemVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION_BASE, ease: EASE_OUT },
  },
};

/** The container that staggers its children. */
export const listContainerVariants: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.02, delayChildren: 0.02 } },
};

/** Popovers / menus / command palette. */
export const popoverVariants: Variants = {
  initial: { opacity: 0, scale: 0.98, y: -4 },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { duration: DURATION_FAST, ease: EASE_OUT },
  },
  exit: {
    opacity: 0,
    scale: 0.98,
    transition: { duration: 0.08 },
  },
};

/** Dialog / sheet. */
export const dialogVariants: Variants = {
  initial: { opacity: 0, scale: 0.97, y: 8 },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { duration: DURATION_BASE, ease: EASE_OUT },
  },
  exit: {
    opacity: 0,
    scale: 0.98,
    y: 4,
    transition: { duration: 0.12, ease: EASE_IN_OUT },
  },
};

/** Crossfade used when a skeleton is replaced by real content. */
export const fadeVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.2, ease: EASE_IN_OUT } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};

/** The render progress bar fill. */
export const progressVariants: Variants = {
  initial: { scaleX: 0 },
  animate: {
    scaleX: 1,
    transition: { duration: DURATION_SLOW, ease: EASE_OUT },
  },
};
