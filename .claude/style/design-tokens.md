# Design Tokens

> **PLACEHOLDER — replace these tokens with your project's design system.**
> This is a neutral starter palette so the harness has a single source of truth for
> colors, spacing, radius, and typography. When you have a real design source
> (your design tool, brand guide, etc.), update the values below and the matching `@theme`
> block in your Tailwind config, then keep this file in sync.

Tailwind v4 reads tokens from an `@theme` block in your global CSS. Define every
token there; reference it everywhere via Tailwind utility classes
(`bg-primary`, `text-gray-500`, `rounded-lg`). Never hardcode raw hex/px in components.

---

## Tailwind v4 `@theme` block (starter)

```css
/* src/app/globals.css */
@import "tailwindcss";

@theme {
  /* --- Brand / Primary --- */
  --color-primary: #10b981;        /* neutral green — replace with brand */
  --color-primary-dark: #059669;
  --color-primary-light: #34d399;

  /* --- Neutrals / Gray scale --- */
  --color-gray-50:  #fafafa;
  --color-gray-100: #f4f4f5;
  --color-gray-200: #e4e4e7;
  --color-gray-300: #d4d4d8;
  --color-gray-400: #a1a1aa;
  --color-gray-500: #71717a;
  --color-gray-600: #52525b;
  --color-gray-700: #3f3f46;
  --color-gray-800: #27272a;
  --color-gray-900: #18181b;

  /* --- Semantic --- */
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-error:   #dc2626;
  --color-info:    #2563eb;

  /* --- Radius --- */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-2xl: 16px;
  --radius-full: 9999px;

  /* --- Font families --- */
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "JetBrains Mono", "SFMono-Regular", monospace;

  /* --- Shadows --- */
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);
  --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
}
```

---

## Color tokens

| Token | Value (placeholder) | Use |
|-------|--------------------|-----|
| `primary` | `#10b981` | Primary actions, links, active states |
| `primary-dark` | `#059669` | Primary hover/pressed |
| `primary-light` | `#34d399` | Tints, subtle backgrounds |
| `gray-50` → `gray-900` | neutral ramp | Text, borders, surfaces |
| `success` | `#16a34a` | Success states |
| `warning` | `#d97706` | Warnings |
| `error` | `#dc2626` | Errors, destructive actions |
| `info` | `#2563eb` | Informational accents |

**Usage:** `bg-primary`, `text-gray-700`, `border-gray-200`, `text-error`. Opacity via modifier: `bg-primary/10`.

---

## Spacing

Use the default Tailwind spacing scale (4px base). Common values:

| Token | px | Use |
|-------|----|----|
| `p-1` / `gap-1` | 4 | Tight inline spacing |
| `p-2` | 8 | Compact padding |
| `p-3` | 12 | Default control padding |
| `p-4` | 16 | Default card/section padding |
| `p-6` | 24 | Card padding |
| `p-8` | 32 | Spacious sections |

Do not use arbitrary `p-[13px]` — round to the nearest scale token, or add a named token if the value recurs.

---

## Radius

| Token | px | Use |
|-------|----|----|
| `rounded-sm` | 4 | Chips, small tags |
| `rounded-md` | 6 | Inputs, small buttons |
| `rounded-lg` | 8 | Buttons, inputs |
| `rounded-xl` | 12 | Cards |
| `rounded-2xl` | 16 | Modals, large surfaces |
| `rounded-full` | — | Avatars, pills, icon buttons |

---

## Typography

| Element | Tailwind | Notes |
|---------|----------|-------|
| h1 | `text-3xl font-bold` | Page title |
| h2 | `text-2xl font-semibold` | Section title |
| h3 | `text-xl font-semibold` | Subsection |
| h4 | `text-base font-semibold` | Card heading |
| Body | `text-sm` | Default body |
| Subtitle | `text-sm text-gray-500` | Descriptions |
| Caption | `text-xs text-gray-400` | Metadata |
| Form label | `text-xs font-semibold uppercase tracking-wide` | Field labels |

Replace the placeholder font families in `@theme` with your brand fonts (load via `next/font`).

---

## Rules

- **One value = one token.** Before adding a token, grep for an existing one with the same value.
- **No arbitrary values** in components (`text-[13px]`, `bg-[#abc123]`). Add a token instead.
- Keep this file and the Tailwind `@theme` block in sync — they are the single source of truth.
