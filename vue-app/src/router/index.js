import { createRouter, createWebHistory } from 'vue-router'
import ParticipantLogin from '../views/ParticipantLogin.vue'
import ParticipantInterface from '../views/ParticipantInterface.vue'
import ResearcherDashboard from '../views/ResearcherDashboard.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'participant-login',
      component: ParticipantLogin
    },
    {
      path: '/participant',
      name: 'participant-interface',
      component: ParticipantInterface,
      meta: { requiresAuth: true }
    },
    {
      path: '/researcher',
      name: 'researcher-dashboard',
      component: ResearcherDashboard
    }
  ]
})

// Navigation guard to check authentication for participant interface only
router.beforeEach((to, from, next) => {
  if (to.matched.some(record => record.meta.requiresAuth)) {
    const authToken = sessionStorage.getItem('auth_token')
    if (!authToken) {
      next('/login')
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router 