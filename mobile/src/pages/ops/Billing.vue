<template>
  <section class="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
    <PageHeader title="Billing" subtitle="Completed jobs with labour or parts to charge. Invoices are created as drafts in ERPNext for accounts to review." />
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <p v-if="notice" role="status" class="flex flex-wrap items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800"><FeatherIcon name="check-circle" class="h-4 w-4" />Draft invoice <a :href="`/desk/sales-invoice/${notice.invoice}`" target="_blank" rel="noopener" class="font-semibold underline">{{ notice.invoice }}</a> created for {{ money(notice.grand_total) }}.</p>
    <div v-if="busy && !customers.length" class="space-y-3"><div v-for="i in 3" :key="i" class="h-32 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <article v-for="c in customers" :key="c.customer" class="card overflow-hidden">
      <header class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4">
        <div>
          <h2 class="font-semibold">{{ c.customer_name }}</h2>
          <p class="text-xs text-gray-500">{{ c.jobs.length }} job{{ c.jobs.length === 1 ? '' : 's' }} · {{ money(c.total) }}</p>
        </div>
        <button class="btn btn-primary btn-sm" :disabled="!picked(c).length || creating" @click="create(c)"><FeatherIcon name="file-plus" class="h-4 w-4" />{{ picked(c).length > 1 ? `Invoice ${picked(c).length} jobs together` : 'Create invoice' }}</button>
      </header>
      <ul class="divide-y divide-gray-100">
        <li v-for="j in c.jobs" :key="j.name" class="flex items-start gap-3 px-5 py-3">
          <input v-model="selected[j.name]" type="checkbox" class="mt-1 rounded border-gray-300 text-brand-600" :aria-label="`Include ${j.subject}`" />
          <span class="min-w-0 flex-1">
            <router-link :to="{ name: 'OpsWorkOrder', params: { name: j.name } }" class="block truncate text-[15px] font-medium hover:text-brand-700">{{ j.subject }}</router-link>
            <span class="mt-0.5 flex flex-wrap gap-x-3 text-xs text-gray-500">
              <span v-if="j.equipment">{{ j.equipment.site }}</span>
              <span>Done {{ formatDate(j.completed) }}</span>
              <span>Labour {{ money(j.labour) }}<template v-if="j.labour_mode === 'Hourly' && j.hours"> ({{ j.hours }} h)</template></span>
              <span>Parts {{ money(j.parts) }}</span>
              <span v-if="j.missing_hours" class="font-semibold text-amber-700">Hours not recorded</span>
            </span>
          </span>
          <span class="shrink-0 text-[15px] font-semibold tabular-nums">{{ money(j.total) }}</span>
        </li>
      </ul>
    </article>
    <EmptyState v-if="!busy && !customers.length && !error" icon="file-text" title="Nothing to invoice" text="Completed customer jobs with chargeable labour or parts appear here." />

    <div v-if="recent.length" class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Recent invoices from jobs</h2></div>
      <ul class="divide-y divide-gray-100">
        <li v-for="i in recent" :key="i.name">
          <a :href="`/desk/sales-invoice/${i.name}`" target="_blank" rel="noopener" class="flex items-center justify-between gap-3 px-5 py-3 text-sm hover:bg-gray-50">
            <span class="min-w-0 truncate"><span class="font-medium">{{ i.name }}</span> · {{ i.customer_name }}</span>
            <span class="shrink-0 text-xs text-gray-500">{{ i.docstatus === 0 ? 'Draft' : i.status }} · {{ money(i.grand_total) }}</span>
          </a>
        </li>
      </ul>
    </div>
  </section>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, formatDate } from '@/data/ops'

const customers = ref([])
const recent = ref([])
const currency = ref('KES')
const selected = reactive({})
const busy = ref(false)
const creating = ref(false)
const error = ref('')
const notice = ref(null)
const money = (n) => {
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency: currency.value, maximumFractionDigits: 0 })
  } catch (e) {
    return `${currency.value} ${Number(n || 0).toLocaleString()}`
  }
}
const picked = (c) => c.jobs.filter((j) => selected[j.name]).map((j) => j.name)

async function load() {
  busy.value = true
  error.value = ''
  try {
    const r = await api('projectit.billing.billing_queue')
    customers.value = r.customers
    recent.value = r.recent
    currency.value = r.currency || 'KES'
    for (const c of r.customers) for (const j of c.jobs) if (!(j.name in selected)) selected[j.name] = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function create(c) {
  creating.value = true
  error.value = ''
  notice.value = null
  try {
    notice.value = await api('projectit.billing.create_invoice', { jobs: picked(c) })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}
onMounted(load)
</script>
