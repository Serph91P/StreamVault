# UX-04 shell, session and onboarding parity

## Primary destinations

| Existing route/action | UX-04 destination | Evidence |
| --- | --- | --- |
| `/` | Overview | `useNavigation.shell.spec.ts` |
| `/streamers`, `/streamers/:id`, add/import routes | Streamers | existing routes retained; `router/index.ts` |
| `/videos`, video and legacy stream player deep links | Library | existing routes retained; `router/index.ts` |
| `/admin` | System entry for existing diagnostics and administration | `useNavigation.shell.spec.ts` |
| `/settings`, `/admin`, `/subscriptions` | direct URLs retained; system content migration remains UX-07 scope | router |

## Session and setup states

| State | Behaviour | Evidence |
| --- | --- | --- |
| 401 on a protected route | sends only an internal `returnTo` query to login | `session.spec.ts` |
| Unsafe/external/recursive return target | falls back to `/` | `session.spec.ts` |
| 403 or unavailable guard response | does not claim session expiry or loop through login | router guard and `useAuth.ts` |
| API 401 | existing shared ApiClient refreshes safe requests once; mutations are never replayed | `api-real.auth-refresh.spec.ts` |
| Required setup | remains under existing `/auth/setup` wizard route | router and `OnboardingWizardView.vue` |
| Optional first streamer | separate, skippable wizard step | `OnboardingWizardView.vue` |
| Twitch connection | omitted from normal onboarding; existing settings route remains its destination | `OnboardingWizardView.vue` |

## Shared controls

`BaseDropdown` restores a native theme-aware selection indicator; `BaseButton` preserves its outline border after the global reset; `ThemeToggle` uses the shared 48px labelled icon-button primitive. Existing modal/sheet ownership and realtime singleton usage are retained.

## Residual gates

This local package does not assert physical Android/iOS, Firefox/WebKit, installed-PWA or a real backend/CSRF/provider run. Full Chromium screenshot/capture packaging and final independent review remain required before acceptance.
