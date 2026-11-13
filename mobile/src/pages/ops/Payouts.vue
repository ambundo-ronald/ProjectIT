<template>
  <section class="mx-auto max-w-5xl p-4 md:p-8">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="min-w-0 flex-1">
        <h1 class="text-[22px] font-semibold tracking-tight md:text-[26px]">Contractor payouts</h1>
        <p class="mt-0.5 text-sm text-gray-500">Approved work becomes a draft Purchase Invoice for each contractor. Accounts checks, submits and pays it in ERPNext.</p>
      </div>
      <router-link :to="{ name: 'OpsContractors' }" class="btn btn-secondary"><FeatherIcon name="briefcase" class="h-4 w-4" />Contractors</router-link>
    </div>

    <div class="tabs mb-4" role="tablist">
      <button v-for="t in TABS" :key="t.key" role="tab" :aria-selected="tab === t.key" :class="tab === t.key ? 'is-active' : ''" @click="tab = t.key; loadTab()">{{ t.label }}<span v-if="t.key === 'queries' && queries.length" class="ml-1 rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white">{{ queries.length }}</span></button>
    </div>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <!-- Payout run -->
    <template v-if="tab === 'run'">
      <div class="card mb-4 flex flex-wrap items-end gap-3 p-4">
        <div><label class="label" for="po-upto">Approved up to</label><input id="po-upto" v-model="upTo" type="date" class="input" @change="loadPreview" /></div>
        <div><label class="label" for="po-cycle">Pay cycle</label>
          <select id="po-cycle" v-model="cycle" class="input" @change="loadPreview"><option value="">Everyone due</option><option>Per job</option><option>Weekly</option><option>Monthly</option></select></div>
        <div class="ml-auto text-right"><p class="section-label">Total</p><p class="text-[22px] font-semibold tabular-nums">{{ money(preview?.total) }}</p></div>
      </div>
      <p v-if="preview?.setup" class="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{{ preview.setup }} <a href="/desk/techy-ops-settings" target="_blank" rel="noopener" class="font-medium underline">Open settings</a></p>
      <div v-if="!preview" class="h-40 animate-pulse rounded-xl bg-gray-200/70" />
      <div v-else-if="preview.contractors.length" class="space-y-3">
        <div v-for="g in preview.contractors" :key="g.name" class="card overflow-hidden">
          <label class="card-header cursor-pointer">
            <span class="flex min-w-0 items-center gap-3">
              <input v-model="chosen" type="checkbox" :value="g.name" class="h-5 w-5 rounded-md border-gray-300 text-brand-600" :disabled="!!g.problem" />
              <span class="min-w-0"><span class="block truncate font-semibold text-gray-900">{{ g.contractor_name }}</span><span class="block text-xs text-gray-500">{{ g.pay_cycle }} · {{ g.lines.length }} {{ g.lines.length === 1 ? 'line' : 'lines' }}<template v-if="g.queried"> · <span class="font-medium text-amber-700">{{ g.queried }} queried</span></template></span></span>
            </span>
            <span class="text-right"><span class="block font-semibold tabular-nums">{{ money(g.net) }}</span><span v-if="g.problem" class="text-xs font-medium text-red-700">{{ g.problem }}</span><span v-else-if="g.deducted" class="text-xs text-gray-500">after {{ money(g.deducted) }} deducted</span></span>
          </label>
          <details class="group">
            <summary class="cursor-pointer list-none px-4 py-2 text-xs font-medium text-brand-700">Show lines</summary>
            <ul class="divide-y divide-gray-100 border-t border-gray-100">
              <li v-for="l in g.lines" :key="l.name" class="flex items-center gap-3 px-4 py-2 text-sm">
                <span class="min-w-0 flex-1"><span class="block truncate">{{ l.description }}</span><span class="block truncate text-xs text-gray-500">{{ PAY_TYPE_LABEL[l.pay_type] }}<template v-if="l.subject"> · {{ l.subject }}</template></span></span>
                <span class="tabular-nums" :class="l.pay_type === 'Deduction' ? 'text-red-700' : ''">{{ l.pay_type === 'Deduction' ? '−' : '' }}{{ money(l.amount) }}</span>
              </li>
            </ul>
          </details>
        </div>
        <div class="flex flex-wrap items-center gap-3 pt-1">
          <button class="btn btn-primary" :disabled="!chosen.length || busy || !!preview.setup" @click="createBills"><FeatherIcon name="file-plus" class="h-4 w-4" />Create {{ chosen.length }} draft {{ chosen.length === 1 ? 'bill' : 'bills' }}</button>
          <span class="text-xs text-gray-500">Lines on hold or queried can be held back from the contractor's page.</span>
        </div>
      </div>
      <EmptyState v-else icon="check-circle" title="Nothing to pay" text="Approved work shows here. A job's pay is approved when a manager completes the job." />

      <div v-if="preview?.recent.length" class="card mt-6 overflow-hidden">
        <div class="card-header"><h2 class="card-title">Recent bills</h2></div>
        <ul class="divide-y divide-gray-100 text-sm">
          <li v-for="b in preview.recent" :key="b.name" class="flex items-center gap-3 px-4 py-2.5">
            <a :href="`/desk/purchase-invoice/${b.name}`" target="_blank" rel="noopener" class="link font-mono text-xs">{{ b.name }}</a>
            <span class="min-w-0 flex-1 truncate">{{ b.supplier_name }}</span>
            <span class="text-xs text-gray-500">{{ formatDate(b.posting_date) }}</span>
            <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="b.docstatus === 0 ? 'bg-gray-100 text-gray-700' : b.status === 'Paid' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'">{{ b.docstatus === 0 ? 'Draft' : b.status }}</span>
            <span class="w-24 text-right tabular-nums">{{ money(b.grand_total) }}</span>
          </li>
        </ul>
      </div>
    </template>

    <!-- What we owe -->
    <template v-else-if="tab === 'owed'">
      <div v-if="owed" class="card overflow-hidden">
        <div class="grid grid-cols-2 gap-px bg-gray-100">
          <div class="bg-panel p-4"><p class="section-label">Approved, not billed</p><p class="mt-1 text-[20px] font-semibold tabular-nums">{{ money(owed.approved) }}</p></div>
          <div class="bg-panel p-4"><p class="section-label">Billed, not paid</p><p class="mt-1 text-[20px] font-semibold tabular-nums">{{ money(owed.billed) }}</p></div>
        </div>
        <ul v-if="owed.rows.length" class="divide-y divide-gray-100 text-sm">
          <li v-for="r in owed.rows" :key="r.name">
            <router-link :to="{ name: 'OpsContractor', params: { name: r.name } }" class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50">
              <span class="min-w-0 flex-1 truncate font-medium">{{ r.contractor_name }}</span>
              <span class="w-28 text-right tabular-nums text-gray-600">{{ money(r.approved) }}</span>
              <span class="w-28 text-right tabular-nums text-gray-600">{{ money(r.billed) }}</span>
              <span class="w-28 text-right font-semibold tabular-nums">{{ money(r.total) }}</span>
            </router-link>
          </li>
        </ul>
        <p v-else class="px-4 py-4 text-sm text-gray-500">We owe no contractor anything right now.</p>
      </div>
    </template>

    <!-- Queries -->
    <template v-else-if="tab === 'queries'">
      <ul v-if="queries.length" class="space-y-2">
        <li v-for="q in queries" :key="q.name" class="card p-4">
          <div class="flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-gray-900">{{ q.contractor_name }}: {{ q.description }}</p>
              <p class="mt-1 whitespace-pre-wrap text-sm text-gray-700">{{ q.query_note }}</p>
            </div>
            <span class="shrink-0 font-semibold tabular-nums">{{ money(q.amount) }}</span>
          </div>
          <div class="mt-2 flex flex-wrap gap-2">
            <button class="btn btn-secondary btn-sm" @click="answer(q)">Answer</button>
            <router-link v-if="q.work_order" :to="{ name: 'OpsWorkOrder', params: { name: q.work_order } }" class="btn btn-ghost btn-sm">Open the job</router-link>
            <router-link :to="{ name: 'OpsContractor', params: { name: q.contractor } }" class="btn btn-ghost btn-sm">Contractor</router-link>
          </div>
        </li>
      </ul>
      <EmptyState v-else icon="message-square" title="No open queries" text="When a contractor questions a line on their pay, it shows here." />
    </template>

    <!-- Report -->
    <template v-else-if="tab === 'report'">
      <div class="mb-3 flex items-center gap-2 text-sm">
        <label for="po-days" class="text-gray-600">Period</label>
        <select id="po-days" v-model.number="days" class="input !w-auto" @change="loadTab"><option :value="30">30 days</option><option :value="90">90 days</option><option :value="180">6 months</option><option :value="365">Year</option></select>
      </div>
      <div v-if="report" class="card overflow-x-auto">
        <table class="w-full min-w-[640px] text-sm">
          <thead class="bg-gray-50 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            <tr><th class="px-4 py-2">Contractor</th><th class="px-4 py-2 text-right">Jobs</th><th class="px-4 py-2 text-right">On time</th><th class="px-4 py-2 text-right">Reworked</th><th class="px-4 py-2 text-right">Declined</th><th class="px-4 py-2 text-right">Average job</th><th class="px-4 py-2 text-right">Paid</th></tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="r in report.rows" :key="r.contractor">
              <td class="px-4 py-2.5"><router-link :to="{ name: 'OpsContractor', params: { name: r.contractor } }" class="link">{{ r.contractor_name }}</router-link></td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ r.jobs }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ r.on_time_rate == null ? '—' : `${r.on_time_rate}%` }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ r.rework_rate == null ? '—' : `${r.rework_rate}%` }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ r.declined }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ r.average_cost == null ? '—' : money(r.average_cost) }}</td>
              <td class="px-4 py-2.5 text-right tabular-nums">{{ money(r.paid) }}</td>
            </tr>
            <tr v-if="!report.rows.length"><td colspan="7" class="px-4 py-4 text-gray-500">No contractor work in this period.</td></tr>
          </tbody>
        </table>
      </div>
      <p class="mt-2 text-xs text-gray-500">On time: completed by the due date. Reworked: sent back for more work at least once. Average job: what we paid per completed job.</p>
    </template>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, formatDate } from '@/data/ops'
import { money as fmt, PAY_TYPE_LABEL } from '@/data/contractor'

const TABS = [{ key: 'run', label: 'Payout run' }, { key: 'owed', label: 'What we owe' }, { key: 'queries', label: 'Queries' }, { key: 'report', label: 'Report' }]
const tab = ref('run')
const upTo = ref(new Date().toISOString().slice(0, 10))
const cycle = ref('')
const preview = ref(null)
const chosen = ref([])
const owed = ref(null)
const queries = ref([])
const report = ref(null)
const days = ref(90)
const busy = ref(false)
const error = ref('')
const currency = ref('')
const money = (v) => fmt(v, currency.value)

async function loadPreview() {
  try {
    preview.value = await api('projectit.payouts.preview', { up_to: upTo.value, cycle: cycle.value || null })
    currency.value = preview.value.currency
    chosen.value = preview.value.contractors.filter((g) => !g.problem).map((g) => g.name)
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}
async function loadTab() {
  error.value = ''
  try {
    if (tab.value === 'run') await loadPreview()
    else if (tab.value === 'owed') owed.value = await api('projectit.payouts.owed')
    else if (tab.value === 'queries') queries.value = await api('projectit.contractor_pay.queries')
    else report.value = await api('projectit.payouts.report', { days: days.value })
  } catch (e) {
    error.value = e.message
  }
}
async function createBills() {
  if (!window.confirm(`Create ${chosen.value.length} draft Purchase Invoice(s)? Accounts reviews and submits them in ERPNext.`)) return
  busy.value = true
  try {
    const r = await api('projectit.payouts.create_bills', { up_to: upTo.value, contractors: chosen.value })
    preview.value = r.preview
    chosen.value = r.preview.contractors.filter((g) => !g.problem).map((g) => g.name)
    if (r.bills.length) toast({ title: `${r.bills.length} draft ${r.bills.length === 1 ? 'bill' : 'bills'} created`, text: r.bills.map((b) => b.invoice).join(', '), icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    if (r.failed.length) error.value = r.failed.map((f) => f.error).join(' ')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function answer(q) {
  const note = window.prompt(`Answer ${q.contractor_name} about “${q.description}”:`)
  if (!note) return
  try {
    await api('projectit.contractor_pay.answer_query', { line: q.name, note })
    queries.value = await api('projectit.contractor_pay.queries')
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}
onMounted(() => {
  loadPreview()
  api('projectit.contractor_pay.queries').then((q) => (queries.value = q)).catch(() => {})
})
</script>
