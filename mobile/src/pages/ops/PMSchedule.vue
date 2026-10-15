<template>
  <section class="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
    <PageHeader title="Preventive maintenance" subtitle="Recurring work from ERPNext Asset Maintenance plans.">
      <router-link :to="{ name: 'OpsProcedures' }" class="btn btn-secondary"><FeatherIcon name="clipboard" class="h-4 w-4" />Procedures</router-link>
      <button v-if="manager" class="btn btn-primary" :disabled="busy" @click="run"><FeatherIcon name="zap" class="h-4 w-4" /><span class="hidden sm:inline">Create due work orders</span><span class="sm:hidden">Create due</span></button>
    </PageHeader>

    <div class="grid grid-cols-3 gap-3">
      <div v-for="s in stats" :key="s.label" class="card p-4">
        <p class="text-[24px] font-semibold" :class="s.tone">{{ s.value }}</p>
        <p class="mt-0.5 text-xs font-medium text-gray-500">{{ s.label }}</p>
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="segmented" role="group" aria-label="Window">
        <button v-for="d in [7, 30, 90]" :key="d" :aria-pressed="days === d" @click="days = d; load()">{{ d }} days</button>
      </div>
      <p class="text-xs text-gray-500">Work orders are created automatically {{ leadDays }} day{{ leadDays === 1 ? '' : 's' }} before they're due.</p>
    </div>

    <p v-if="notice" class="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800" role="status"><FeatherIcon name="check-circle" class="h-4 w-4" />{{ notice }}</p>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <ul v-if="logs.length" class="card divide-y divide-gray-100 overflow-hidden">
      <li v-for="log in logs" :key="log.name" class="flex items-center gap-3 px-4 py-3.5">
        <div class="flex w-14 shrink-0 flex-col items-center rounded-lg py-1.5" :class="tone(log).box">
          <span class="text-[10px] font-semibold uppercase">{{ month(log.due_date) }}</span>
          <span class="text-[18px] font-bold leading-none">{{ day(log.due_date) }}</span>
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate font-semibold">{{ log.task_name }}</p>
          <p class="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-gray-500">
            <router-link :to="{ name: 'OpsAsset', params: { name: log.asset_name } }" class="inline-flex items-center gap-1 hover:text-brand-700"><FeatherIcon name="box" class="h-3.5 w-3.5" />{{ log.asset_label || log.asset_name }}</router-link>
            <span>{{ log.periodicity }}</span>
            <span v-if="log.assign_to_name" class="inline-flex items-center gap-1"><FeatherIcon name="user" class="h-3.5 w-3.5" />{{ log.assign_to_name }}</span>
          </p>
          <div v-if="manager || log.procedure" class="mt-1.5 flex items-center gap-1.5 text-xs text-gray-600">
            <FeatherIcon name="clipboard" class="h-3.5 w-3.5 shrink-0 text-gray-400" />
            <ProcedureSelect v-if="manager" :model-value="log.procedure || ''" :label="`Procedure for ${log.task_name}`" placeholder="No procedure" class="h-7 w-auto min-w-0 max-w-[15rem] py-0 pl-2 pr-7 text-xs" @update:model-value="(v) => setProcedure(log, v)" />
            <span v-else class="truncate">{{ log.procedure_title }}</span>
          </div>
        </div>
        <div class="flex shrink-0 flex-col items-end gap-1">
          <span class="whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold" :class="tone(log).chip">{{ tone(log).text }}</span>
          <router-link v-if="log.work_order" :to="{ name: 'OpsWorkOrder', params: { name: log.work_order } }" class="text-xs font-medium text-brand-600 hover:underline">Work order →</router-link>
        </div>
      </li>
    </ul>
    <EmptyState v-else-if="!busy" icon="calendar" title="Nothing due in this window" text="Plans come from ERPNext Asset Maintenance. Try a longer window or add a plan to an asset." />
  </section>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import ProcedureSelect from '@/components/ops/ProcedureSelect.vue'
import { api, dueIn } from '@/data/ops'

const logs = ref([])
const days = ref(30)
const leadDays = ref(3)
const manager = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

const parse = (d) => new Date(`${d}T00:00:00`)
const month = (d) => parse(d).toLocaleDateString(undefined, { month: 'short' })
const day = (d) => parse(d).getDate()
function tone(log) {
  const d = dueIn(log.due_date)
  if (d < 0) return { text: `${-d}d overdue`, chip: 'bg-red-50 text-red-700', box: 'bg-red-50 text-red-700' }
  if (d === 0) return { text: 'Due today', chip: 'bg-amber-50 text-amber-800', box: 'bg-amber-50 text-amber-800' }
  if (d <= leadDays.value) return { text: `In ${d}d`, chip: 'bg-amber-50 text-amber-800', box: 'bg-amber-50 text-amber-800' }
  return { text: `In ${d}d`, chip: 'bg-gray-100 text-gray-600', box: 'bg-gray-100 text-gray-700' }
}
const stats = computed(() => [
  { label: 'Overdue', value: logs.value.filter((l) => dueIn(l.due_date) < 0).length, tone: 'text-red-600' },
  { label: `Due in ${leadDays.value} days`, value: logs.value.filter((l) => dueIn(l.due_date) >= 0 && dueIn(l.due_date) <= leadDays.value).length, tone: 'text-amber-600' },
  { label: `Next ${days.value} days`, value: logs.value.length, tone: 'text-gray-900' },
])

async function load() {
  busy.value = true
  error.value = ''
  try {
    const data = await api('projectit.maintenance.pm_schedule', { days: days.value })
    logs.value = data.logs
    leadDays.value = data.lead_days
    manager.value = data.manager
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function run() {
  busy.value = true
  notice.value = ''
  try {
    const { created } = await api('projectit.maintenance.run_pm_now')
    notice.value = created.length ? `Created ${created.length} work order${created.length === 1 ? '' : 's'}.` : 'Nothing new was due — all set.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
  await load()
}

async function setProcedure(log, procedure) {
  error.value = ''
  try {
    await api('projectit.maintenance.set_task_procedure', { task: log.task, procedure: procedure || null })
    for (const l of logs.value) if (l.task === log.task) l.procedure = procedure || null
    notice.value = procedure ? `New work orders for “${log.task_name}” will include this procedure.` : `Procedure removed from “${log.task_name}”.`
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>
