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

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  // FIXED: Always scroll to top when navigating to new page
  scrollBehavior(to, from, savedPosition) {
    // If user clicked back/forward button, restore position
    if (savedPosition) {
      return savedPosition
    }
    // Always scroll to top for new navigation
    return { top: 0, behavior: 'smooth' }
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
      return next('/auth/setup');
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

      if (!authResponse.ok && to.path !== '/auth/login') {
        return next('/auth/login');
      }

      return next();
    }
  } catch (error) {
    console.error('Router error:', error);
    return next('/auth/setup');
  }
});

export default router;
