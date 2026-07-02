# Privacy and Legal UI Notes

Last updated: July 2, 2026

## Scope

Worker B added P0 public legal UI routes for:

- `/privacy`
- `/terms`
- `/cookies`
- `/subprocessors`
- `/security`
- `/.well-known/security.txt`

The frontend copy is intentionally concise and token-backed, and it avoids
clickwrap language or checkbox consent. Login footer links now resolve because
the target pages exist. Chat/admin account menus expose Privacy Policy and Terms
of Service, and settings exposes the full legal page set.

## Notices

- Profile completion includes a privacy handling notice without agreement
  language.
- Conversation upload copy states that files stay scoped to the conversation.
- Admin KB upload copy reminds admins to upload department-approved content.

## Follow-up Before Production

- Replace placeholder legal copy with counsel-approved policy text.
- Replace `security@playbook.example` in `frontend/src/lib/legalContent.ts` with
  the approved production security mailbox.
- Replace the prototype subprocessor categories with the approved named vendor
  register before launch.
