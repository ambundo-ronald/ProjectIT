<template>
  <section class="mx-auto max-w-5xl p-4 md:p-8" :class="editable ? 'pb-40 md:pb-28' : ''">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsContracts' }" class="hover:text-gray-800">Service contracts</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">{{ isNew ? 'New contract' : form.customer_name || route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="loading" class="space-y-4"><div class="h-32 animate-pulse rounded-xl bg-gray-200/70" /><div class="h-64 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <div v-else class="space-y-5">
      <div v-if="paymentWarning" class="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-800"><FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" />Subscription {{ subscriptionRow?.name }} is <strong class="font-semibold">{{ subscriptionRow?.status }}</strong>. Check payment before extra work.</div>

      <!-- Customer and billing -->
      <div class="card space-y-4 p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="section-label">Customer</p>
            <p v-if="form.customer" class="mt-1 text-[18px] font-semibold">{{ form.customer_name || form.customer }}</p>
          </div>
          <span v-if="!isNew" class="rounded-md px-2 py-1 text-xs font-semibold" :class="stateTone">{{ state }}</span>
        </div>
        <div v-if="editable && isNew && !form.customer" class="relative">
          <input v-model="customerQuery" class="input" placeholder="Search customers" aria-label="Customer" autocomplete="off" @input="findCustomers" @focus="findCustomers" />
          <ul v-if="customers.length" class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-pop">
            <li v-for="c in customers" :key="c.name"><button type="button" class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50" @mousedown.prevent="setCustomer(c)">{{ c.customer_name }}</button></li>
          </ul>
        </div>

        <template v-if="form.customer">
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="sm:col-span-2">
              <label class="label" for="sc-title">Title</label>
              <input id="sc-title" v-model="form.title" :disabled="!editable" maxlength="140" class="input" placeholder="e.g. RO service – quarterly (filled in if left blank)" />
            </div>
            <div class="sm:col-span-2">
              <label class="label" for="sc-sub">Subscription (billing)</label>
              <select id="sc-sub" v-model="form.subscription" :disabled="!editable" class="input">
                <option value="">{{ subscriptions.length ? 'Not linked' : 'This customer has no Subscription in ERPNext' }}</option>
                <option v-for="s in subscriptions" :key="s.name" :value="s.name">{{ s.name }} · {{ s.status }}<template v-if="s.end_date"> · until {{ formatDate(s.end_date) }}</template></option>
              </select>
              <button v-if="editable && subscriptionRow?.start_date" type="button" class="mt-1 text-xs font-medium text-brand-600 hover:underline" @click="useSubscriptionDates">Use the subscription's dates</button>
            </div>
            <div>
              <label class="label" for="sc-start">Start date <span class="text-red-500">*</span></label>
              <input id="sc-start" v-model="form.start_date" type="date" :disabled="!editable" class="input" />
            </div>
            <div>
              <label class="label" for="sc-end">End date <span class="text-red-500">*</span></label>
              <input id="sc-end" v-model="form.end_date" type="date" :disabled="!editable" class="input" />
            </div>
          </div>
        </template>
      </div>

      <template v-if="form.customer">
        <!-- Cover -->
        <div class="card space-y-4 p-5">
          <h2 class="card-title">What's covered</h2>
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="label" for="sc-freq">Service visits</label>
              <select id="sc-freq" v-model="form.visit_frequency" :disabled="!editable" class="input">
                <option v-for="f in FREQUENCIES" :key="f">{{ f }}</option>
              </select>
            </div>
            <div>
              <label class="label" for="sc-proc">Visit procedure</label>
              <ProcedureSelect id="sc-proc" v-model="form.visit_procedure" :disabled="!editable" placeholder="No procedure" />
            </div>
          </div>
          <div class="grid gap-2 sm:grid-cols-2">
            <label class="flex items-start gap-3 rounded-lg border border-gray-200 p-3" :class="editable ? 'cursor-pointer hover:bg-gray-50' : ''">
              <input v-model="form.labour_included" type="checkbox" :disabled="!editable" class="mt-0.5 rounded border-gray-300 text-brand-600" />
              <span><span class="block text-sm font-medium">Labour included</span><span class="text-xs text-gray-500">On scheduled service visits</span></span>
            </label>
            <label class="flex items-start gap-3 rounded-lg border border-gray-200 p-3" :class="editable ? 'cursor-pointer hover:bg-gray-50' : ''">
              <input v-model="form.callouts_included" type="checkbox" :disabled="!editable" class="mt-0.5 rounded border-gray-300 text-brand-600" />
              <span><span class="block text-sm font-medium">Breakdown call-outs included</span><span class="text-xs text-gray-500">Unscheduled visits when something fails</span></span>
            </label>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="label" for="sc-response">On site within (hours)</label>
              <input id="sc-response" v-model="form.response_hours" type="number" min="0" max="720" step="0.5" :disabled="!editable" class="input" placeholder="No promise" />
            </div>
            <div>
              <label class="label" for="sc-fix">Fixed within (hours)</label>
              <input id="sc-fix" v-model="form.fix_hours" type="number" min="0" max="720" step="0.5" :disabled="!editable" class="input" placeholder="No promise" />
            </div>
            <p class="text-xs text-gray-500 sm:col-span-2">For breakdowns on this contract's machines, counted from the customer's request (or when the job is opened). Technicians and managers are warned an hour before a response is due.</p>
          </div>
          <div>
            <span class="label">Parts included at no charge</span>
            <div class="flex flex-wrap gap-2">
              <span v-for="(it, i) in items" :key="it.item_code" class="inline-flex items-center gap-1.5 rounded-full bg-green-50 py-1 pl-3 pr-2 text-sm text-green-800 ring-1 ring-inset ring-green-200">
                {{ it.item_name || it.item_code }}
                <button v-if="editable" type="button" class="rounded-full p-0.5 hover:bg-green-100" :aria-label="`Remove ${it.item_name || it.item_code}`" @click="items.splice(i, 1)"><FeatherIcon name="x" class="h-3.5 w-3.5" /></button>
              </span>
              <span v-if="!items.length" class="text-sm text-gray-500">None. Every part used is charged.</span>
            </div>
            <div v-if="editable" class="relative mt-2 sm:w-80">
              <input v-model="itemQuery" class="input h-9" placeholder="Add a part, e.g. pre-filter" aria-label="Add an included part" autocomplete="off" @input="findItems" @focus="findItems" @blur="hideItems" />
              <ul v-if="itemResults.length" class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-pop">
                <li v-for="it in itemResults" :key="it.name"><button type="button" class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50" @mousedown.prevent="addItem(it)">{{ it.item_name }} <span class="text-gray-400">· {{ it.name }}</span></button></li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Machines -->
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Machines</h2><span class="text-xs text-gray-500">{{ machines.filter((m) => m.included).length }} covered</span></div>
          <ul v-if="machines.length" class="divide-y divide-gray-100">
            <li v-for="m in machines" :key="m.equipment" class="flex flex-wrap items-center gap-3 px-5 py-3">
              <label class="flex min-w-0 flex-1 items-center gap-3" :class="editable ? 'cursor-pointer' : ''">
                <input v-if="editable" v-model="m.included" type="checkbox" class="rounded border-gray-300 text-brand-600" :aria-label="`Cover ${m.equipment_name} at ${m.site}`" />
                <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
                <span class="min-w-0"><span class="block truncate text-sm font-medium">{{ m.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ m.site || 'No site' }} · {{ m.tag || m.equipment }}<template v-if="m.other_contract"> · on {{ m.other_contract }}</template></span></span>
              </label>
              <div v-if="m.included" class="flex items-center gap-2 text-xs text-gray-500">
                <label :for="`nv-${m.equipment}`">Next visit</label>
                <input :id="`nv-${m.equipment}`" v-model="m.next_visit" type="date" :disabled="!editable" class="input h-8 w-36 px-2 text-[13px]" />
                <router-link v-if="m.last_visit_job" :to="{ name: 'OpsWorkOrder', params: { name: m.last_visit_job } }" class="link">Last visit</router-link>
              </div>
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">This customer has no equipment yet. Deliver or register a machine first.</p>
          <p v-if="editable && machines.some((m) => m.included && !m.next_visit)" class="border-t border-gray-100 px-5 py-2 text-xs text-gray-500">Leave the next visit blank to start one {{ (form.visit_frequency || 'Quarterly').toLowerCase().replace('every ', '') }} after the start date.</p>
        </div>

        <!-- Visits -->
        <div v-if="!isNew" class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Visits</h2><span class="text-xs text-gray-500">{{ visits.length }}</span></div>
          <ul v-if="visits.length" class="divide-y divide-gray-100">
            <li v-for="v in visits" :key="v.name">
              <router-link :to="{ name: 'OpsWorkOrder', params: { name: v.name } }" class="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
                <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ v.subject }}</span><span class="text-xs text-gray-500">Due {{ v.exp_end_date ? formatDate(v.exp_end_date) : '—' }}</span></span>
                <StatusPill :status="v.status" />
              </router-link>
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">Visit jobs appear here {{ leadText }} before each machine's next visit.</p>
        </div>

        <div class="card p-5">
          <label class="label" for="sc-notes">Notes</label>
          <textarea id="sc-notes" v-model="form.notes" :disabled="!editable" rows="2" maxlength="2000" class="input" placeholder="Response time, access, anything special about this customer…" />
        </div>
      </template>
    </div>

    <div v-if="editable && !loading && form.customer" class="fixed inset-x-0 bottom-16 z-30 border-t border-gray-200 bg-white/95 backdrop-blur md:bottom-0 md:left-64">
      <div class="mx-auto flex max-w-5xl items-center gap-2 p-3 md:pl-8 md:pr-24">
        <button v-if="!isNew" type="button" class="btn btn-ghost text-gray-500" :disabled="saving" @click="toggleCancel">{{ form.status === 'Cancelled' ? 'Reactivate' : 'Cancel contract' }}</button>
        <router-link :to="{ name: 'OpsContracts' }" class="btn btn-secondary ml-auto">Close</router-link>
        <button type="button" class="btn btn-primary" :disabled="saving || !form.start_date || !form.end_date" @click="save()"><FeatherIcon name="check" class="h-4 w-4" />{{ saving ? 'Saving…' : isNew ? 'Create contract' : 'Save changes' }}</button>
      </div>
    </div>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import StatusPill from '@/components/ops/StatusPill.vue'
import ProcedureSelect from '@/components/ops/ProcedureSelect.vue'
import { api, me, formatDate } from '@/data/ops'
import { ui } from '@/data/apps'

const FREQUENCIES = ['Monthly', 'Every 2 months', 'Quarterly', 'Every 4 months', 'Half-yearly', 'Yearly']
const route = useRoute()
const router = useRouter()
const isNew = computed(() => route.params.name === 'new')
const editable = computed(() => me.manager)
const form = reactive({ customer: '', customer_name: '', title: '', status: 'Active', subscription: '', start_date: '', end_date: '', visit_frequency: 'Quarterly', visit_procedure: '', labour_included: true, callouts_included: false, response_hours: '', fix_hours: '', notes: '', modified: null })
const items = ref([])
const machines = ref([])
const visits = ref([])
const subscriptions = ref([])
const customers = ref([])
const customerQuery = ref('')
const itemQuery = ref('')
const itemResults = ref([])
const state = ref('Active')
const loading = ref(!isNew.value)
const saving = ref(false)
const error = ref('')
const leadText = computed(() => `${me.lead_days ?? 3} days`)
const subscriptionRow = computed(() => subscriptions.value.find((s) => s.name === form.subscription))
const paymentWarning = computed(() => ['Grace Period', 'Unpaid', 'Cancelled'].includes(subscriptionRow.value?.status))
const stateTone = computed(() => ({ Active: 'bg-green-50 text-green-700', Upcoming: 'bg-violet-50 text-violet-700', Expired: 'bg-red-50 text-red-700', Cancelled: 'bg-gray-100 text-gray-500' })[state.value])

let timer = null
function findCustomers() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    try {
      customers.value = (await api('projectit.contracts.contract_options', { txt: customerQuery.value })).customers
    } catch (e) {
      error.value = e.message
    }
  }, 200)
}
async function loadCustomer(existing = []) {
  const opts = await api('projectit.contracts.contract_options', { customer: form.customer })
  subscriptions.value = opts.subscriptions
  const covered = Object.fromEntries(existing.map((m) => [m.equipment, m]))
  const list = opts.equipment.map((e) => ({ equipment: e.name, equipment_name: e.equipment_name, site: e.site, tag: e.tag, included: !!covered[e.name], next_visit: covered[e.name]?.next_visit || '', last_visit_job: covered[e.name]?.last_visit_job, other_contract: e.service_contract && e.service_contract !== route.params.name ? e.service_contract : '' }))
  // Covered machines that are no longer active still show, so they can be removed.
  for (const m of existing) if (!list.some((l) => l.equipment === m.equipment)) list.push({ ...m, included: true })
  machines.value = list
}
async function setCustomer(c) {
  Object.assign(form, { customer: c.name, customer_name: c.customer_name })
  customers.value = []
  try {
    await loadCustomer()
    if (machines.value.length === 1) machines.value[0].included = true
  } catch (e) {
    error.value = e.message
  }
}
function useSubscriptionDates() {
  form.start_date = subscriptionRow.value.start_date || form.start_date
  form.end_date = subscriptionRow.value.end_date || form.end_date
}
let itemTimer = null
function findItems() {
  clearTimeout(itemTimer)
  itemTimer = setTimeout(async () => {
    try {
      itemResults.value = (await api('projectit.contracts.search_items', { txt: itemQuery.value })).filter((i) => !items.value.some((x) => x.item_code === i.name))
    } catch (e) {
      error.value = e.message
    }
  }, 200)
}
const hideItems = () => setTimeout(() => (itemResults.value = []), 150)
function addItem(it) {
  items.value.push({ item_code: it.name, item_name: it.item_name })
  itemQuery.value = ''
  itemResults.value = []
}

function apply(r) {
  const c = r.contract
  Object.assign(form, { customer: c.customer, customer_name: c.customer_name, title: c.title || '', status: c.status, subscription: c.subscription || '', start_date: c.start_date, end_date: c.end_date, visit_frequency: c.visit_frequency || 'Quarterly', visit_procedure: c.visit_procedure || '', labour_included: !!c.labour_included, callouts_included: !!c.callouts_included, response_hours: c.response_hours || '', fix_hours: c.fix_hours || '', notes: c.notes || '', modified: c.modified })
  items.value = r.items
  visits.value = r.visits
  state.value = r.state
  return loadCustomer(r.machines)
}

async function save(extra = {}) {
  saving.value = true
  error.value = ''
  try {
    const data = { ...form, ...extra, items: items.value.map((i) => i.item_code), labour_included: form.labour_included ? 1 : 0, callouts_included: form.callouts_included ? 1 : 0, machines: machines.value.filter((m) => m.included).map((m) => ({ equipment: m.equipment, next_visit: m.next_visit || null })) }
    const r = await api('projectit.contracts.save_contract', { name: isNew.value ? null : route.params.name, data })
    toast({ title: isNew.value ? 'Contract created' : 'Contract saved', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    if (isNew.value) router.replace({ name: 'OpsContract', params: { name: r.contract.name } })
    else await apply(r)
  } catch (e) {
    error.value = e.message
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    saving.value = false
  }
}
function toggleCancel() {
  const cancelling = form.status !== 'Cancelled'
  if (cancelling && !window.confirm('Cancel this contract? Its machines lose contract cover. Cancel the Subscription in ERPNext separately.')) return
  save({ status: cancelling ? 'Cancelled' : 'Active' })
}

onMounted(async () => {
  ui.dockLift = editable.value ? 64 : 0
  if (isNew.value) {
    if (route.query.customer) await setCustomer({ name: String(route.query.customer), customer_name: String(route.query.customer_name || route.query.customer) })
    if (route.query.equipment) for (const m of machines.value) m.included = m.equipment === route.query.equipment || m.included
    return
  }
  try {
    await apply(await api('projectit.contracts.get_contract', { name: route.params.name }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => (ui.dockLift = 0))
</script>
