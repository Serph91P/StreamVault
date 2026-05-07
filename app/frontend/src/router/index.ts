import { createRouter, createWebHistory } from 'vue-router';

// PERFORMANCE FIX: Implement lazy loading for all routes
const HomeView = () => import('../views/HomeView.vue');
const SubscriptionsView = () => import('../views/SubscriptionsView.vue');
const AddStreamerView = () => import('../views/AddStreamerView.vue');
const OnboardingWizardView = () => import('../views/OnboardingWizardView.vue');
const LoginView = () => import('../views/LoginView.vue');
const AdminView = () => import('../views/AdminView.vue');
const SettingsView = () => import('../views/SettingsView.vue');
const StreamerDetailView = () => import('../views/StreamerDetailView.vue');
const StreamersView = () => import('../views/StreamersView.vue');
const VideoPlayerView = () => import('../views/VideoPlayerView.vue');
const VideosView = () => import('../views/VideosView.vue');

// Disable browser's native scroll restoration so we control scroll manually
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual'
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior() {
    return { top: 0, left: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/welcome',
      name: 'welcome',
      component: OnboardingWizardView,
    },
    {
      path: '/streamers',
      name: 'streamers',
      component: StreamersView,
    },
    {
      path: '/videos',
      name: 'videos',
      component: VideosView,
    },
    {
      path: '/videos/:id',
      name: 'video-player',
      component: () => import('../views/VideoPlayerView.vue'),
      props: true
    },
    {
      path: '/subscriptions',
      name: 'subscriptions',
      component: SubscriptionsView,
    },
    {
      path: '/add-streamer',
      name: 'add-streamer',
      component: AddStreamerView,
    },
    {
      path: '/add-streamer/manual',
      name: 'add-streamer-manual',
      component: AddStreamerView,
    },
    {
      path: '/add-streamer/import',
      name: 'add-streamer-import',
      component: AddStreamerView,
    },
    {
      path: '/auth/setup',
      name: 'setup',
      component: OnboardingWizardView,
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: OnboardingWizardView,
    },
    {
      path: '/auth/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: "/admin",
      name: "Admin",
      component: AdminView,
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    },
    {
      path: '/streamers/:id',  // FIXED: Changed from /streamer to /streamers (plural) to match navigation
      name: 'streamer-detail',
      component: StreamerDetailView
    },
    {
      path: '/streamer/:streamerId/stream/:streamId/watch',
      name: 'VideoPlayer',
      component: VideoPlayerView
    },
  ],
});

// Route everything through the OnboardingWizardView until both setup and
// the welcome step have been completed (server-side flag).
router.beforeEach(async (to, from, next) => {
  // 🎭 MOCK MODE: Bypass auth checks in development
  const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';
  if (USE_MOCK_DATA) {
    console.log('🎭 Mock mode: Skipping auth checks, allowing all routes');
    return next();
  }

  try {
    const response = await fetch('/auth/setup', {
      credentials: 'include', // Required for session cookies
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    // FIXED: Add error handling for invalid JSON responses
    let data;
    try {
      data = await response.json();
    } catch (jsonError) {
      console.error('Failed to parse setup response as JSON:', jsonError);
      // Avoid infinite loop: only redirect if not already heading to onboarding/login
      if (
        to.path !== '/auth/setup' &&
        to.path !== '/auth/login' &&
        to.path !== '/welcome' &&
        to.path !== '/onboarding'
      ) {
        return next('/auth/login');
      }
      return next();
    }

    // Server-persisted onboarding flag replaces the old localStorage `welcome_seen`
    // so the welcome screen no longer reappears on every new device or after
    // clearing browser storage.
    const welcomeCompleted = Boolean(data.welcome_completed);

    // Treat the wizard routes as one logical group. The wizard component
    // figures out which step to show based on `setup_required` itself.
    const isWizardRoute =
      to.path === '/auth/setup' || to.path === '/welcome' || to.path === '/onboarding';

    if (data.setup_required) {
      if (!isWizardRoute) {
        return next('/auth/setup');
      }
      return next();
    }

    // Setup is done; gate other routes on the persisted welcome flag.
    if (to.path === '/' && !welcomeCompleted) {
      return next('/welcome');
    }
    if (isWizardRoute && welcomeCompleted) {
      return next('/');
    }
    if (isWizardRoute) {
      // Wizard handles its own internal routing once setup is done.
      return next();
    }

    const authResponse = await fetch('/auth/check', {
      credentials: 'include', // CRITICAL: Required to send session cookie
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    // Check both HTTP status AND response body for authentication
    if (!authResponse.ok) {
      if (to.path !== '/auth/login') {
        return next('/auth/login');
      }
      return next();
    }

    // Parse response body to check authenticated status
    let authData;
    try {
      authData = await authResponse.json();
    } catch (jsonError) {
      console.error('Failed to parse auth response as JSON:', jsonError);
      if (to.path !== '/auth/login') {
        return next('/auth/login');
      }
      return next();
    }

    // If not authenticated, redirect to login (unless already there)
    if (!authData.authenticated && to.path !== '/auth/login') {
      return next('/auth/login');
    }

    // If authenticated but trying to access login page, redirect to home
    if (authData.authenticated && to.path === '/auth/login') {
      return next('/');
    }

    return next();
  } catch (error) {
    console.error('Router error:', error);
    // Avoid infinite loop: only redirect if not already on an auth page
    if (to.path !== '/auth/setup' && to.path !== '/auth/login') {
      return next('/auth/login');
    }
    return next();
  }
});

// Scroll to top after every navigation
router.afterEach(() => {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
})

export default router;
