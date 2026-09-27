import { createRouter, createWebHistory } from 'vue-router'
import { loginLocationFor } from '@/services/session'

const HomeView = () => import('../views/HomeView.vue')
const SubscriptionsView = () => import('../views/SubscriptionsView.vue')
const AddStreamerView = () => import('../views/AddStreamerView.vue')
const OnboardingWizardView = () => import('../views/OnboardingWizardView.vue')
const LoginView = () => import('../views/LoginView.vue')
const AdminView = () => import('../views/AdminView.vue')
const SettingsView = () => import('../views/SettingsView.vue')
const SystemHubView = () => import('../views/SystemHubView.vue')
const StreamerDetailView = () => import('../views/StreamerDetailView.vue')
const StreamersView = () => import('../views/StreamersView.vue')
const VideoPlayerView = () => import('../views/VideoPlayerView.vue')
const VideosView = () => import('../views/VideosView.vue')
const LivePlayerView = () => import('../views/LivePlayerView.vue')


if ('scrollRestoration' in history) history.scrollRestoration = 'manual'

const SETUP_PATH = '/auth/setup'
const WELCOME_PATHS = new Set(['/welcome', '/onboarding'])
const WIZARD_PATHS = new Set([SETUP_PATH, ...WELCOME_PATHS])
const PUBLIC_PATHS = new Set(['/auth/login', SETUP_PATH])

async function responseJson(response: Response): Promise<Record<string, unknown> | null> {
  try {
    return await response.json() as Record<string, unknown>
  } catch {
    return null
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0, left: 0 }),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/welcome', name: 'welcome', component: OnboardingWizardView },
    { path: '/streamers', name: 'streamers', component: StreamersView },
    { path: '/videos', name: 'videos', component: VideosView },
    { path: '/videos/:id', name: 'video-player', component: VideoPlayerView, props: true },
    { path: '/subscriptions', name: 'subscriptions', component: SubscriptionsView },
    { path: '/add-streamer', name: 'add-streamer', component: AddStreamerView },
    { path: '/add-streamer/manual', name: 'add-streamer-manual', component: AddStreamerView },
    { path: '/add-streamer/import', name: 'add-streamer-import', component: AddStreamerView },
    { path: '/auth/setup', name: 'setup', component: OnboardingWizardView },
    { path: '/onboarding', name: 'onboarding', component: OnboardingWizardView },
    { path: '/auth/login', name: 'login', component: LoginView },
    { path: '/system', name: 'system', component: SystemHubView },
    { path: '/admin', name: 'Admin', component: AdminView },
    { path: '/settings', name: 'settings', component: SettingsView },

    { path: '/streamers/:id', name: 'streamer-detail', component: StreamerDetailView },
    { path: '/streamer/:streamerId/stream/:streamId/watch', name: 'VideoPlayer', component: VideoPlayerView },
    { path: '/live/:streamer', name: 'live-player', component: LivePlayerView },
  ],
})

/**
 * The guard owns route decisions only. It neither refreshes credentials nor
 * retries mutations: ApiClient retains that bounded, safe-request-only policy.
 */
router.beforeEach(async (to) => {
  if (import.meta.env.VITE_USE_MOCK_DATA === 'true') return true

  let setup: Record<string, unknown> | null = null
  try {
    const response = await fetch('/auth/setup', {
      credentials: 'include',
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    })
    if (response.ok) setup = await responseJson(response)
    else if (response.status === 401 && !PUBLIC_PATHS.has(to.path)) return loginLocationFor(to.fullPath)
    else if (!PUBLIC_PATHS.has(to.path)) return true // Let the route show its own unavailable/denied state.
  } catch {
    return true // Offline is not evidence of a terminated session.
  }

  if (setup?.setup_required === true) {
    return WIZARD_PATHS.has(to.path) ? true : '/auth/setup'
  }

  // The server owns the welcome-completion flag. Preserve the established
  // root gate so a failed or incomplete onboarding flow cannot open Overview.
  if (to.path === '/' && setup?.welcome_completed === false) {
    return '/welcome'
  }

  if (to.path === SETUP_PATH) {
    if (setup?.setup_required === true) return true
    return setup?.welcome_completed === false ? '/welcome' : '/'
  }

  if (WELCOME_PATHS.has(to.path) && setup?.welcome_completed === true) {
    return '/'
  }

  if (to.path === '/auth/login') {
    try {
      const response = await fetch('/auth/check', { credentials: 'include', headers: { Accept: 'application/json' } })
      const auth = response.ok ? await responseJson(response) : null
      return auth?.authenticated === true ? '/' : true
    } catch {
      return true
    }
  }

  try {
    const response = await fetch('/auth/check', { credentials: 'include', headers: { Accept: 'application/json' } })
    if (response.status === 401) return loginLocationFor(to.fullPath)
    if (!response.ok) return true // Preserve 403 and unavailable states for their route-level UI.
    const auth = await responseJson(response)
    return auth?.authenticated === true ? true : loginLocationFor(to.fullPath)
  } catch {
    return true
  }
})

router.afterEach(() => {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
})

export default router
