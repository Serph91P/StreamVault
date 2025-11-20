# Frontend Development Guide

## 🚀 Quick Start (Frontend-Only Development)

Develop the UI without running the full Docker stack:

```bash
cd app/frontend

# Install dependencies (first time only)
npm install

# Start development server with mock data
npm run dev

# Open browser at http://localhost:5173
```

**Benefits:**
- ⚡ **Instant updates** - Changes visible immediately (Hot Module Replacement)
- 🎨 **All components visible** - Mock data shows streamers, videos, recordings, etc.
- 🐛 **Vue DevTools** - Full debugging support
- 📦 **No Docker** - No container builds needed

---

## 🎭 Mock Data Mode

Mock mode provides realistic test data for all UI components:

### What's Included:

- **4 Streamers** (2 live, 2 offline)
- **3 Videos** with different durations and categories
- **1 Active Recording** 
- **2 Favorite Categories**
- **3 Proxies** (healthy, degraded, failed)
- **Background Queue Tasks**
- **Settings Data**

### Toggle Mock Mode:

**Option 1: Environment Variable (Recommended)**
```bash
# Edit app/frontend/.env.development
VITE_USE_MOCK_DATA=true
```

**Option 2: Runtime Toggle**
```javascript
// In browser console (F12)
localStorage.setItem('useMockData', 'true')
location.reload()
```

### Verify Current Mode:

Check the browser console (F12) on page load:
- `🎭 MOCK MODE ENABLED` - Using mock data
- `🌐 LIVE MODE` - Connecting to backend

---

## 🛠️ Development Scripts

```bash
# Start dev server (default: uses .env.development settings)
npm run dev

# Start with mock data explicitly enabled
VITE_USE_MOCK_DATA=true npm run dev

# Start connected to real backend
VITE_USE_MOCK_DATA=false npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run type-check

# Lint code
npm run lint
```

---

## 📁 Project Structure

```
app/frontend/
├── src/
│   ├── components/          # Reusable Vue components
│   │   ├── cards/          # StreamerCard, VideoCard, StatusCard
│   │   ├── settings/       # Settings panels
│   │   └── ...
│   ├── views/              # Page-level components
│   │   ├── HomeView.vue
│   │   ├── StreamersView.vue
│   │   ├── VideosView.vue
│   │   └── ...
│   ├── services/           # API clients
│   │   ├── api.ts         # Real API implementation
│   │   └── apiProxy.ts    # Mock/Real switcher
│   ├── mocks/              # Mock data for development
│   │   ├── mockData.ts    # Test data
│   │   └── mockApi.ts     # Mock API responses
│   ├── composables/        # Reusable Vue logic
│   ├── styles/             # SCSS design system
│   │   ├── main.scss
│   │   ├── _variables.scss
│   │   ├── _components.scss
│   │   └── ...
│   └── router/             # Vue Router config
├── .env.example            # Environment template
├── .env.development        # Development defaults (with mock mode)
└── vite.config.ts          # Vite configuration
```

---

## 🎨 Testing UI Components

All major components have mock data:

### Dashboard (HomeView)
- **Live Streamers** - Horizontal scroll with 2 live channels
- **Recent Recordings** - Grid of 3 videos
- **Quick Stats** - 4 status cards

### Streamers (StreamersView)
- **Grid/List View** - Toggle between layouts
- **Live/Offline Filters** - Filter by status
- **Search** - Test search functionality
- **StreamerCard** - Hover states, actions menu

### Videos (VideosView)
- **Video Grid** - Multiple videos with thumbnails
- **Search & Filter** - Test filtering
- **VideoCard** - Play button, metadata display

### Settings (SettingsView)
- **All Tabs** - Twitch, Recording, Notifications, Proxies, Favorites, PWA, About
- **Forms** - Input fields, dropdowns, checkboxes
- **Theme Toggle** - Light/Dark mode switching

### Background Jobs (BackgroundQueueMonitor)
- **Active Tasks** - Recording progress
- **Queue Stats** - Pending, running, completed
- **Jobs Panel** - Expandable panel with task details

---

## 🔄 WebSocket Behavior

**Mock Mode:**
- WebSocket connections are **simulated** (no actual connection)
- Updates are triggered by mock events every 30 seconds
- No real-time data from backend

**Live Mode:**
- WebSocket connects to backend at `ws://localhost:8000/ws`
- Real-time updates for recordings, queue tasks, etc.

---

## 🎯 Common Development Tasks

### 1. Test New Component Styling

```bash
# Start dev server with mock data
npm run dev

# Edit component file
# Changes auto-reload in browser
```

### 2. Test Light/Dark Mode

```typescript
// In any Vue component
import { useTheme } from '@/composables/useTheme'

const { theme, toggleTheme } = useTheme()

// Toggle in browser console:
// toggleTheme()
```

### 3. Add New Mock Data

Edit `app/frontend/src/mocks/mockData.ts`:

```typescript
export const mockStreamers = [
  // Add your test streamer here
  {
    id: 5,
    username: 'teststreamer',
    display_name: 'TestStreamer',
    is_live: true,
    // ... other fields
  }
]
```

### 4. Test API Error Handling

Edit `app/frontend/src/mocks/mockApi.ts`:

```typescript
// Simulate API error
streamers: {
  getAll: () => {
    throw new Error('Simulated API error')
  }
}
```

---

## 🐛 Debugging

### Vue DevTools

Install browser extension:
- **Chrome:** [Vue.js devtools](https://chrome.google.com/webstore/detail/vuejs-devtools)
- **Firefox:** [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)

### Browser Console

Enable debug logging:
```bash
# In .env.development
VITE_DEBUG=true
```

Check logs:
```javascript
// F12 → Console
// Look for:
// - API requests/responses
// - WebSocket messages
// - Component lifecycle events
```

### Network Tab

Monitor API calls:
1. Open DevTools (F12)
2. Go to Network tab
3. Reload page
4. See all fetch() requests

---

## 📦 Building for Production

```bash
# Build optimized bundle
npm run build

# Output: app/frontend/dist/
# These files are served by FastAPI in production
```

**Production Notes:**
- Mock data is automatically disabled (`VITE_USE_MOCK_DATA=false`)
- API calls go to same origin (`/api/...`)
- Static assets are optimized and minified

---

## 🔧 Troubleshooting

### Issue: Changes not showing

**Solution:**
- Check browser console for errors
- Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Clear browser cache
- Restart dev server

### Issue: "Cannot find module" error

**Solution:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### Issue: API calls failing in mock mode

**Solution:**
- Verify `.env.development` has `VITE_USE_MOCK_DATA=true`
- Check browser console for "🎭 MOCK MODE ENABLED" message
- Restart dev server after changing `.env` files

### Issue: WebSocket errors

**Solution:**
- In mock mode: Errors are expected (simulated connection)
- In live mode: Ensure backend is running on port 8000

---

## 🚢 Integration with Backend

When you're ready to test with real data:

```bash
# 1. Disable mock mode
# Edit .env.development:
VITE_USE_MOCK_DATA=false

# 2. Start backend
cd ../../  # Back to repo root
docker compose -f docker/docker-compose.yml up -d

# 3. Start frontend (connects to localhost:8000)
cd app/frontend
npm run dev
```

**Backend URLs:**
- Frontend: `http://localhost:5173` (Vite dev server)
- Backend API: `http://localhost:8000/api/`
- WebSocket: `ws://localhost:8000/ws`

---

## 📚 Related Documentation

- [Design System](../../docs/DESIGN_SYSTEM.md) - SCSS utilities, components, patterns
- [Architecture](../../docs/ARCHITECTURE.md) - Backend/frontend communication
- [Copilot Instructions](../../.github/copilot-instructions.md) - AI agent guidelines

---

**Happy Developing! 🎨**
