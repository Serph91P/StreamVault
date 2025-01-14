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
      path: '/auth/setup',
      name: 'setup',
      component: SetupView
    },
    {
      path: '/auth/login',
      name: 'login',
      component: LoginView
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  if (to.path === '/auth/setup' || to.path === '/auth/login') {
    try {
      const setupResponse = await fetch('/auth/setup')
      const setupData = await setupResponse.json()
      
      if (!setupData.setup_required && to.path === '/auth/setup') {
        return next('/')
      }
      return next()
    } catch (error) {
      console.error('Error checking setup status:', error)
      return next()
    }
  }

  try {
    const setupResponse = await fetch('/auth/setup')
    const setupData = await setupResponse.json()
    
    if (setupData.setup_required) {
      return next('/auth/setup')
    }

    const authResponse = await fetch('/auth/check')
    if (!authResponse.ok) {
      return next('/auth/login')
    }
    
    return next()
  } catch (error) {
    console.error('Error checking application status:', error)
    return next('/auth/setup')
  }
})
export default router