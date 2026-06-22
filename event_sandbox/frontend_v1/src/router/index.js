import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import SimulationView from '@/views/SimulationView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
