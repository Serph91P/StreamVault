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
  if (to.path === '/setup' || to.path === '/login') {
    try {
      const setupResponse = await fetch('/setup')
      const setupData = await setupResponse.json()
      
      if (!setupData.setup_required && to.path === '/setup') {
        return next('/')
      }
      return next()
    } catch (error) {
      console.error('Error checking setup status:', error)
      return next()
    }
  }

  try {
    const setupResponse = await fetch('/setup')
    const setupData = await setupResponse.json()
    
    if (setupData.setup_required) {
      return next('/setup')
    }

    const authResponse = await fetch('/auth/check')
    if (!authResponse.ok) {
      return next('/login')
    }
    
    return next()
  } catch (error) {
    console.error('Error checking application status:', error)
    return next('/setup')
  }
})

export default router