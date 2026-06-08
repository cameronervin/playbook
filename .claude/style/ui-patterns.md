# Playbook UI Patterns

Use `docs/design/` as the visual source of truth.

## Primitive Strategy

- Build local primitives in `frontend/src/components/ui/`.
- Use Radix for dialogs, dropdown menus, tabs, tooltips, and switches.
- Do not initialize shadcn/ui unless a later plan explicitly adopts it.
- Use `lucide-react` for normal icons.
- Inline SVG is allowed only for the Playbook mark and Microsoft/Google SSO logos.

## Screens

- Login: SSO-only card, Microsoft first, Google second, no email/password.
- Chat: left history rail, center chat surface, sources panel open by default.
- Admin: admin-only shell; athletes see access denied; Users & roles is super-admin only.
- Admin tables: keep row actions, dropdown menus, metadata, and column labels compact
  with the shared `pb-admin-table-*` and `pb-admin-menu*` globals. Search/filter
  controls for a table should sit in the table surface header when they operate
  only on that table.
- Settings modals: keep tab labels, pane headings, field labels, field values,
  metadata, and badges compact with the shared `pb-settings-*` globals. Avoid
  translating screenshot text into generic Tailwind type utilities.

## Behavior

- Server state: TanStack Query hooks.
- UI state: Zustand stores.
- Missing backend APIs: typed fixtures under `frontend/src/lib/fixtures/`.
- Motion must honor `prefers-reduced-motion`.
- Copy should be calm, plain-spoken, and sentence case.
