import { createRouter, createWebHistory } from 'vue-router';

// PERFORMANCE FIX: Implement lazy loading for all routes
const HomeView = () => import('../views/HomeView.vue');
const SubscriptionsView = () => import('../views/SubscriptionsView.vue');
const AddStreamerView = () => import('../views/AddStreamerView.vue');
const SetupView = () => import('../views/SetupView.vue');
const LoginView = () => import('../views/LoginView.vue');
const AdminView = () => import('../views/AdminView.vue');
const SettingsView = () => import('../views/SettingsView.vue');
const StreamerDetailView = () => import('../views/StreamerDetailView.vue');
const WelcomeView = () => import('../views/WelcomeView.vue');
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
      component: WelcomeView,
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
      path: '/auth/setup',
      name: 'setup',
      component: SetupView,
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

// Show WelcomeView only if not seen yet
router.beforeEach(async (to, from, next) => {
  // 🎭 MOCK MODE: Bypass auth checks in development
  const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';
  if (USE_MOCK_DATA) {
    console.log('🎭 Mock mode: Skipping auth checks, allowing all routes');
    // Mark welcome as seen to avoid redirect loop
    if (!localStorage.getItem('welcome_seen')) {
      localStorage.setItem('welcome_seen', 'true');
    }
    return next();
  }

  // Show WelcomeView only if not seen yet and not coming from setup
  if (to.path === '/' && !localStorage.getItem('welcome_seen')) {
    return next('/welcome');
  }
  // Prevent direct access to /welcome after first visit
  if (to.path === '/welcome' && localStorage.getItem('welcome_seen')) {
    return next('/');
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
      // Avoid infinite loop: only redirect if not already heading to setup/login
      if (to.path !== '/auth/setup' && to.path !== '/auth/login') {
        return next('/auth/login');
      }
      return next();
    }

    if (data.setup_required) {
      if (to.path !== '/auth/setup') {
        return next('/auth/setup');
      }
      return next();
    } else {
      // FIXED: After setup, redirect to /welcome instead of /
      if (to.path === '/auth/setup') {
        return next('/welcome');
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
    }
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
