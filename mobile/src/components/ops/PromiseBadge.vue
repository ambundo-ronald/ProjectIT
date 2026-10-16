<template>
  <span v-for="b in badges" :key="b.text" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold" :class="b.tone" :title="b.title">
    <FeatherIcon :name="b.icon" class="h-3 w-3" />{{ b.text }}
  </span>
</template>
<script setup>
// The response times a service contract promises on this repair: what is due next, or (on the job page) how
// the promises went once kept or missed.
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { now } from '@/data/ops'

const props = defineProps({ wo: { type: Object, required: true }, detail: Boolean, contract: String })

const ms = (v) => (v ? new Date(String(v).replace(' ', 'T')).getTime() : null)
function span(hours) {
  const mins = Math.round(hours * 60)
  if (mins < 60) return `${Math.max(1, mins)} min`
  if (hours < 48) return `${Math.round(hours * 10) / 10} h`
  return `${Math.round(hours / 2.4) / 10} days`
}
function at(t) {
  const d = new Date(t)
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return d.toDateString() === new Date(now.value).toDateString() ? time : `${d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })} ${time}`
}

const badges = computed(() => {
  const wo = props.wo
  if (wo.status === 'Cancelled' || !(wo.custom_respond_by || wo.custom_fix_by)) return []
  const t = now.value || Date.now()
  const done = wo.status === 'Completed'
  const title = props.contract ? `Promised in ${props.contract}` : 'Promised in the service contract'
  const result = []
  const due = (kind, by) => {
    const left = (by - t) / 3600000
    if (left < 0) return { text: `${kind} late by ${span(-left)}`, tone: 'bg-red-50 text-red-700', icon: 'alert-circle', title }
    if (left <= 1) return { text: `${kind} within ${span(left)}`, tone: 'bg-amber-50 text-amber-800', icon: 'clock', title }
    return { text: `${kind} by ${at(by)}`, tone: 'bg-brand-50 text-brand-700', icon: 'clock', title }
  }
  const kept = (kind, by, doneAt) => (doneAt <= by
    ? { text: `${kind} in time`, tone: 'bg-green-50 text-green-700', icon: 'check', title }
    : { text: `${kind} late by ${span((doneAt - by) / 3600000)}`, tone: 'bg-red-50 text-red-700', icon: 'x', title })
  const respondBy = ms(wo.custom_respond_by)
  const fixBy = ms(wo.custom_fix_by)
  const started = ms(wo.custom_started_at)
  if (respondBy && !started && !done) result.push(due('Respond', respondBy))
  else if (respondBy && started && props.detail) result.push(kept('Responded', respondBy, started))
  if (fixBy && !done && (started || props.detail)) result.push(due('Fix', fixBy))
  else if (fixBy && done && props.detail) result.push(kept('Fixed', fixBy, ms(wo.custom_completed_at || wo.modified)))
  return result
})
</script>
