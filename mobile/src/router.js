import { createRouter, createWebHistory } from 'vue-router'
import { session } from './data/session'
import { userResource } from '@/data/user'
import { createResource } from 'frappe-ui'

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
      { path: 'parts-requests', name: 'OpsPartsRequests', component: () => import('@/pages/ops/PartsRequests.vue') },
      { path: 'reports', name: 'OpsReports', component: () => import('@/pages/ops/Reports.vue') },
      { path: 'billing', name: 'OpsBilling', component: () => import('@/pages/ops/Billing.vue') },
      { path: 'contracts', name: 'OpsContracts', component: () => import('@/pages/ops/Contracts.vue') },
      { path: 'contracts/:name', name: 'OpsContract', component: () => import('@/pages/ops/ContractDetail.vue'), meta: { back: true, title: 'Service contract' } },
      { path: 'assets', name: 'OpsAssets', component: () => import('@/pages/ops/Assets.vue') },
      { path: 'assets/:name', name: 'OpsAsset', component: () => import('@/pages/ops/AssetDetail.vue'), meta: { back: true, title: 'Asset' } },
      { path: 'pm', name: 'OpsPM', component: () => import('@/pages/ops/PMSchedule.vue') },
      { path: 'chat', name: 'OpsChat', component: () => import('@/pages/ops/Chat.vue') },
      { path: 'procedures', name: 'OpsProcedures', component: () => import('@/pages/ops/Procedures.vue') },
      { path: 'procedures/:name', name: 'OpsProcedure', component: () => import('@/pages/ops/ProcedureEditor.vue'), meta: { back: true, title: 'Procedure' } },
      { path: 'chat/:channel', name: 'OpsChannel', component: () => import('@/pages/ops/Channel.vue'), meta: { back: true, title: 'Chat' } },
    ],
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
  try {
    // A deep link or reload with an existing session never ran the login flow, so load the user here.
    if (isLoggedIn && !userResource.data) await userResource.fetch()
    await userResource.Promise
  } catch (error) {
    isLoggedIn = false
  }
  if (to.name === 'Login' && isLoggedIn) {
    next({ name: "Home" })
  } else if (to.name !== 'Login' && !isLoggedIn) {
    next({ name: 'Login' })
  } 
  else if(to.name === 'Login' && !isLoggedIn){
    next()
  }
  else {
    const mobileModules = createResource({
      type: "POST",
      url: "projectit.api.get_modules_for_router",
      makeParams() {
        return {
          user_id: userResource.data
        }
      },
      onSuccess(data) {
        let allowed = false;
        for (let d of data){
          if(to.path.match(d)){
            allowed =  true;
            break;
          }
        }
        if(allowed === true){
            next()
        }
        else{
          next({name : "Home"})
        }
      },
    })

    await mobileModules.fetch()
  }
})

export default router