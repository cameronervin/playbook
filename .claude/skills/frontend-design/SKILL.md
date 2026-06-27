# Playbook Frontend Design

Use this skill for Playbook UI work. The visual direction is already defined by
the Claude Design handoff; do not invent a new aesthetic.

## Required Context

Read these before frontend edits:

- `backstage/design/README.md`
- `backstage/design/frontend_wireframe_implementation_plan.md`
- `backstage/design/source/colors_and_type.css`
- The relevant reference screen in `backstage/design/design-reference/`

## Direction

Playbook is a dark, precise athletics operations product: warm charcoal
surfaces, restrained OSU-orange accents, sharp borders, local Archivo/Sora/Inter
type, and calm coaching-staff copy. Avoid generic blue/purple AI gradients,
decorative blobs, and marketing-style hero pages.

## Implementation Rules

- Use Next.js App Router, Tailwind v4 tokens, TanStack Query, Zustand, and local
  Playbook primitives.
- Use Radix primitives for dialogs, dropdowns, tabs, tooltips, and switches.
- Use `lucide-react` for ordinary icons.
- Inline SVG is allowed only for the Playbook mark and SSO provider logos.
- Treat `backstage/design/source/` as structural reference, not production code.
- Drop prototype quirks: Tweaks panels, CDN React, Babel, `window` globals, and
  fake `window.location` navigation.
- Keep server state in TanStack Query and UI-only state in Zustand.
