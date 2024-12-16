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
  // Skip check for setup and login routes
  if (to.path === '/setup' || to.path === '/login') {
    return next()
  }

  try {
    // First check if setup is required
    const setupResponse = await fetch('/setup')
    const setupData = await setupResponse.json()
    
    if (setupData.setup_required) {
      return next('/setup')  // Return here to ensure setup takes priority
    }
    
    // Only check auth if setup is complete
    const authResponse = await fetch('/auth/check')
    const authData = await authResponse.json()
    
    if (!authData.authenticated && to.path !== '/login') {
      next('/login')
    } else {
      next()
    }
  } catch (error) {
    console.error('Error checking status:', error)
    next('/setup')  // Default to setup on error
  }
})

export default router