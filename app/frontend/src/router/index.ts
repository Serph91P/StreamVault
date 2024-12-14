import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SubscriptionsView from '../views/SubscriptionsView.vue'
import AddStreamerView from '../views/AddStreamerView.vue'

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
    }
  ]
})

export default routerexport default router