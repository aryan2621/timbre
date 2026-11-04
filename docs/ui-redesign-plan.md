# VoiceClone Studio — Minimal UI Plan

> Updated: 2026-11-05
> Scope: simplify the existing Tauri + React desktop UI. This is a source-based review, not a new live visual audit.

## Goal

Apply minimalism consistently across the **entire platform**, not only Studio: the app shell, all six pages, dialogs, tables, settings, and status feedback. Make each screen feel calm and direct by showing the information and actions needed for the current task, and progressively disclosing the rest.

The aim is **less UI, not less capability**. Preserve consent and licensing information, honest engine state, accessible controls, and the complete rendering workflow.

## Platform-wide minimal UI standard

Use the following standard on every screen and shared component:

- **One clear hierarchy:** page title, task content, one primary action. Avoid competing headlines, repeated section titles, and multiple primary buttons.
- **Show only useful information:** remove decorative counts, redundant chips, repeated descriptions, and metadata that does not help the current task. Keep necessary safety, licensing, progress, and recovery information.
- **Use fewer containers:** group related controls with spacing and subtle dividers instead of wrapping every item in a card, badge, or nested panel.
- **Keep actions consistent:** primary actions are visible; secondary actions are quieter or placed in an overflow menu; destructive actions remain clear and confirmed.
- **Use concise copy:** label controls once. Reserve helper text for consequential choices, constraints, or recovery. Avoid repeating privacy, offline, engine, or license statements across the shell and page.
- **Reveal complexity when requested:** default views serve the common workflow; advanced tuning, rarely changed settings, and technical metadata remain available but out of the way.
- **Make state visible without noise:** use one authoritative status location per concept. Only show progress, warnings, and activity when they reflect a real state.
- **Treat motion as feedback, not decoration:** animate only to clarify a state transition or playback; avoid constant pulsing, staggered entrance effects, and motion without meaning.
- **Apply the same rules on narrow windows:** reflow and simplify secondary content rather than shrinking controls or adding more scrolling.

Before adding any UI element, ask: **Does this help the user decide, act, understand state, or recover?** If not, omit it.

## Studio example: put Script and Output in one row

The Studio currently puts the Script and Output cards one after another. At desktop widths, place them side by side so the user can edit text and see the resulting audio in one compact workspace. Stack them on narrow windows. This is one concrete application of the platform-wide standard, not the limit of the simplification work.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Studio     Voice ▾     Engine ▾                              Render      │
├─────────────────────────────────────┬──────────────────────────────────┤
│ Script                              │ Output                           │
│                                     │                                  │
│ Type or paste text…                 │   compact waveform               │
│                                     │   ▶  0:00 ───────── 0:12         │
│                                     │   Play / pause        Export     │
│ 128 words · ~45 sec                 │                                  │
└─────────────────────────────────────┴──────────────────────────────────┘
```

- Give the script the larger share of the row; keep the output player compact and aligned with it.
- Put voice and engine selection where they are easy to find, rather than hiding essential setup behind a generic “Settings” label. Keep less common controls in a clearly named **Voice & delivery** panel.
- Keep one obvious **Render** action. Avoid competing render buttons in the header, page body, and empty output state.
- On small windows, stack Script above Output; do not shrink either into an unusable column.

### Waveform and playback

Use the waveform as a small, useful playback visual—not a second dashboard or full audio-editing surface.

- Show the actual audio waveform when a render is ready. Keep it short and horizontally compact.
- Provide the essentials: play/pause, elapsed and total time, seek, and export. Keep secondary controls out of the default view unless they are already needed by users.
- During playback, animate a subtle playhead or a restrained waveform highlight. During rendering, show a small activity/progress cue tied to real job state; do not invent waveform data that the backend has not produced.
- Keep the visualization still when idle, and respect reduced-motion preferences.
- Do not add zoom, regions, markers, looping, or an elaborate timeline unless real user workflows require them.
- Do not repeat the same “no render yet” explanation, action, and render button in both the output area and elsewhere on the page.

## Current UI observations

The current source already includes several features proposed by the earlier redesign: a routed Settings page, a command palette, an engine status provider, searchable voice selection, a functional batch queue, history filtering/virtualization, and a wavesurfer-based player. The previous version of this document incorrectly described several of those as missing.

The simplification review applies to every area, not just Studio:

- **Shell:** search is offered in both the sidebar and header; engine status is shown in both the header and sidebar. Choose one place for each. Keep global actions limited to those that are genuinely global.
- **Studio:** Script and Output are separate full-width cards; core voice/engine choices are in a drawer titled “Settings”; a global “New render” competes with the page’s “Synthesize”; the output empty state adds another render action; several counts and chunk chips compete for attention.
- **Voices:** keep consent, quality, search, and audition, but avoid repeating consent and quality details across filters, chips, and profile cards. Keep creation focused on required inputs.
- **Batch:** keep real import, queue, progress, and cancellation, while keeping setup and per-line details compact until they matter.
- **History:** preserve retrieval and bulk actions, but prioritize script, voice, date, and playback; make technical fields and secondary actions quieter.
- **Models:** preserve download and license decisions, but avoid repeating license notices, installed counts, or storage summaries in multiple places.
- **Settings and dialogs:** preserve settings and save/revert behavior; avoid a drawer duplicating a routed page, shortcuts repeated in multiple places, or helper text that restates the control label.
- **Shared visual language:** avoid turning every statistic, label, and action into a badge, card, icon button, or animation. Use those treatments only when they improve scanning or interaction.
- **Documentation:** the general README and `desktop/README.md` should describe the active desktop workflow and current app, not old or removed frontends.

## Page-by-page direction

### Studio

- Make Script and Output a single responsive row on desktop.
- Bring voice selection and engine selection close to the script. Keep language alongside voice/engine only if it is required for the selected engine or changes often.
- Rename the tuning drawer to **Voice & delivery**. Keep the consent/provenance and engine license details accessible, but do not repeat long privacy and license explanations in multiple places.
- Keep a compact script summary (for example word count and estimated duration). Show chunk details only when useful; avoid displaying character count, word count, duration, chunk count, and sentence chips all at once by default.
- Use one Render action, one compact output player, and one real progress/cancel state while rendering.
- Leave seed and specialist model parameters under Advanced.

### Voices

- Keep the searchable voice list, consent state, quality information, audition, and create/delete actions.
- Make the voice name and audition the focus. Group less-used metadata; avoid showing the same consent or quality information in several places.
- Keep the new-profile flow short: name, reference recording, language if needed, consent confirmation. Make notes optional or secondary.
- Keep the file picker and a clear empty-state action. Avoid extra onboarding prose once the next action is obvious.

### Batch

- Keep the real import, queue, progress, and cancellation workflow.
- Make setup compact: script, voice, engine, and output location. Hide or defer optional details.
- Show per-line filename and status; reveal errors and less-used metadata when relevant rather than permanently expanding every row.
- Do not add queue controls that the backend does not support.

### History

- Keep search/filter, play, export, delete, and reuse because they support real retrieval workflows.
- Make playback the most visible row action; move secondary actions to a compact overflow menu if the layout feels crowded.
- Keep date, voice, script preview, and duration easy to scan. Hide technical metadata such as seed unless needed.

### Models

- Keep model availability, download state/progress, size, and license information; these affect user decisions and should not be removed.
- Use a concise model row/card with one clear action. Avoid a separate download dashboard or repeated license explanation unless active downloads make it necessary.
- State plainly when an internet connection is needed to download weights.

### Settings

- Keep settings as a page; it should not also be represented as a Studio drawer.
- Keep the section list and save/revert behavior, but make search find actual settings or remove it.
- Put rarely changed synthesis defaults and diagnostics in appropriately named sections. Keep appearance and common defaults easy to locate.
- Do not repeat keyboard shortcuts in multiple places; a single shortcuts reference is sufficient.

## What not to remove

- Consent confirmation and the ability to inspect consent status.
- Model and engine license restrictions.
- Clear connection, render, download, error, and cancellation states.
- Keyboard access, focus indication, and reduced-motion support.
- Useful filtering, playback, export, and destructive-action confirmation.

These are functional or trust-related, not decoration. Simplify their presentation, not their meaning.

## Suggested implementation order

| Order | Change | Done when |
| --- | --- | --- |
| 1 | Apply shared minimal UI rules | All six pages, the shell, dialogs, and shared components use one hierarchy, concise copy, fewer containers, and one primary action per context. |
| 2 | Remove global duplication | Search, engine status, render actions, shortcut references, and privacy messaging each have one deliberate home. |
| 3 | Simplify each page | Studio, Voices, Batch, History, Models, and Settings each retain their core workflow while secondary information and controls become quieter or progressive. |
| 4 | Reflow Studio workspace | Script and compact Output sit side by side on desktop and stack cleanly on narrow windows; waveform motion reflects actual state. |
| 5 | Align documentation | README and desktop instructions reflect the actual current frontend, startup steps, and supported capabilities. |

## Validation checklist

- Review every page, shared shell surface, and dialog for duplicate labels/actions, unnecessary cards/badges, and repeated explanations.
- Check all pages at desktop and narrow window widths.
- Test render start, progress, completion, failure, cancellation, playback, seeking, and export.
- Verify waveform animation reflects actual playback/render state and stops when idle.
- Check light/dark themes, keyboard-only navigation, visible focus, and reduced motion.
- Confirm consent, license, download, and offline/engine messaging remain accurate.
- Run the existing frontend build/type check after implementation.
