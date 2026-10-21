import { createRouter, createWebHistory } from 'vue-router'
import { session } from './data/session'
import { userResource } from '@/data/user'
import { api } from '@/data/offline'

const routes = [
  { path: '/', redirect: '/home' },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    path: '/workit',
    component: () => import('@/pages/work/WorkLayout.vue'),
    children: [
      { path: '', name: 'WorkIT', component: () => import('@/pages/work/WorkToday.vue') },
      { path: 'tasks', name: 'MyTasks', component: () => import('@/pages/Tasks.vue') },
      { path: 'history', name: 'WorkHistory', component: () => import('@/pages/work/WorkHistory.vue') },
    ],
  },
  {
    path: '/manageit',
    component: () => import('@/pages/manage/ManageLayout.vue'),
    children: [
      { path: '', name: 'ManageIT', component: () => import('@/pages/manage/ManageProjects.vue') },
      { path: 'projects/:project', name: 'ManageProject', component: () => import('@/pages/manage/ManageProject.vue') },
      { path: 'tasks', name: 'ManageTasks', component: () => import('@/pages/Tasks.vue'), props: { manager: true } },
      // Old bookmarks: both screens are now part of the project page.
      { path: 'edit-instructions/:project_name', redirect: (to) => ({ name: 'ManageProject', params: { project: to.params.project_name } }) },
      { path: 'allocate-employees/:project_name', redirect: (to) => ({ name: 'ManageProject', params: { project: to.params.project_name } }) },
    ],
  },
  {
    path: '/ops',
    name: 'Ops',
    component: () => import('@/pages/ops/OpsLayout.vue'),
    redirect: { name: 'OpsWorkOrders' },
    children: [
      { path: 'work-orders', name: 'OpsWorkOrders', component: () => import('@/pages/ops/WorkOrders.vue') },
      { path: 'work-orders/:name', name: 'OpsWorkOrder', component: () => import('@/pages/ops/WorkOrderDetail.vue'), meta: { back: true, title: 'Work order' } },
      { path: 'requests', name: 'OpsRequests', component: () => import('@/pages/ops/Requests.vue') },
      { path: 'equipment', name: 'OpsEquipment', component: () => import('@/pages/ops/Equipment.vue') },
      { path: 'equipment/:name', name: 'OpsEquipmentDetail', component: () => import('@/pages/ops/EquipmentDetail.vue'), meta: { back: true, title: 'Equipment' } },
      { path: 'parts-requests', name: 'OpsPartsRequests', component: () => import('@/pages/ops/PartsRequests.vue'), meta: { only: 'ops/parts-requests' } },
      { path: 'reports', name: 'OpsReports', component: () => import('@/pages/ops/Reports.vue'), meta: { only: 'ops/reports' } },
      { path: 'billing', name: 'OpsBilling', component: () => import('@/pages/ops/Billing.vue'), meta: { only: 'ops/billing' } },
      { path: 'contracts', name: 'OpsContracts', component: () => import('@/pages/ops/Contracts.vue') },
      { path: 'contracts/:name', name: 'OpsContract', component: () => import('@/pages/ops/ContractDetail.vue'), meta: { back: true, title: 'Service contract' } },
      { path: 'assets', name: 'OpsAssets', component: () => import('@/pages/ops/Assets.vue') },
      { path: 'assets/:name', name: 'OpsAsset', component: () => import('@/pages/ops/AssetDetail.vue'), meta: { back: true, title: 'Asset' } },
      { path: 'pm', name: 'OpsPM', component: () => import('@/pages/ops/PMSchedule.vue') },
      { path: 'customer-app', name: 'OpsCustomerApp', component: () => import('@/pages/ops/CustomerApp.vue'), meta: { title: 'Customer plants', only: 'ops/customer-app' } },
      { path: 'dispatch', name: 'OpsDispatch', component: () => import('@/pages/ops/Dispatch.vue'), meta: { title: 'Dispatch', only: 'ops/dispatch' } },
      { path: 'investigations', name: 'OpsInvestigations', component: () => import('@/pages/ops/Investigations.vue') },
      { path: 'investigations/:name', name: 'OpsInvestigation', component: () => import('@/pages/ops/InvestigationDetail.vue'), meta: { back: true, title: 'Investigation' } },
      { path: 'chat', name: 'OpsChat', component: () => import('@/pages/ops/Chat.vue') },
      { path: 'procedures', name: 'OpsProcedures', component: () => import('@/pages/ops/Procedures.vue') },
      { path: 'procedures/:name', name: 'OpsProcedure', component: () => import('@/pages/ops/ProcedureEditor.vue'), meta: { back: true, title: 'Procedure' } },
      { path: 'chat/:channel', name: 'OpsChannel', component: () => import('@/pages/ops/Channel.vue'), meta: { back: true, title: 'Chat' } },
    ],
  },
  {
    // The customer app: customers' admins and operators (see projectit/plant.py).
    path: '/plant',
    component: () => import('@/pages/plant/PlantLayout.vue'),
    children: [
      { path: '', name: 'PlantHome', component: () => import('@/pages/plant/PlantHome.vue') },
      { path: 'log', name: 'PlantLog', component: () => import('@/pages/plant/PlantLog.vue') },
      { path: 'service', name: 'PlantService', component: () => import('@/pages/plant/PlantService.vue') },
      { path: 'account', name: 'PlantAccount', component: () => import('@/pages/plant/PlantAccount.vue') },
    ],
  },
  {
    // Customers rate a completed visit from the link in their service report email (no sign-in).
    path: '/rate',
    name: 'Rate',
    component: () => import('@/pages/Rate.vue'),
    meta: { public: true },
  },
  {
    // Asset QR codes link here; guests may use it when public requests are enabled.
    path: '/request',
    name: 'PublicRequest',
    component: () => import('@/pages/PublicRequest.vue'),
    meta: { public: true },
  },
  {
    name: 'Login',
    path: '/account/login',
    component: () => import('@/pages/Login.vue'),
  },
]

let router = createRouter({
  history: createWebHistory(window.location.pathname.startsWith('/projectit') ? '/projectit' : '/techy-app'),
  routes,
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.public) return next()
  let isLoggedIn = session.isLoggedIn
  // Without a connection the session cookie is all there is; the server checks again once back online.
  const offline = typeof navigator !== 'undefined' && !navigator.onLine
  if (!offline) {
    try {
      // A deep link or reload with an existing session never ran the login flow, so load the user here.
      if (isLoggedIn && !userResource.data) await userResource.fetch()
      await userResource.Promise
    } catch (error) {
      isLoggedIn = false
    }
  }
  if (to.name === 'Login' && isLoggedIn) return next({ name: 'Home' })
  if (to.name === 'Login') return next()
  if (!isLoggedIn) return next({ name: 'Login' })
  let modules
  try {
    // Saved on the phone by api(), so the apps this person may open are known offline too.
    modules = await api('projectit.api.get_modules_for_router', {})
  } catch (error) {
    // Offline before the list was ever saved: let them in; every screen checks access on the server.
    return next()
  }
  // An app opens everything under its address (/ops, /workit, /manageit); pages marked `only` must be listed.
  const allowed = to.meta.only ? modules.includes(to.meta.only) : modules.some((m) => to.path === `/${m}` || to.path.startsWith(`/${m}/`))
  // Customers have no Home (their plant app is all they have): send them to the first app they may open.
  const fallback = modules.includes('home') || !modules.length ? { name: 'Home' } : `/${modules[0]}`
  next(allowed ? undefined : fallback)
})

export default router