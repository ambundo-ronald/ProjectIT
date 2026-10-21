<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Customer app" subtitle="Who has the plant app, and whether customers are logging their machines.">
      <a :href="`/api/method/projectit.customer_reports.export?days=${days}`" class="btn btn-secondary" download><FeatherIcon name="download" class="h-4 w-4" /><span class="hidden sm:inline">Excel</span></a>
    </PageHeader>

    <div class="flex flex-wrap items-center gap-2">
      <div class="segmented" role="tablist" aria-label="View">
        <button v-for="t in TABS" :key="t.key" role="tab" :aria-selected="tab === t.key" :aria-pressed="tab === t.key" @click="tab = t.key">{{ t.label }}</button>
      </div>
      <div v-if="tab === 'logging'" class="segmented" role="group" aria-label="Period">
        <button v-for="d in [7, 30, 90]" :key="d" type="button" :aria-pressed="days === d" @click="setDays(d)">{{ d }} days</button>
      </div>
      <input v-model="search" type="search" class="input ml-auto w-full sm:w-64" :placeholder="tab === 'logging' ? 'Search customer or machine' : 'Search name, email or customer'" aria-label="Search" @input="debounced" />
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-600">{{ error }}</p>

    <!-- Logging -->
    <template v-if="tab === 'logging'">
      <div v-if="!log" class="h-48 animate-pulse rounded-2xl bg-gray-200/70" />
      <template v-else>
        <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="card p-4"><p class="text-xs font-medium text-gray-500">Logged overall</p><p class="mt-1 text-[22px] font-semibold tabular-nums text-gray-900">{{ log.overall === null ? '–' : `${log.overall}%` }}</p><p class="text-xs text-gray-500">of expected days, last {{ log.days }} days</p></div>
          <div class="card p-4"><p class="flex items-center gap-1 text-xs font-medium text-gray-500"><FeatherIcon name="check-circle" class="h-3.5 w-3.5 text-green-600" />Logging well</p><p class="mt-1 text-[22px] font-semibold tabular-nums text-gray-900">{{ log.good }}</p><p class="text-xs text-gray-500">machines, 90% or more</p></div>
          <div class="card p-4"><p class="flex items-center gap-1 text-xs font-medium text-gray-500"><FeatherIcon name="alert-circle" class="h-3.5 w-3.5 text-amber-600" />Some days missed</p><p class="mt-1 text-[22px] font-semibold tabular-nums text-gray-900">{{ log.some }}</p><p class="text-xs text-gray-500">machines</p></div>
          <div class="card p-4"><p class="flex items-center gap-1 text-xs font-medium text-gray-500"><FeatherIcon name="x-circle" class="h-3.5 w-3.5 text-red-600" />Not logged</p><p class="mt-1 text-[22px] font-semibold tabular-nums text-gray-900">{{ log.none }}</p><p class="text-xs text-gray-500">machines</p></div>
        </div>

        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Machines</h2><span class="text-xs text-gray-500">{{ log.rows.length }} · worst first</span></div>
          <div v-if="log.rows.length" class="overflow-x-auto">
            <table class="w-full min-w-[720px] text-sm">
              <thead><tr class="border-b border-gray-100 text-left text-xs text-gray-500">
                <th class="px-5 py-2 font-medium">Machine</th><th class="px-3 py-2 font-medium">Schedule</th><th class="px-3 py-2 font-medium">Logged</th>
                <th class="px-3 py-2 font-medium">Last log</th><th class="px-3 py-2 text-right font-medium">People</th><th class="px-5 py-2" />
              </tr></thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="r in log.rows" :key="r.equipment">
                  <td class="px-5 py-2.5"><router-link :to="{ name: 'OpsEquipmentDetail', params: { name: r.equipment } }" class="font-medium text-gray-900 hover:text-brand-700">{{ r.equipment_name }}</router-link><span class="block text-xs text-gray-500">{{ [r.customer_name, r.site].filter(Boolean).join(' · ') }}</span></td>
                  <td class="px-3 py-2.5 text-gray-700">{{ SCHEDULE[r.schedule] || r.schedule }}</td>
                  <td class="px-3 py-2.5">
                    <template v-if="r.expected">
                      <span class="flex items-center gap-2">
                        <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold" :class="tone(r.share).chip"><FeatherIcon :name="tone(r.share).icon" class="h-3.5 w-3.5" />{{ r.share }}%</span>
                        <span class="tabular-nums text-gray-700">{{ r.done }} of {{ r.expected }}</span>
                      </span>
                    </template>
                    <span v-else class="text-gray-500">Not expected</span>
                  </td>
                  <td class="px-3 py-2.5 text-gray-700">{{ r.last_on ? fromNow(r.last_on) : 'Never' }}<span v-if="r.last_by" class="block text-xs text-gray-500">{{ r.last_by }}</span></td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-gray-700">{{ r.people }}</td>
                  <td class="px-5 py-2.5 text-right"><router-link :to="{ path: '/plant', query: { preview: r.equipment } }" class="btn btn-ghost btn-sm" :aria-label="`See ${r.equipment_name} as the customer`"><FeatherIcon name="eye" class="h-4 w-4" />Preview</router-link></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="px-5 py-4 text-sm text-gray-500">No customer has the plant app yet. Invite people from a machine's page (Customer app access).</p>
        </div>
      </template>
    </template>

    <!-- Accounts -->
    <template v-else>
      <div v-if="!people" class="h-48 animate-pulse rounded-2xl bg-gray-200/70" />
      <div v-else class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Accounts</h2><span class="text-xs text-gray-500">{{ people.accounts.length }} people · {{ people.customers }} customers · {{ people.waiting }} not signed in yet · {{ people.off }} switched off</span></div>
        <ul v-if="people.accounts.length" class="divide-y divide-gray-100">
          <li v-for="a in people.accounts" :key="a.user" class="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
            <span class="min-w-0 flex-1">
              <span class="flex flex-wrap items-center gap-x-2">
                <span class="font-medium" :class="a.enabled ? 'text-gray-900' : 'text-gray-500 line-through'">{{ a.full_name }}</span>
                <span class="rounded px-1.5 text-[11px] font-semibold" :class="a.access === 'Customer admin' ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-600'">{{ a.access === 'Customer admin' ? 'Admin' : 'Operator' }}</span>
                <span class="text-xs text-gray-500">{{ a.customer_name }}</span>
              </span>
              <span class="block truncate text-xs text-gray-500">{{ a.user }} · {{ a.access === 'Customer admin' ? 'all machines' : a.machine_names.join(', ') || 'no machines' }}</span>
              <span class="block text-xs" :class="!a.enabled ? 'text-gray-500' : a.joined ? 'text-gray-500' : 'text-amber-700'">
                {{ !a.enabled ? 'Switched off' : a.joined ? `Signed in ${fromNow(a.last_login)}` : 'Invited, has not signed in yet' }}<template v-if="a.last_log"> · last log {{ fromNow(a.last_log) }}</template>
              </span>
            </span>
            <span class="flex shrink-0 gap-1.5">
              <button v-if="a.enabled" class="btn btn-ghost btn-sm" :disabled="busy === a.user" @click="resend(a)"><FeatherIcon name="send" class="h-4 w-4" />New link</button>
              <button class="btn btn-ghost btn-sm" :class="a.enabled ? 'text-red-600' : ''" :disabled="busy === a.user" @click="toggle(a)"><FeatherIcon :name="a.enabled ? 'user-x' : 'user-check'" class="h-4 w-4" />{{ a.enabled ? 'Switch off' : 'Switch on' }}</button>
            </span>
          </li>
        </ul>
        <p v-else class="px-5 py-4 text-sm text-gray-500">No accounts{{ search ? ' match' : ' yet' }}.</p>
      </div>
    </template>

    <Modal :model-value="!!link" title="New sign-in link" :subtitle="link?.name" @update:model-value="link = null">
      <div v-if="link" class="space-y-3 text-sm">
        <p :class="link.emailed ? 'text-green-700' : 'text-amber-800'">{{ link.emailed ? `We emailed ${link.email} a new link.` : `The email could not be sent. Share this link with ${link.name} another way.` }}</p>
        <div class="flex gap-2">
          <input class="input font-mono text-xs" readonly :value="link.link" aria-label="Sign-in link" @focus="$event.target.select()" />
          <button type="button" class="btn btn-secondary shrink-0" @click="copy(link.link)"><FeatherIcon name="copy" class="h-4 w-4" />Copy</button>
        </div>
      </div>
      <template #footer><button class="btn btn-primary" type="button" @click="link = null">Done</button></template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, watch, onMounted } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import Modal from '@/components/ops/Modal.vue'
import { api, request, fromNow } from '@/data/ops'

const TABS = [{ key: 'logging', label: 'Logging' }, { key: 'accounts', label: 'Accounts' }]
const SCHEDULE = { Daily: 'Daily', 'Twice a day': 'Twice a day', Weekly: 'Weekly', 'Not expected': 'Not expected' }
const tab = ref('logging')
const days = ref(30)
const search = ref('')
const log = ref(null)
const people = ref(null)
const error = ref('')
const busy = ref('')
const link = ref(null)

// Status: an icon and a number, never colour alone.
const tone = (share) => (share >= 90 ? { chip: 'bg-green-50 text-green-700', icon: 'check-circle' } : share > 0 ? { chip: 'bg-amber-50 text-amber-800', icon: 'alert-circle' } : { chip: 'bg-red-50 text-red-700', icon: 'x-circle' })

async function load() {
  error.value = ''
  try {
    if (tab.value === 'logging') log.value = await api('projectit.customer_reports.logging', { days: days.value, search: search.value || null })
    else people.value = await api('projectit.customer_reports.accounts', { search: search.value || null })
  } catch (e) {
    error.value = e.message
  }
}
let timer = null
function debounced() {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
}
function setDays(d) {
  days.value = d
  load()
}
watch(tab, load)
onMounted(load)

async function resend(a) {
  busy.value = a.user
  try {
    const r = await request('projectit.customer_accounts.resend_invite', { user: a.user, customer: a.customer })
    link.value = { name: a.full_name, email: a.user, link: r.link, emailed: r.emailed }
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}
async function toggle(a) {
  if (a.enabled && !window.confirm(`Switch off ${a.full_name}'s account? They will not be able to sign in. Their logs are kept.`)) return
  busy.value = a.user
  try {
    await request('projectit.customer_accounts.update_account', { user: a.user, customer: a.customer, enabled: a.enabled ? 0 : 1 })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}
const copy = (text) => navigator.clipboard?.writeText(text).then(() => toast({ title: 'Link copied', icon: 'check', iconClasses: 'text-green-600', position: 'top-center' }))
</script>
