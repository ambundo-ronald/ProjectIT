<template>
  <div class="ops min-h-[100dvh]">
    <header class="border-b border-gray-200 bg-white">
      <div class="mx-auto flex h-16 max-w-3xl items-center gap-3 px-4">
        <img :src="logo" alt="" class="h-8 w-8 rounded-lg object-contain" @error="logoFailed = true" />
        <span class="min-w-0 flex-1 truncate font-semibold">{{ companyInfo.data?.[1] || 'Techy App' }}</span>
        <UserMenu />
      </div>
    </header>

    <main class="mx-auto max-w-3xl px-4 py-8 md:py-12">
      <p class="text-sm font-medium text-brand-600">{{ greeting }}</p>
      <h1 class="mt-1 text-[24px] font-semibold tracking-tight md:text-[30px]">{{ firstName ? `${firstName}, where to?` : 'Where to?' }}</h1>

      <div v-if="apps === null" class="mt-8 space-y-3">
        <div v-for="i in 2" :key="i" class="h-24 animate-pulse rounded-2xl bg-gray-200/70" />
      </div>
      <div v-else-if="modules.length || shortcuts.length" class="mt-8 grid gap-3 sm:grid-cols-2">
        <button v-for="m in [...modules, ...shortcuts]" :key="m.module" class="card group flex items-start gap-4 p-5 text-left transition hover:-translate-y-0.5 hover:border-gray-300 hover:shadow-pop" @click="router.push({ name: m.route })">
          <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl" :class="m.tone"><FeatherIcon :name="m.icon" class="h-6 w-6" /></span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between font-semibold text-gray-900"><span>{{ m.title }}<span v-if="m.count" class="ml-2 rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white">{{ m.count }}</span></span><FeatherIcon name="arrow-right" class="h-4 w-4 text-gray-300 transition group-hover:translate-x-0.5 group-hover:text-brand-600" /></span>
            <span class="mt-1 block text-sm text-gray-500">{{ m.text }}</span>
          </span>
        </button>
      </div>
      <div v-else class="mt-8">
        <EmptyState icon="user-x" title="No apps enabled for your account" text="Ask an administrator to link your user to an Employee and tick Techy Ops, Techy Work or Techy Manage under Techy App Access, or to give you a maintenance role." />
      </div>
    </main>
  </div>
</template>

<script setup>
import { inject, computed, ref } from 'vue'
import { createResource, FeatherIcon } from 'frappe-ui'
import { useRoute, useRouter } from 'vue-router'
import EmptyState from '../components/ops/EmptyState.vue'
import UserMenu from '../components/ops/UserMenu.vue'
import { api, me, loadMe } from '../data/ops'

const router = useRouter()
const route = useRoute()
const employee = inject('employee_id')

const CATALOG = {
  Ops: { route: 'Ops', title: 'Techy Ops', icon: 'tool', tone: 'bg-brand-50 text-brand-700', text: 'Work orders, requests, assets, maintenance and team chat.' },
  WorkIT: { route: 'WorkIT', title: 'Techy Work', icon: 'briefcase', tone: 'bg-accent-50 text-accent-600', text: 'Check in and out, your tasks, instructions and timesheets.' },
  ManageIT: { route: 'ManageIT', title: 'Techy Manage', icon: 'users', tone: 'bg-amber-50 text-amber-700', text: 'Allocate people to projects and share instructions.' },
}
// Role-based shortcuts that do not need an app module (e.g. stock keepers approving parts).
const shortcuts = computed(() => [
  me.can_approve_parts && { module: 'parts', route: 'OpsPartsRequests', title: 'Parts requests', icon: 'package', tone: 'bg-amber-50 text-amber-700', text: 'Approve technicians’ parts lists into Material Requests.', count: me.counts?.pending_parts },
  me.can_invoice && { module: 'billing', route: 'OpsBilling', title: 'Billing', icon: 'file-text', tone: 'bg-green-50 text-green-700', text: 'Turn completed customer jobs into draft invoices.' },
].filter(Boolean))
// The apps this person may open, decided on the server (Employee ticks plus roles; see projectit/api.py).
const apps = ref(null)
const modules = computed(() => (apps.value || []).filter((m) => CATALOG[m]).map((m) => ({ module: m, ...CATALOG[m] })))
// Wait for the shortcuts too: someone with one app and an approval queue should see Home.
Promise.all([api('projectit.api.my_apps'), loadMe().catch(() => null)])
  .then(([list]) => {
    apps.value = list
    // Someone with a single app goes straight into it right after signing in or opening the app, but Home itself
    // ("All apps", the back button) always stays open.
    let signedIn = false
    try {
      signedIn = sessionStorage.getItem('techy_signed_in') === '1'
      sessionStorage.removeItem('techy_signed_in')
    } catch (e) {
      /* storage blocked */
    }
    const opened = signedIn || route.redirectedFrom?.path === '/'
    if (opened && list.length === 1 && !shortcuts.value.length && CATALOG[list[0]]) router.replace({ name: CATALOG[list[0]].route })
  })
  .catch(() => (apps.value = []))

const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
const firstName = (cookies.get('full_name') || '').split(' ')[0]
const hour = new Date().getHours()
const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

const companyInfo = createResource({ url: 'projectit.api.get_header_info', auto: true })
const logoFailed = ref(false)
const logo = computed(() => (!logoFailed.value && companyInfo.data?.[0]) || `${import.meta.env.BASE_URL}techy-app.svg`)

// Kept for the parts of the app that remember the signed-in Employee.
createResource({
  type: 'POST',
  url: 'projectit.api.get_employee_id',
  onSuccess(d) {
    if (d) employee.name = d
  },
  auto: true,
})
</script>
