# Frontend Development Guide

## Quick Start

Develop the UI without running any backend or Docker:

```bash
cd app/frontend
npm install        # first time only
npm run dev:mock   # starts with mock data → http://localhost:5173
```

That's it. All pages work — login is auto-bypassed, mock data populates every view.

## Dev Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server (uses `.env.development` — mock mode by default) |
| `npm run dev:mock` | Start with mock data (explicit, no backend needed) |
| `npm run dev:live` | Start connected to real backend at `localhost:8000` |
| `npm run build` | Production build (type-check + bundle) |
| `npm run preview` | Preview production build locally |
| `npm run type-check` | TypeScript type checking only |
| `npm run lint` | ESLint + auto-fix |

## Mock Mode

When `VITE_USE_MOCK_DATA=true` (default in development):

- **Auth bypassed** — automatically logged in as "demo" user, all routes accessible
- **All API calls return mock data** — no network requests to backend
- **WebSocket disabled** — no connection attempts
- **Status data populated** — dashboard shows realistic streamer/recording status

### What Mock Data Provides

- 4 streamers (2 live, 2 offline, 1 actively recording)
- 12 videos with metadata, durations, categories
- 1 active recording
- 8 categories (with favorites)
- 3 proxies (healthy/degraded/failed)
- Background queue tasks
- Full settings data

### Verify Mock Mode

Browser console on page load shows:
- `🎭 Using MOCK API for all endpoints` — mock mode active
- `🌐 Using REAL API for all endpoints` — live mode (needs backend)

### Toggle at Runtime

```javascript
// Browser console (F12)
localStorage.setItem('useMockData', 'true')
location.reload()
```

## Pages You Can Test

| Page | Route | Mock Data |
|------|-------|-----------|
| Dashboard | `/` | Live streamers, recent recordings, stats |
| Streamers | `/streamers` | Grid/list view, live/offline filters, search |
| Streamer Detail | `/streamers/:id` | Profile, recordings, settings |
| Videos | `/videos` | Video grid, search, multi-select |
| Video Player | `/videos/:id` | Player controls, chapters |
| Settings | `/settings` | All tabs: Twitch, Recording, Notifications, Proxies, Favorites |
| Login | `/auth/login` | Form (any credentials work in mock mode) |
| Admin | `/admin` | Background queue status |

## Project Structure

```
src/
├── components/         # Reusable Vue components
│   ├── cards/         # StreamerCard, VideoCard, GlassCard
│   ├── navigation/    # SidebarNav, BottomNav
│   └── settings/      # Settings panel components
├── views/             # Page-level components
├── composables/       # Reusable logic (useAuth, useWebSocket, useTheme)
├── services/
│   ├── api.ts         # Mock/Real API switcher (single entry point)
│   └── api-real.ts    # Real backend HTTP client
├── mocks/
│   └── mockData.ts    # All mock datasets
├── styles/
│   ├── main.scss              # Import aggregator
│   ├── _variables.scss        # Design tokens (colors, spacing)
│   ├── _glass-system.scss     # Glassmorphism design system
│   └── _utilities.scss        # Utility classes
└── router/            # Vue Router + auth guards
```

### API Architecture

Components import from `services/api.ts` — never directly from `api-real.ts` or mock files.

```
Component → api.ts → (VITE_USE_MOCK_DATA=true)  → inline mock implementations
                   → (VITE_USE_MOCK_DATA=false) → api-real.ts → backend
```

## Connecting to Real Backend

```bash
# Option 1: Use the live script
npm run dev:live

# Option 2: Start full stack
cd ../../
docker compose -f docker/docker-compose.yml up -d
cd app/frontend
npm run dev:live
```

Backend URLs in live mode:
- API: `http://localhost:8000/api/`
- WebSocket: `ws://localhost:8000/ws`
- Frontend: `http://localhost:5173`

## Troubleshooting

**Changes not showing** — Hard refresh `Ctrl+Shift+R`, or restart dev server.

**Module not found** — `rm -rf node_modules && npm install`

**Mock mode not working** — Check console for `🎭` emoji. Restart dev server after `.env` changes.

**Build fails with ENOTEMPTY** — `rm -rf dist/ && npm run build`
