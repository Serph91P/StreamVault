import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SubscriptionsView from '../views/SubscriptionsView.vue'
import AddStreamerView from '../views/AddStreamerView.vue'
import SetupView from '../views/SetupView.vue'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/subscriptions',
      name: 'subscriptions',
      component: SubscriptionsView
    },
    {
      path: '/add-streamer',
      name: 'add-streamer',
      component: AddStreamerView
    },
    {
      path: '/setup',
      name: 'setup',
      component: SetupView
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  // Public routes that don't need checks
  if (to.path === '/setup' || to.path === '/login') {
    return next()
  }

  try {
    // Check setup status first
    const setupResponse = await fetch('/setup')
    const setupData = await setupResponse.json()
    
    // If setup is required, redirect to setup page immediately
    if (setupData.setup_required === true) {
      return next('/setup')
    }

    // Only check auth if setup is complete
    const authResponse = await fetch('/auth/check')
    const authData = await authResponse.json()
    
    if (!authData.authenticated && to.path !== '/login') {
      return next('/login')
    }
    
    return next()
  } catch (error) {
    console.error('Error checking application status:', error)
    // On error, default to setup page
    return next('/setup')
  }
})

export default router