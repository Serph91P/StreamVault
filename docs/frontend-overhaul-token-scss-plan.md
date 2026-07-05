# StreamVault Token and SCSS Consolidation Plan

Date: 2026-07-05
Depends on: `docs/frontend-overhaul-analysis.md` and `docs/frontend-overhaul-product-ux-plan.md`
Frontend path: `app/frontend`

## Source verification

Current source files checked before this plan:

| File | Current role | Token finding |
| --- | --- | --- |
| `app/frontend/src/styles/_variables.scss` | Owns Sass variables and app-wide CSS custom properties | Defines 192 unique CSS custom properties in the current file, including canonical tokens and compatibility names. |
| `app/frontend/src/styles/_glass-system.scss` | Owns glass surface variables, mixins and global glass utility classes | Defines 19 glass-only CSS custom properties and consumes core tokens from `_variables.scss`. |
| `app/frontend/src/styles/main.scss` | Owns imports, reset, document base styles and legacy global element styles | Defines no CSS custom properties. It should consume tokens only. |
| `app/frontend/src/styles/_components.scss` | Owns legacy global component classes | Defines no CSS custom properties. It should consume tokens only until classes move to Vue primitives. |

## Canonical token groups

These names are the canonical names for new implementation work. New UI code should use these names or Sass variables from the same group instead of creating aliases.

### Color

| Purpose | Canonical tokens | Notes |
| --- | --- | --- |
| Brand primary | `--primary-color`, `--primary-color-light`, `--primary-color-dark`, `--primary-color-rgb`, `--primary-bg` | Teal brand system. Use for primary action, focus and recording identity. |
| Accent | `--accent-color`, `--accent-color-hover`, `--accent-color-rgb` | Purple highlights and secondary emphasis. |
| Status success | `--success-color`, `--success-color-dark`, `--success-color-rgb`, `--success-bg`, `--success-border-color`, `--success-text-color` | Successful operations and healthy status. |
| Status danger | `--danger-color`, `--danger-color-dark`, `--danger-color-hover`, `--danger-color-rgb`, `--danger-bg-color`, `--danger-border-color`, `--danger-text-color` | Errors, destructive actions and failed jobs. |
| Status warning | `--warning-color`, `--warning-color-dark`, `--warning-color-rgb`, `--warning-hover` | Warnings, queued work and attention states. |
| Status info | `--info-color`, `--info-color-dark`, `--info-bg-color`, `--info-border-color`, `--info-text-color` | Informational surfaces. |
| Background | `--background-dark`, `--background-darker`, `--background-card`, `--background-primary`, `--background-secondary`, `--background-tertiary` | Page, shell and surface backgrounds. |
| Text | `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-muted`, `--text-on-primary`, `--text-on-warning` | Use semantic text names instead of Vue starter aliases. |
| Border | `--border-color`, `--border-color-rgb`, `--border-color-subtle` | App-wide border system. |
| Twitch brand | `--twitch-purple`, `--twitch-purple-dark`, `--twitch-purple-rgb` | Twitch-specific surfaces only. |

### Typography

| Purpose | Canonical tokens |
| --- | --- |
| Font families | `--font-sans`, `--font-mono` |
| Size scale | `--text-xs`, `--text-sm`, `--text-base`, `--text-lg`, `--text-xl`, `--text-2xl`, `--text-3xl`, `--text-4xl`, `--text-5xl` |
| Weights | `--font-normal`, `--font-medium`, `--font-semibold`, `--font-bold` |
| Line height | `--leading-none`, `--leading-tight`, `--leading-snug`, `--leading-normal`, `--leading-relaxed` |
| Letter spacing | `--tracking-wide` |

### Spacing

| Purpose | Canonical tokens |
| --- | --- |
| Base grid | `--spacing-0`, `--spacing-1`, `--spacing-2`, `--spacing-3`, `--spacing-4`, `--spacing-5`, `--spacing-6`, `--spacing-8`, `--spacing-10`, `--spacing-12`, `--spacing-16` |
| Fine-grained exceptions | `--spacing-0-5`, `--spacing-2-5`, `--spacing-7`, `--spacing-15` |

Prefer the base grid. Fine-grained exceptions are allowed only where the existing UI already needs them.

### Radius

| Purpose | Canonical tokens |
| --- | --- |
| Component radius | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`, `--radius-2xl`, `--radius-full` |
| Legacy bridge | `--border-radius`, `--border-radius-sm`, `--border-radius-lg` |

New UI should use the `--radius-*` family. Keep `--border-radius*` only for current legacy consumers.

### Elevation and focus

| Purpose | Canonical tokens |
| --- | --- |
| Elevation | `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-xl`, `--shadow-2xl` |
| Brand focus | `--shadow-primary` |
| Transitions | `--transition-fast`, `--transition-base`, `--transition-slow`, `--transition-colors`, `--transition-opacity`, `--transition-transform`, `--transition-all` |
| Motion primitives | `--duration-150`, `--duration-200`, `--duration-250`, `--duration-300`, `--duration-400`, `--duration-500`, `--ease-out`, `--ease-in`, `--ease-in-out`, `--ease-bounce` |

### Glass

| Purpose | Canonical tokens |
| --- | --- |
| Surface strength | `--glass-bg-subtle`, `--glass-bg`, `--glass-bg-strong`, `--glass-bg-solid` |
| Border | `--glass-border`, `--glass-border-hover`, `--glass-border-primary`, `--glass-border-primary-hover` |
| Shadow | `--glass-shadow-sm`, `--glass-shadow-md`, `--glass-shadow-lg`, `--glass-shadow-xl` |
| Blur | `--glass-blur-sm`, `--glass-blur-md`, `--glass-blur-lg`, `--glass-blur-xl` |
| Highlight | `--glass-highlight`, `--glass-highlight-strong`, `--glass-glow` |

Glass tokens are owned by `_glass-system.scss`, not `_variables.scss`.

### Status naming

Use `success`, `danger`, `warning` and `info` for the core status palette. For product event severity, map event names into those four display statuses before they reach UI styles.

Recommended event-to-token mapping:

| Event severity | Display token group |
| --- | --- |
| `success` | `--success-*` |
| `error`, `critical`, destructive | `--danger-*` |
| `warning`, delayed, queued | `--warning-*` |
| `info`, neutral, system | `--info-*` |

## Deprecated aliases

These names stay available for compatibility during migration, but new code should not introduce or expand them:

| Deprecated alias group | Use instead |
| --- | --- |
| `--color-primary`, `--color-primary-rgb`, `--highlight-color` | `--primary-color`, `--primary-color-rgb` |
| `--primary-hover`, `--primary-hover-color`, `--primary-color-hover` | `--primary-color-dark` for static states, or component hover styles based on `--primary-color` |
| `--color-accent`, `--color-accent-rgb` | `--accent-color`, `--accent-color-rgb` |
| `--color-success`, `--color-success-rgb` | `--success-color`, `--success-color-rgb` |
| `--error-color`, `--color-error`, `--color-error-hover`, `--color-error-rgb`, `--error-bg` | `--danger-color`, `--danger-color-hover`, `--danger-color-rgb`, `--danger-bg-color` |
| `--color-warning`, `--color-warning-rgb` | `--warning-color`, `--warning-color-rgb` |
| `--text-color`, `--text-muted-color`, `--color-text`, `--color-text-light`, `--color-heading` | `--text-primary`, `--text-muted`, `--text-secondary` |
| `--bg-primary`, `--bg-secondary`, `--input-bg`, `--color-background`, `--color-background-soft`, `--color-background-mute` | `--background-primary`, `--background-secondary`, `--background-card` |
| `--border-radius*` where no legacy consumer requires it | `--radius-*` |
| `--spacing-xs`, `--spacing-sm`, `--spacing-md`, `--spacing-lg`, `--spacing-xl` | Numeric spacing tokens such as `--spacing-2`, `--spacing-3`, `--spacing-4`, `--spacing-6`, `--spacing-8` |
| `--purple-color` | `--twitch-purple` when Twitch-specific, otherwise `--accent-color` |
| `--vue-ease*` | `--ease-*` tokens |

## SCSS ownership decision

| File | Owns | Must not own |
| --- | --- | --- |
| `_variables.scss` | Sass primitives, theme values, canonical app tokens, deprecated compatibility aliases and light-theme overrides | Glass-only mixins, component classes, layout resets |
| `_glass-system.scss` | Glass CSS custom properties, glass mixins, glass utility classes, glass fallback behavior | Non-glass app tokens and generic components |
| `main.scss` | Import order, reset, document base, global element defaults and compatibility bridge styles | New design tokens or new component systems |
| `_components.scss` | Existing legacy global component classes only while migration is in progress | New tokens, new aliases or new product-specific styles |

## Glass usage rules

1. Use glass for shell surfaces, global overlays, cards with status-rich context and transient panels or sheets.
2. Do not use glass for every nested section. Inside a glass surface, prefer solid or transparent child surfaces to avoid stacked blur.
3. Use the mixins and classes from `_glass-system.scss` rather than redefining blur, alpha, border or shadow values in component scoped styles.
4. Interactive glass is allowed for cards and buttons that clearly afford click or tap. Static information groups should use non-interactive surface styles.
5. Respect reduced motion and mobile performance during implementation. Avoid large animated blur areas in long lists.
6. If a component can use a shared primitive such as `GlassCard.vue`, prefer the primitive before adding a new global class.

## Migration rule

New changes must not add CSS custom property aliases. If a new visual value is truly needed, add it first to the canonical group in `_variables.scss` or `_glass-system.scss`, document the intended owner, and update the token lint expectations in the same change.
