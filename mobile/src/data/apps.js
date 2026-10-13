import { ref, reactive } from 'vue'
import { api } from './ops'

/** Techy App modules, in switcher order. `module` is the Mobile Module Item name on the Employee. */
export const APPS = [
  { module: 'Ops', route: 'Ops', prefix: '/ops', title: 'Techy Ops', icon: 'tool', tone: 'bg-brand-50 text-brand-700', text: 'Work orders, requests, assets and maintenance' },
  { module: 'WorkIT', route: 'WorkIT', prefix: '/workit', title: 'Techy Work', icon: 'briefcase', tone: 'bg-accent-50 text-accent-600', text: 'Check in, tasks and timesheets' },
  { module: 'ManageIT', route: 'ManageIT', prefix: '/manageit', title: 'Techy Manage', icon: 'users', tone: 'bg-amber-50 text-amber-700', text: 'Crews and site instructions' },
]

export const myApps = ref(null)
let loading = null
export function loadApps() {
  loading ||= api('projectit.api.my_apps')
    .then((modules) => (myApps.value = APPS.filter((a) => modules.includes(a.module))))
    .catch(() => {
      loading = null
      myApps.value = []
    })
  return loading
}

/** Shared UI state: pages with their own bottom-fixed controls lift the chat bubble above them. */
export const ui = reactive({ dockLift: 0 })
