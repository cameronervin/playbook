# Epic 1: Authentication, Roles, and Seamless Entry

## Epic Goal

Make Playbook feel effortless from the first visit: users sign in with familiar identity providers, new athletes reach chat quickly, and admins can promote operators without separate credential workflows.

### US-01
As an athlete
I want to sign in with Google or Microsoft
So that I can access Playbook without creating another password.

> **New in Playbook MVP.** Requested by product owner for a low-friction prototype.

#### Acceptance Criteria
1. A user can start Google OAuth/OIDC sign-in from the login screen.
2. A user can start Microsoft OAuth/OIDC sign-in from the login screen.
3. Successful sign-in creates or updates a local user record with email, name, provider, and provider subject.
4. Failed sign-in returns a clear error without creating a partial session.
5. No paid third-party auth vendor is required for the MVP implementation.

### US-02
As a new athlete
I want to self-register and land directly in chat
So that I can ask a question without onboarding friction.

> **New in Playbook MVP.** Day-one success depends on a seamless first experience.

#### Acceptance Criteria
1. A first-time authenticated user can select the athlete role during signup.
2. The signup flow collects name, email, and sport/team.
3. After profile creation, the athlete lands directly on the chat screen.
4. Returning athletes skip signup and land directly on the chat screen.
5. Missing required profile fields block entry with inline validation.

### US-03
As a super admin
I want to promote signed-in users into admin roles
So that athletic department operators can manage Playbook without a separate login system.

> **New in Playbook MVP.** Admin users also sign in through Google/Microsoft and are promoted by a super admin.

#### Acceptance Criteria
1. A super admin can view registered users.
2. A super admin can assign `admin` or `super_admin` roles.
3. Role changes take effect on the user's next authorized request or session refresh.
4. Role changes are recorded in the audit log with actor, target user, previous role, new role, and timestamp.
5. The role model supports future role values without schema redesign.

### US-04
As an admin
I want role-based access controls
So that athlete, admin, and super-admin capabilities remain separated.

> **New in Playbook MVP.** Role-based answer and admin access are critical.

#### Acceptance Criteria
1. Athletes cannot access admin routes or admin API endpoints.
2. Admins can manage documents and view analytics but cannot promote super admins unless granted that role.
3. Super admins can manage users and roles.
4. Unauthorized API access returns 403 with a structured error.
5. Route guards and API authorization are covered by automated tests.

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| OAuth provider is unavailable | User sees retryable sign-in error |
| Existing user signs in with second provider using same email | Account link is blocked or requires explicit confirmed linking |
| User selects athlete but later needs admin access | Super admin promotes user through role management |
| Athlete attempts admin URL | Route guard blocks access and API returns 403 |
