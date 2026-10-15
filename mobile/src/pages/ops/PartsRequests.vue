<template>
  <section class="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
    <PageHeader title="Parts requests" subtitle="Technicians' parts lists waiting for approval. Approving raises an ERPNext Material Request for the stock team." />
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="busy && !jobs.length" class="space-y-3"><div v-for="i in 3" :key="i" class="h-32 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <article v-for="job in jobs" :key="job.work_order" class="card overflow-hidden">
      <header class="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 px-5 py-4">
        <div class="min-w-0">
          <router-link :to="{ name: 'OpsWorkOrder', params: { name: job.work_order } }" class="block truncate font-semibold hover:text-brand-700">{{ job.subject || job.work_order }}</router-link>
          <p class="mt-0.5 text-xs text-gray-500">
            {{ job.requested_by }} · {{ fromNow(job.requested_on) }}<template v-if="job.equipment"> · {{ job.equipment.customer_name }}, {{ job.equipment.site }}</template><template v-if="job.due"> · due {{ formatDate(job.due) }}</template>
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-secondary btn-sm" :disabled="acting === job.work_order" @click="reject(job, job.lines.map((l) => l.name))">Reject all</button>
          <button class="btn btn-success btn-sm" :disabled="acting === job.work_order" @click="approve(job, null)"><FeatherIcon name="check-circle" class="h-4 w-4" />Approve all</button>
        </div>
      </header>
      <ul class="divide-y divide-gray-100">
        <li v-for="l in job.lines" :key="l.name" class="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3">
          <span class="min-w-0 flex-1">
            <span class="block text-[15px] font-medium">{{ fmt(l.qty) }} × {{ l.item_name }}</span>
            <span class="mt-0.5 flex flex-wrap gap-x-2 text-xs text-gray-500">
              <span>{{ l.warehouse }}</span>
              <span :class="l.in_stock >= l.qty ? 'text-green-700' : 'font-semibold text-red-600'">{{ fmt(l.in_stock) }} in stock</span>
              <span>{{ l.billing }}<template v-if="l.billing === 'Chargeable'"> · {{ money(l.amount) }}</template></span>
            </span>
          </span>
          <span class="flex gap-2">
            <button class="btn btn-ghost btn-sm text-gray-500" :disabled="acting === job.work_order" @click="reject(job, [l.name])">Reject</button>
            <button class="btn btn-secondary btn-sm" :disabled="acting === job.work_order" @click="approve(job, [l.name])"><FeatherIcon name="check" class="h-4 w-4" />Approve</button>
          </span>
        </li>
      </ul>
    </article>
    <EmptyState v-if="!busy && !jobs.length && !error" icon="check-circle" title="Nothing to approve" text="Parts lists that technicians send for approval appear here." />
  </section>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, formatDate, fromNow, loadMe, onRealtime } from '@/data/ops'

const jobs = ref([])
const currency = ref('KES')
const busy = ref(false)
const acting = ref('')
const error = ref('')
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
const money = (n) => {
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency: currency.value, maximumFractionDigits: 0 })
  } catch (e) {
    return `${currency.value} ${fmt(n)}`
  }
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    const r = await api('projectit.parts.approval_queue')
    jobs.value = r.jobs
    currency.value = r.currency || 'KES'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function act(job, method, args, done) {
  acting.value = job.work_order
  error.value = ''
  try {
    const r = await api(method, { work_order: job.work_order, ...args })
    if (done) done(r)
    await load()
    loadMe(true).catch(() => {})
  } catch (e) {
    error.value = e.message
  } finally {
    acting.value = ''
  }
}
const approve = (job, lines) => act(job, 'projectit.parts.approve_parts', { lines }, (r) => toast({ title: `Approved · ${r.material_requests.join(', ')}`, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' }))
function reject(job, lines) {
  const reason = window.prompt('Why are these parts rejected? The technician sees this.')
  if (reason?.trim()) act(job, 'projectit.parts.reject_parts', { lines, reason })
}
const stop = onRealtime('techy_work_order', () => !acting.value && load())
onMounted(load)
onBeforeUnmount(stop)
</script>
