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

## Behavior

- Server state: TanStack Query hooks.
- UI state: Zustand stores.
- Missing backend APIs: typed fixtures under `frontend/src/lib/fixtures/`.
- Motion must honor `prefers-reduced-motion`.
- Copy should be calm, plain-spoken, and sentence case.
