<template>
  <router-link
    :to="{ name: 'OpsWorkOrder', params: { name: wo.name } }"
    class="group relative block overflow-hidden rounded-xl border border-gray-200 bg-panel p-3.5 pl-4 shadow-card transition hover:-translate-y-px hover:border-gray-300 hover:shadow-pop"
  >
    <span class="absolute inset-y-0 left-0 w-1" :class="stripe" aria-hidden="true" />
    <div class="flex items-start gap-2">
      <p class="min-w-0 flex-1 font-semibold leading-snug text-gray-900 group-hover:text-brand-700" :class="done ? 'text-gray-500' : ''">{{ wo.subject }}</p>
      <StatusPill v-if="showStatus" :status="overdue ? 'Overdue' : displayStatus(wo)" />
    </div>
    <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-gray-500">
      <PriorityFlag :priority="wo.priority" />
      <span v-if="wo.equipment" class="inline-flex min-w-0 items-center gap-1"><FeatherIcon name="droplet" class="h-3.5 w-3.5 shrink-0" /><span class="truncate">{{ wo.equipment.customer_name }}<template v-if="wo.equipment.site"> · {{ wo.equipment.site }}</template></span></span>
      <span v-else-if="wo.custom_asset" class="inline-flex min-w-0 items-center gap-1"><FeatherIcon name="box" class="h-3.5 w-3.5 shrink-0" /><span class="truncate">{{ wo.asset_name || wo.custom_asset }}</span></span>
      <span v-else-if="wo.custom_location" class="inline-flex items-center gap-1"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />{{ wo.custom_location }}</span>
      <span v-if="wo.custom_work_category === 'Preventive'" class="inline-flex items-center gap-1 text-accent-600"><FeatherIcon name="repeat" class="h-3.5 w-3.5" />PM</span>
      <span v-else-if="wo.custom_work_category === 'Installation'" class="inline-flex items-center gap-1 text-violet-700"><FeatherIcon name="truck" class="h-3.5 w-3.5" />Install</span>
      <CoverageBadge v-if="wo.equipment && !done" :kind="wo.equipment.coverage" short />
    </div>
    <div v-if="wo.is_group" class="mt-2.5 flex items-center gap-2">
      <div class="h-1.5 flex-1 rounded-full bg-gray-100"><div class="h-1.5 rounded-full bg-green-500" :style="{ width: `${Math.round(wo.progress || 0)}%` }" /></div>
      <span class="text-[11px] font-medium text-gray-500">{{ Math.round(wo.progress || 0) }}%</span>
    </div>
    <div class="mt-3 flex items-center justify-between gap-2">
      <AvatarStack :people="wo.assignees || []" />
      <PromiseBadge :wo="wo" class="ml-auto" />
      <span v-if="wo.exp_end_date && !done" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold" :class="overdue ? 'bg-red-50 text-red-700' : dueSoon ? 'bg-amber-50 text-amber-800' : 'bg-gray-100 text-gray-600'">
        <FeatherIcon name="clock" class="h-3 w-3" />{{ dueLabel }}
      </span>
      <span v-else-if="done" class="text-[11px] text-gray-400">Done {{ fromNow(wo.modified) }}</span>
    </div>
  </router-link>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import StatusPill from './StatusPill.vue'
import PriorityFlag from './PriorityFlag.vue'
import PromiseBadge from './PromiseBadge.vue'
import AvatarStack from './AvatarStack.vue'
import CoverageBadge from './CoverageBadge.vue'
import { displayStatus, dueIn, fromNow, isOverdue } from '@/data/ops'

const props = defineProps({ wo: Object, showStatus: Boolean })
const done = computed(() => ['Completed', 'Cancelled'].includes(props.wo.status))
const overdue = computed(() => !done.value && (props.wo.status === 'Overdue' || isOverdue(props.wo)))
const days = computed(() => dueIn(props.wo.exp_end_date))
const dueSoon = computed(() => days.value !== null && days.value <= 1)
const dueLabel = computed(() => {
  const d = days.value
  if (d === null) return ''
  if (d < 0) return `${-d}d overdue`
  if (d === 0) return 'Due today'
  if (d === 1) return 'Tomorrow'
  return `In ${d}d`
})
const stripe = computed(() => (done.value ? 'bg-gray-200' : { Urgent: 'bg-red-500', High: 'bg-orange-400', Medium: 'bg-brand-400', Low: 'bg-gray-300' }[props.wo.priority] || 'bg-gray-300'))
</script>
