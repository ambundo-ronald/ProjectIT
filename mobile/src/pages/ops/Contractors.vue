<template>
  <section class="mx-auto max-w-5xl p-4 md:p-8">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="min-w-0 flex-1">
        <h1 class="text-[22px] font-semibold tracking-tight md:text-[26px]">Contractors</h1>
        <p class="mt-0.5 text-sm text-gray-500">External technicians and small companies. Give them jobs and projects, and pay them for the work.</p>
      </div>
      <router-link :to="{ name: 'OpsOnSite' }" class="btn btn-secondary"><FeatherIcon name="map-pin" class="h-4 w-4" />On site</router-link>
      <router-link v-if="me.can_invoice" :to="{ name: 'OpsPayouts' }" class="btn btn-secondary"><FeatherIcon name="credit-card" class="h-4 w-4" />Payouts</router-link>
      <button class="btn btn-primary" @click="openNew"><FeatherIcon name="plus" class="h-4 w-4" />New contractor</button>
    </div>

    <div class="mb-4 flex flex-wrap items-center gap-2">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" class="input pl-9" placeholder="Search by name, trade or supplier" aria-label="Search contractors" @input="debounced" />
      </div>
      <label class="flex items-center gap-2 text-sm text-gray-600"><input v-model="showAll" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-brand-600" @change="load" />Show inactive</label>
    </div>

    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!rows && !error" class="space-y-3" aria-busy="true"><div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <ul v-else-if="rows?.length" class="grid gap-3 md:grid-cols-2">
      <li v-for="c in rows" :key="c.name">
        <router-link :to="{ name: 'OpsContractor', params: { name: c.name } }" class="card block p-4 transition hover:border-gray-300">
          <div class="flex items-start gap-3">
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600"><FeatherIcon :name="c.contractor_type === 'Company' ? 'briefcase' : 'user'" class="h-5 w-5" /></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate font-semibold text-gray-900">{{ c.contractor_name }}<span v-if="!c.enabled" class="ml-2 rounded bg-gray-100 px-1.5 text-[11px] font-semibold text-gray-500">Inactive</span></span>
              <span class="block truncate text-sm text-gray-500">{{ [c.contractor_type, c.trades].filter(Boolean).join(' · ') }}</span>
              <span class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
                <span class="inline-flex items-center gap-1"><FeatherIcon name="users" class="h-3 w-3" />{{ c.people.length }} {{ c.people.length === 1 ? 'person' : 'people' }}</span>
                <span class="inline-flex items-center gap-1"><FeatherIcon name="tool" class="h-3 w-3" />{{ c.open_jobs }} open {{ c.open_jobs === 1 ? 'job' : 'jobs' }}</span>
                <span v-if="c.owed.approved" class="inline-flex items-center gap-1 font-medium text-green-700"><FeatherIcon name="credit-card" class="h-3 w-3" />{{ money(c.owed.approved) }} to pay</span>
                <span>{{ c.pay_cycle }}</span>
              </span>
            </span>
          </div>
        </router-link>
      </li>
    </ul>
    <EmptyState v-else icon="briefcase" title="No contractors yet" text="Add the external technicians and companies you give work to. Each is linked to a supplier, so their bills go to Accounts as Purchase Invoices." />

    <Modal v-model="creating" title="New contractor" subtitle="A supplier with the same name is used, or created, for their bills.">
      <form id="new-contractor" class="space-y-3" @submit.prevent="create">
        <div><label class="label" for="nc-name">Name</label><input id="nc-name" v-model="form.contractor_name" class="input" required maxlength="140" placeholder="e.g. Kamau Fixers Ltd or John Otieno" /></div>
        <div>
          <span class="label">Type</span>
          <div class="segmented w-full" role="group" aria-label="Type">
            <button v-for="t in ['Individual', 'Company']" :key="t" type="button" class="flex-1" :aria-pressed="form.contractor_type === t" @click="form.contractor_type = t">{{ t === 'Company' ? 'Company with a crew' : 'Individual' }}</button>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="label" for="nc-phone">Phone</label><input id="nc-phone" v-model="form.phone" type="tel" class="input" /></div>
          <div><label class="label" for="nc-cycle">Usual pay cycle</label><select id="nc-cycle" v-model="form.pay_cycle" class="input"><option>Per job</option><option>Weekly</option><option>Monthly</option></select></div>
        </div>
        <div><label class="label" for="nc-trades">Skills or trades</label><input id="nc-trades" v-model="form.trades" class="input" maxlength="1000" placeholder="e.g. RO installation, plumbing" /></div>
        <div><label class="label" for="nc-supplier">Supplier <span class="font-normal text-gray-400">(optional)</span></label><input id="nc-supplier" v-model="form.supplier" class="input" placeholder="Existing supplier ID, or leave empty" /></div>
        <p v-if="formError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ formError }}</p>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="creating = false">Cancel</button>
        <button type="submit" form="new-contractor" class="btn btn-primary" :disabled="busy">Create</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import Modal from '@/components/ops/Modal.vue'
import { api, me, loadMe } from '@/data/ops'
import { money as fmt } from '@/data/contractor'

const router = useRouter()
const rows = ref(null)
const currency = ref('')
const error = ref('')
const search = ref('')
const showAll = ref(false)
const creating = ref(false)
const busy = ref(false)
const formError = ref('')
const form = reactive({ contractor_name: '', contractor_type: 'Individual', phone: '', pay_cycle: 'Monthly', trades: '', supplier: '' })
const money = (v) => fmt(v, currency.value)
let timer = null
const debounced = () => {
  clearTimeout(timer)
  timer = setTimeout(load, 250)
}
async function load() {
  try {
    const r = await api('projectit.contractors.list_contractors', { search: search.value, include_disabled: showAll.value ? 1 : 0 })
    rows.value = r.contractors
    currency.value = r.currency
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}
function openNew() {
  Object.assign(form, { contractor_name: '', contractor_type: 'Individual', phone: '', pay_cycle: 'Monthly', trades: '', supplier: '' })
  formError.value = ''
  creating.value = true
}
async function create() {
  busy.value = true
  formError.value = ''
  try {
    const r = await api('projectit.contractors.save_contractor', { data: { ...form } })
    creating.value = false
    router.push({ name: 'OpsContractor', params: { name: r.contractor.name } })
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(() => {
  loadMe().catch(() => {})
  load()
})
</script>
