# Frontend Design Standards

For Playbook UI work, read `docs/design/README.md`,
`docs/design/frontend_wireframe_implementation_plan.md`, and the relevant
reference screen before editing.

## Tokens And Styling

- Use Tailwind v4 tokens from `frontend/src/app/globals.css`.
- Use the Playbook orange and warm-charcoal system from `.claude/style/design-tokens.md`.
- Avoid hardcoded colors and repeated arbitrary values. Add named tokens/constants for repeated exact design dimensions.
- Controls use 8px radius; cards/dialogs use 12px.
- Dense admin surfaces must use the compact admin text/control globals from
  `frontend/src/app/globals.css` (`pb-admin-table-*`, `pb-admin-menu*`,
  `pb-admin-nav-*`) instead of generic `text-sm`, `text-base`, or default
  form-control sizing inside table rows.
- Compact settings/modal surfaces must use the settings text/control globals
  from `frontend/src/app/globals.css` (`pb-settings-*`) instead of generic
  `text-sm`, `text-base`, oversized mobile headings, or one-off arbitrary text
  sizes.
- Do not introduce blue/purple AI gradients, decorative blobs, or generic scaffold palettes.

## Icons

- Use `lucide-react` for normal icons.
- Inline SVG is allowed only for the Playbook mark and Microsoft/Google SSO provider logos.
- Do not draw icons with CSS boxes or pseudo-elements.

## Screen Fidelity

- Login is SSO-only: Microsoft first, Google second, no email/password.
- Chat keeps the history rail, center thread/composer, and sources panel open by default.
- Admin is role gated: athlete access denied, Users & roles super-admin only.
- Prototype-only Tweaks panels, CDN React/Babel, `window` globals, and fake HTML-page navigation must not ship.

## Accessibility

- Use Radix primitives for dialogs, menus, tabs, tooltips, and switches.
- All buttons and icon buttons need accessible names.
- Preserve keyboard focus rings and reduced-motion behavior.
