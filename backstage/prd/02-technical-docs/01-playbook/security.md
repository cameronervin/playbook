# Security Specification

This document defines Playbook MVP security, authorization, privacy, and safety requirements.

## Baseline

The scaffold includes FastAPI auth patterns, service-to-service auth for the KB service, Pydantic validation, structured errors, and logging guidance.

<!-- V2 CHANGE: Add Playbook OAuth/OIDC, role-based authorization, athlete conversation privacy, admin analytics anonymization, and safety policies. -->

## Authentication

| Area | Target |
|------|--------|
| Providers | Google and Microsoft OAuth/OIDC |
| Sessions | Short-lived app JWT in an HttpOnly cookie, backed by server-side `app_sessions` rows for sliding renewal and revocation |
| Passwords | No local password required for MVP |
| Tokens | OAuth provider tokens are never exposed to frontend app code |
| Vendor cost | No paid third-party auth vendor required for MVP |

App JWTs include the local user UUID and app session UUID, not provider tokens.
Authenticated activity refreshes the app session when the JWT is inside the
configured renewal threshold; expired or revoked sessions return 401 and the
frontend clears local state before routing to SSO. OAuth/SSO identity remains
the login bootstrap and is not refreshed on every app-session renewal.

## Roles

| Role | Permissions |
|------|-------------|
| `athlete` | Chat, upload conversation files, view own history |
| `admin` | Manage KB documents, view anonymized analytics, run dashboard insights, use admin chat |
| `super_admin` | Admin permissions plus user role management and audit log query |

Role storage must support future roles without schema redesign.

## Authorization Rules

1. Athletes can only access their own conversations, messages, and conversation files.
2. Athletes cannot access admin frontend routes.
3. Athletes cannot call admin API endpoints.
4. Admins can manage KB documents and analytics.
5. Admins cannot promote users unless they are super admins.
6. Super admins can query audit logs.
7. KB service routes remain protected by service-to-service auth.

## Privacy and Analytics

1. Conversation owner identity is protected.
2. Admin analytics shows query text but anonymizes athlete identity.
3. Analytics payloads should use stable anonymous identifiers where grouping is needed.
4. Logs should avoid unnecessary PII and must never include secrets or provider tokens.
5. Stored conversations are used for athlete history, dashboard insights, and anonymized admin analytics.

## Safety Policy

| Category | Behavior |
|----------|----------|
| NIL | Answer only with KB support; otherwise decline |
| Compliance | Answer only with KB support; otherwise decline |
| Recruiting | Decline unless approved KB guidance supports a safe procedural answer |
| FERPA/student records | Decline or provide only approved procedural guidance |
| Medical | Decline medical advice and direct to official support |
| Legal | Decline legal advice and direct to official support |
| Mental health crisis | Refuse advice and show crisis/emergency instructions |
| Emergency | Refuse advice and show emergency instructions |
| Harassment/reporting | Provide approved reporting path only when sourced; otherwise decline |

## Audit Controls

Audited actions:
- KB document upload.
- KB document retry/re-upload.
- KB document metadata update.
- KB document deletion/archive.
- User role change.
- Insight run manual trigger.

Audit entries include actor, action, target type, target ID, timestamp, and metadata. Normal admin UI/API operations must not modify or delete audit entries.

## Theming and Affiliation Controls

1. Product copy must not claim or imply affiliation with a specific university.
2. Code identifiers must not use protected university names as product tenant or entity names.
3. Theming must be configurable for future college rollout.
4. Demo content should use neutral names unless authorized marks are explicitly provided.

## Validation Assertions

1. Unauthenticated user cannot access chat or admin routes.
2. Athlete cannot access admin APIs.
3. Admin cannot change super-admin roles.
4. Super admin role changes create audit records.
5. Admin analytics returns anonymized query owner data.
6. Emergency and unsupported questions refuse safely.
7. OAuth tokens are not logged or returned to frontend API responses.
