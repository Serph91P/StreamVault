import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import SubscriptionsView from '../views/SubscriptionsView.vue';
import AddStreamerView from '../views/AddStreamerView.vue';
import SetupView from '../views/SetupView.vue';
import LoginView from '../views/LoginView.vue';
import AdminView from '../views/AdminView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
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
  ],
});

router.beforeEach(async (to, from, next) => {
  try {
    const response = await fetch('/auth/setup', {
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    const data = await response.json();

    if (data.setup_required) {
      if (to.path !== '/auth/setup') {
        return next('/auth/setup');
      }
      return next();
    } else {
      if (to.path === '/auth/setup') {
        return next('/');
      }

      const authResponse = await fetch('/auth/check', {
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
