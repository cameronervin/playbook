# Handoff: Playbook — Auth, Chat Workspace & Admin Console

## Overview
**Playbook** is an agentic AI platform for college athletic departments (launch partner:
Oklahoma State University — black-and-orange identity). This package documents three
screens so they can be rebuilt in a real codebase:

1. **Login** — SSO-only sign-in (Microsoft + Google).
2. **Home** — post-login chat workspace: conversation history rail, center chat thread,
   grounding-sources panel, and a knowledge-base browser.
3. **Admin** — admin-only console: insights dashboard, knowledge-base management, and
   super-admin users & roles.

Voice: confident, plain-spoken, "coaching staff" calm. Address the user as **"you"**;
the product is **"Playbook"** or **"your agents."** Sentence case everywhere except big
display headlines. **No emoji, anywhere.**

---

## About the design files
The files in `design-reference/` and `source/` are **design references created in HTML** —
prototypes that demonstrate the intended look and behavior. **They are not production code
to copy verbatim.** Your task is to **recreate these designs in the target codebase
(Next.js) using its established patterns and libraries** — real routing, real auth, real
data fetching, a real component tree.

Two representations of the same three screens are included:

- **`design-reference/`** — each screen bundled into a **single self-contained HTML file**
  (all tokens, fonts, JS inlined). Open these in a browser to see exactly how the screen
  looks and behaves. This is the "ground truth" for visual fidelity.
- **`source/`** — the **un-bundled prototype source**: the page HTML plus one file per
  React component. Read these to see how each piece is structured. Note the prototype
  quirks below — they exist only because this ran as in-browser Babel, and should be
  *dropped* in a real build.

### Prototype quirks to discard when porting
- React 18 + Babel-standalone loaded from CDN with integrity hashes → **Next owns React;
  delete all of this.**
- Components are hung off `window` via `Object.assign(window, {...})` and a **mount poller**
  that waits for globals → **replace with real ES `import`/`export`.**
- Design tokens are **inlined into each page's `<style>`** (a workaround for a MIME-type
  issue on the served `.css`) → **move to a single `app/globals.css` imported once.**
- A **Tweaks panel** (`bg`, `motion`, `density`, `role`, etc.) is a *prototyping*
  affordance for exploring options. **It is not part of the product.** Bake the chosen
  defaults in and wire `role` to real auth. (Chosen defaults are listed per-screen below.)
- Canvas background fields can't be captured by DOM-serialization screenshots — this
  caveat is irrelevant once it's a real app; just keep the `prefers-reduced-motion` guard.

---

## Fidelity
**High-fidelity (hifi).** These are pixel-level mockups with final colors, typography,
spacing, radii, and interaction states. Recreate the UI faithfully using the codebase's
component primitives. Exact token values are in the **Design Tokens** section and in
`source/colors_and_type.css`.

---

## Target stack (recommendation)
The user is porting to a **Next.js** application (App Router). Suggested mapping:

| Prototype concern | Next.js target |
|---|---|
| Design tokens (inlined `:root`) | `app/globals.css`, imported in `app/layout.tsx` |
| Fonts in `source/fonts/*.ttf` | `next/font/local` → exposes `--font-display`, `--font-body`, `--font-display-alt` |
| `window`-global components + mount poller | one file per component, real `import`/`export`; `"use client"` on any with state/effects/canvas |
| CDN React + Babel script tags | delete — Next provides React |
| `role` Tweak | real auth/session (RBAC) |
| `bg` / `motion` / `density` Tweaks | a `useSettings` store (Context or DB-backed), or bake the default and drop |
| SSO fake click handlers | NextAuth/Auth.js with Azure AD + Google providers |
| Canned replies / mock data | API routes / server actions / fixtures |

**Decide up front:** TypeScript vs JS (Next defaults to TS — recommended), and whether the
mocked conversation/KB data stays as fixtures initially or wires to a backend immediately.

---

## Design Tokens
Full source: `source/colors_and_type.css`. Inline this `:root` block once in `globals.css`.

### Brand — Playbook Orange (OSU)
`#FF7300` is the **single spotlight accent** — used with restraint (primary action, brand
mark, active/live state, inline answer emphasis). **Never a wash. No blue/purple "AI
gradient."** The info semantic color is **teal**, not blue.

| Token | Hex | Use |
|---|---|---|
| `--orange-500` / `--brand` | `#FF7300` | core brand orange |
| `--brand-hover` (`--orange-400`) | `#FF8224` | hover |
| `--brand-press` (`--orange-600`) | `#E85F00` | pressed |
| `--brand-soft` | `rgba(255,115,0,0.14)` | tinted fills |
| `--brand-glow` | `rgba(255,115,0,0.35)` | focus ring / active glow |
| orange-50…900 | `#FFF3E9 #FFE0C4 #FFC089 #FF9D4D #FF8224 #FF7300 #E85F00 #C24C00 #8F3800 #5E2500` | full ramp |

### Warm charcoal neutrals (slight warm undertone — never cold blue-gray)
| Token | Hex | Role |
|---|---|---|
| `--ink-1000` / `--bg-void` | `#0C0B09` | app shell void |
| `--ink-950` / `--bg-page` | `#100F0C` | page background |
| `--ink-900` / `--bg-base` | `#16140F` | base background |
| `--ink-850` / `--surface` | `#1C1A14` | surface |
| `--ink-800` / `--surface-raised` | `#221F18` | raised surface / cards |
| `--ink-750` / `--surface-hover` | `#2A271E` | hover surface |
| `--ink-700` / `--border-solid` | `#332F25` | strong border |
| `--ink-600` | `#423D30` | divider on raised |
| `--ink-500` | `#5A5343` | faint / disabled text |
| `--ink-400` | `#7E7665` | muted text |
| `--ink-300` | `#A89E8B` | secondary text |
| `--ink-200` | `#CFC6B5` | high secondary |
| `--ink-100` | `#E9E2D5` | near-white warm |
| `--ink-050` | `#F6F1E8` | warm white |

### Foreground (text on dark)
`--fg-1 #F6F1E8` (primary) · `--fg-2 #C2B9A8` (secondary) · `--fg-3 #8E8674` (muted/captions)
· `--fg-4 #5A5343` (faint/placeholder) · `--fg-on-brand #16140F` (text on orange fills).

### Borders
`--border rgba(246,241,232,0.08)` · `--border-strong rgba(246,241,232,0.14)`
· `--border-solid #332F25` · `--border-brand rgba(255,115,0,0.45)`.
**Borders do the structural work on dark UI, not shadows.**

### Semantic
| | Color | Bg |
|---|---|---|
| success | `#3FB68B` | `rgba(63,182,139,0.14)` |
| warning | `#F4A93C` | `rgba(244,169,60,0.14)` |
| danger | `#F0563F` | `rgba(240,86,63,0.14)` |
| info (teal) | `#4FB6C7` | `rgba(79,182,199,0.14)` |

Agent status accents: thinking = info teal, active = brand orange, done = success green.

### Typography
- **`--font-display` = Archivo** — headlines/display/eyebrows. **UPPERCASE only for big
  display headlines.** Weights: black 900 (display), extrabold 800 (h1), bold 700 (h2/h3).
- **`--font-display-alt` = Sora** — alternate geometric display.
- **`--font-body` = Inter** — body + all UI labels.
- **`--font-mono` is repointed to Inter in the app UI.** In the original design-system CSS
  `--font-mono` is JetBrains Mono, but **the product deliberately repoints it to Inter** —
  filenames, IDs, counts, and keyboard hints render in Inter. A true mono "machine voice"
  reads as a generic AI-product tell and is avoided. (The bundled Home/Admin pages already
  set `--font-mono: 'Inter'`.) Keep mono *only* if you have genuine log/latency output.

Type scale (rem on 16px base): `2xs .6875` · `xs .75` · `sm .875` · `base 1` · `md 1.125`
· `lg 1.375` · `xl 1.75` · `2xl 2.25` · `3xl 3` · `4xl 4` · `5xl 5.5`.
Weights: 400/500/600/700/800/900. Tracking: tight `-0.02em`, snug `-0.01em`, normal `0`,
wide `0.04em`, caps `0.12em`.

Semantic type classes (defined in `colors_and_type.css`): `.pb-eyebrow .pb-display .pb-h1
.pb-h2 .pb-h3 .pb-h4 .pb-lead .pb-body .pb-small .pb-label .pb-mono .pb-meta .pb-token`.
**Eyebrows are sentence-case bold orange Inter — NOT uppercase-letterspaced mono** (that
reads as AI-generated and is explicitly avoided).

### Spacing (4px base)
`space-1 4` · `2 8` · `3 12` · `4 16` · `5 24` · `6 32` · `7 48` · `8 64` · `9 96` (px).

### Radii (sharp / tight)
`xs 3` · `sm 5` · **`md 8` (default control radius)** · **`lg 12` (cards)** · `xl 16`
· `pill 999` (px). Controls 8px, cards 12px.

### Elevation & motion
Shadows: `sm 0 1px 2px rgba(0,0,0,.4)` · `md 0 4px 16px rgba(0,0,0,.45)` ·
`lg 0 16px 48px rgba(0,0,0,.55)` · `focus 0 0 0 3px var(--brand-glow)`.
Easing: `--ease-out cubic-bezier(.2,.7,.2,1)` · `--ease-in-out cubic-bezier(.4,0,.2,1)`.
Durations: `fast 120ms` · `med 200ms` · `slow 360ms`. **Honor `prefers-reduced-motion`
everywhere** — every animation in the prototype already has a reduce guard.

---

## Shared concept: animated background fields
A reusable ambient background, low-contrast and behind content, with selectable fields.
Used full-screen on **Login** and as a faint layer behind the chat thread on **Home**.

Fields: **`horizon`** (default — a waving perspective grid drawn on `<canvas>`),
**`aurora`** (drifting warm CSS blooms + dot grid), **`ember`** (rising particles on
`<canvas>`), **`grid`** (static hairline CSS grid), **`plain`** (none).
- The two canvas fields (`HorizonGrid`, `Ember`) live in `source/Login.html` (and
  `source/home/BgFields.jsx`). Port the `useEffect` render loop as-is into a `"use client"`
  component; **keep the `prefers-reduced-motion` early-out** (it freezes to a single
  static frame).
- **Default field is `horizon`, motion on.** Keep it ambient — never high-contrast.

---

## Screen 1 — Login (`design-reference/Login.html`, `source/Login.html`)

### Purpose
Sign in via SSO. **Locked decision: SSO only — Microsoft + Google. No email/password
field, ever.**

### Layout
Full-viewport dark stage (`--bg-page`) with the animated background field behind a warm
vignette. A single **rectangular card**, centered, `max-width: 380px`,
`background: --surface-raised`, `1px solid --border-strong`, `radius-lg (12px)`,
`shadow-lg`, padding `64px 32px 24px`. The card rises in on mount (`translateY(8px)` →
0, 200ms ease-out). **Everything lives inside the card**, vertically stacked & centered:

1. **Brand lockup** — the Playbook `Mark` (34px) + wordmark "Playbook" (Archivo extrabold
   26px, `--track-tight`), gap 11px.
2. **Heading** — "Log in to continue" (18px). (An optional eyebrow "Agentic AI for
   athletics" in orange sits above it but is **off by default**.)
3. **SSO buttons** — stacked, gap 12px, full width. **Microsoft first, then Google.**
4. **Footer** — divider (`1px --border`), then legal links "Privacy Policy · Terms of
   Service" (`--fg-3`, 12px, hover `--fg-1`).

### SSO buttons — **tile style** (the chosen default)
Provider brand logo boxed on the left, label centered in the remainder:
- Container: `--surface` fill, `1px solid --border-strong`, `radius-md (8px)`,
  full width. Hover → `--surface-hover`. Active → `translateY(1px)`.
  Focus-visible → `box-shadow: --shadow-focus` + `border-color: --border-brand`.
- Left glyph box: `50×50px`, `border-right: 1px solid --border`,
  `background: --surface-raised`, `radius-md 0 0 radius-md`.
- Label: `flex:1`, centered, Inter semibold 16px, `padding: 15px 50px 15px 0`
  (the right 50px pad balances the left glyph box so text is optically centered).
- Copy: **"Continue with Microsoft"** / **"Continue with Google"**.
- **Provider brand logos are the one allowed multicolor exception** — use the official
  4-square Microsoft logo and 4-color Google "G" (SVGs are in `source/Login.html`:
  `MicrosoftLogo`, `GoogleLogo`). Microsoft `19×19`, Google `20×20`.

### Behavior
- Click Microsoft → `signIn('azure-ad')`; click Google → `signIn('google')`
  (prototype handlers are stubs).
- Default background field `horizon`, motion on.
- Optional extras (all **off** by default, were Tweaks): centered (non-tile) button style,
  Google-first order, eyebrow, a "Can't log in?" support link, a "All systems
  operational · SSO via SAML 2.0" status line. Ship without these unless asked.

### Baked defaults (drop the Tweak controls)
`buttonStyle: tile`, `buttonOrder: ms` (Microsoft first), `headline: display`,
`eyebrow: false`, `bg: horizon`, motion on, `support: false`, `sysline: false`.

---

## Screen 2 — Home / Chat workspace (`design-reference/Home.html`, `source/home/*`)

### Purpose
The post-login workspace. Chat-first: ask Playbook a question, get an answer **grounded in
the department's documents** with citations. Also a place to browse the knowledge base.

### Layout — three columns inside a full-height flex row (`--bg-base`)
1. **NavRail** (left, `source/home/NavRail.jsx`) — fixed-width rail:
   brand lockup, **New chat** action (⌘/Ctrl+N), a **searchable conversation history**
   list grouped by "Today / Yesterday / Previous 7 days", a Knowledge-base entry, and an
   **account block at the foot** that opens a **ProfileMenu** → **SettingsModal**.
   Conversations support rename and delete (inline).
2. **Center column** — the chat surface, with the ambient `BgField` faint behind it
   (`source/home/BgFields.jsx`):
   - **TopBar** (`TopBar.jsx`) — shown once a conversation has messages: conversation
     title (rename/delete menu), the active knowledge scope, and a toggle for the sources
     panel.
   - **ChatThread** (`ChatThread.jsx`) — user + agent messages, max content width
     760px (680px in compact density), gap 24px (16px compact). Agent answers render
     inline emphasis in **orange `<b>`** and show "checked N sources · 1.8s" metadata
     plus inline **citation chips** that open the sources panel. Includes **thinking**
     (pulsing mark + "Thinking…") and **streaming** (blinking caret) states.
   - **Composer** (`Composer.jsx`) — the input. Enter-to-send (configurable).
   - **Empty state** is fixed: **"Ask PlaybookAI"** + a tagline. **Never topic-specific.**
3. **SourcesPanel** (right, `SourcesPanel.jsx`) — grounding sources for the current scope,
   with the cited document highlighted. Toggleable; open by default.

### Knowledge base view (in `source/home/app.jsx`: `KnowledgeView` / `KnowledgeDetail`)
Replaces the center+right area when entered from the rail.
- **Grid of KB cards** (`repeat(auto-fill, minmax(280px,1fr))`, gap 16). Each card: icon
  tile in `--brand-soft`, KB name (Archivo bold), blurb, and a footer reading
  **"N sources · updated X"** (no "answered" count). Hover raises the surface and turns
  the border + chevron orange.
- **Clicking a card opens that KB's document list** (`KnowledgeDetail`) — it does **not**
  start a scoped chat. Document rows show a file-type icon, filename (Inter), meta, and an
  uppercase extension chip.

### Role model (RBAC — replaces the `role` Tweak)
Two roles: **Super admin** vs **Department admin** (default Super admin in the prototype).
**Only super admins** see: **New knowledge base**, **Add document**, and the document
**delete** control. Department admins get a read-only knowledge base.

### State (prototype `useState` — map to real data layer)
`conversations[]` (id, title, topicId, group, messages[]), `topics[]` (KB areas with
docs[]), `activeId`, `view` (`chat` | `knowledge`), `sourcesOpen`, `highlight` (cited
file), `settingsSection`, `profile`, `prefs`, `notify`. Sending a message appends a user
msg + an agent "thinking" placeholder, then (after ~850ms) swaps in the streamed answer
and surfaces its first citation. **All replies and KB data are canned fixtures** — replace
with real retrieval/RAG + streaming.

### SettingsModal (`source/home/SettingsModal.jsx`)
Opened from the profile menu. **MVP scope: Profile + Security & SSO only.** (Appearance /
density live only in the prototype Tweaks — fold into a real settings store or omit.)

### Baked defaults
`bg: horizon`, motion on, `density: Comfortable`, `sourcesDefault: true`,
`role: Super admin`.

### Component inventory (`source/home/`)
`NavRail`, `ProfileMenu`, `SettingsModal`, `BgFields` (exports the field components),
`TopBar`, `ChatThread`, `Composer`, `SourcesPanel`; `KnowledgeView` / `KnowledgeDetail` /
`KnowledgeCard` / `DocRow` live in `app.jsx`. Shared primitives in `source/ui.jsx`
(`PBButton`, `IconBtn`, `Card`, etc.) and `source/Icon.jsx` (icon set). **All interactive
→ `"use client"` in Next.**

---

## Screen 3 — Admin console (`design-reference/Admin.html`, `source/admin/*`)

### Purpose
Admin-only surface. **The athlete role is hard-gated out** — athletes see an "Admins only"
access-denied screen (`AccessDenied` in `app.jsx`). Three routes:

1. **Insights** (`Dashboard.jsx`, default route) — analytics dashboard: KPI summary cards
   + an **AI-generated summary** with a time-window selector (7d / 30d / custom) and a
   **Generate** action that shows a ~2.2s processing state. An **analytics chat** panel
   (`AdminChat.jsx`) can be opened to ask questions about the data.
2. **Knowledge base** (`KBManage.jsx`) — manage collections and documents: upload
   (shows processing → ready), retry failed ingests, delete, toggle "official", edit
   metadata, create collections. Document **status** states: `processing` / `ready` /
   `failed` (with reason). The nav badges the count of failed docs.
3. **Users & roles** (`UsersAudit.jsx`) — **super-admin only**. Change a user's role.
   If the viewer's role drops below super admin while on this route, it redirects to
   Insights.

### Layout
Full-height flex row (`--bg-base`): **AdminNav** (left) + main route content, with
**AdminChat** as a right-side panel and a faint technical grid (`.admin-grid`) seated
behind page headers. Same NavRail/account/SettingsModal pattern as Home.

### Role model
`Athlete` (denied) / `Department admin` / `Super admin` (default). Super-admin-only:
the Users route, plus KB management actions (upload/retry/delete/official/metadata/create).
Replace the `role` Tweak with real RBAC.

### Cross-screen navigation (prototype uses `window.location`)
Rail "chat workspace" → `Home.html`; Home "knowledge"/admin entry → `Admin.html`;
sign-out everywhere → `Login.html`. **In Next, these become real routes/links**, e.g.
`/login`, `/` (or `/chat`), `/admin` — and sign-out via the auth provider.

### Baked defaults
`role: Super admin`, `chatDefault: false` (analytics chat closed by default).

### Component inventory (`source/admin/`)
`AdminNav`, `Dashboard`, `KBManage`, `UsersAudit`, `AdminChat`, `SettingsModal`,
`widgets.jsx` (dashboard widgets/cards), `data.jsx` (all mock data: `ADMIN_SUMMARY`,
`ADMIN_INSIGHT`, `ADMIN_DOCS`, `ADMIN_KB_COLLECTIONS`, `ADMIN_USERS`). `app.jsx` holds the
route shell + `AccessDenied`. **All mock data → real API.**

---

## Interactions & behavior (summary)
- **Hover**: surfaces step up one neutral (`--surface` → `--surface-hover` /
  `--surface-raised`), borders strengthen, accent affordances turn orange. ~120ms.
- **Focus-visible**: `--shadow-focus` ring (`0 0 0 3px brand-glow`) + `--border-brand`.
- **Active/press**: subtle `translateY(1px)`.
- **Agent states**: `thinking` (pulsing mark + "Thinking…"), `streaming` (blinking orange
  caret appended to text), `live/active` (orange pulse ring).
- **Overlays**: menus rise+fade in (`translateY(6px)`→0), modals rise+scale
  (`translateY(10px) scale(.99)`→0), side panels slide from the right.
- **Keyboard**: ⌘/Ctrl+N → new chat (Home).
- **Reduced motion**: all of the above collapse to static end-states.

---

## Assets
- **Fonts** (`source/fonts/`, variable TTFs): `Archivo-Variable.ttf`,
  `Archivo-Italic-Variable.ttf`, `Inter-Variable.ttf`, `Sora-Variable.ttf`. Load via
  `next/font/local`. (JetBrains Mono is referenced by the design-system CSS but **not used
  in the product UI** — `--font-mono` is repointed to Inter; you can skip it.)
- **Brand mark**: `source/logo-mark.svg`, and an inline `Mark` React component (3-path SVG,
  warm-white body + two orange accent strokes) defined in `source/Login.html`. The
  CLAUDE.md convention is to **define the Mark inline** rather than depend on icon load
  order — keep it as a small shared component.
- **Favicon**: `source/favicon.svg`.
- **Provider logos**: official Microsoft (4 squares) and Google (4-color G) SVGs, inline in
  `source/Login.html`. These are the only sanctioned multicolor elements.
- **Icon set**: `source/Icon.jsx` (line icons referenced by `name`, e.g. `shield`, `plane`,
  `ticket`, `book-open`, `database`, `users`, `file-text`, `chevron-right`, `arrow-left`,
  `trash`, `lock`, `message-circle`, `plus`, `x`).
- No raster imagery, photos, or third-party logos beyond the two SSO providers.

---

## Files in this package
```
design_handoff_playbook/
├── README.md                     ← you are here
├── design-reference/             ← self-contained bundles (open in a browser = ground truth)
│   ├── Login.html
│   ├── Home.html
│   └── Admin.html
└── source/                       ← un-bundled prototype source (read per-component)
    ├── Login.html                ← page shell + Mark + provider logos + canvas fields + App
    ├── Home.html                 ← page shell (tokens inlined, script load order)
    ├── Admin.html                ← page shell
    ├── colors_and_type.css       ← canonical design tokens + semantic type classes
    ├── Icon.jsx                  ← icon set
    ├── ui.jsx                    ← shared primitives (PBButton, IconBtn, Card, …)
    ├── tweaks-panel.jsx          ← prototyping-only; DO NOT ship
    ├── favicon.svg, logo-mark.svg
    ├── fonts/                    ← Archivo, Inter, Sora variable TTFs
    ├── home/                     ← NavRail, ProfileMenu, SettingsModal, BgFields, TopBar,
    │                               ChatThread, Composer, SourcesPanel, app.jsx
    └── admin/                    ← AdminNav, Dashboard, KBManage, UsersAudit, AdminChat,
                                    SettingsModal, widgets.jsx, data.jsx, app.jsx
```

### Suggested porting order
1. **Tokens + fonts + globals** — `colors_and_type.css` → `globals.css`, fonts via
   `next/font/local`. Gets you visual parity instantly.
2. **Login** — smallest screen; proves the card/button system + auth wiring (Auth.js).
3. **Home** — lift `home/*` components one at a time, adding `"use client"` where needed;
   start with mock fixtures, then wire real retrieval + streaming.
4. **Admin** — lift `admin/*`; wire RBAC and real analytics/KB data; replace
   `window.location` jumps with Next routes.
