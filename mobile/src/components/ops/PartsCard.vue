<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <div>
        <h2 class="card-title">Parts</h2>
        <p v-if="parts.pending" class="mt-0.5 text-xs font-medium text-amber-700">{{ parts.pending }} waiting for approval</p>
      </div>
      <button v-if="parts.can_edit" class="btn btn-secondary btn-sm" :disabled="busy" @click="picking = true"><FeatherIcon name="plus" class="h-4 w-4" />Add part</button>
    </div>
    <ul v-if="parts.rows.length" class="divide-y divide-gray-100">
      <li v-for="r in parts.rows" :key="r.name" class="flex items-start gap-3 px-5 py-3" :class="r.status === 'Rejected' ? 'bg-red-50/40' : ''">
        <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="STATUS[r.status].icon"><FeatherIcon :name="STATUS[r.status].glyph" class="h-4 w-4" /></span>
        <div class="min-w-0 flex-1">
          <div class="flex items-start justify-between gap-3">
            <p class="min-w-0 text-[15px] font-medium leading-snug" :class="r.status === 'Rejected' ? 'text-gray-500 line-through decoration-gray-300' : ''">{{ fmt(r.qty) }} × {{ r.item_name || r.item_code }}</p>
            <span v-if="r.billing === 'Chargeable' && r.status !== 'Rejected'" class="shrink-0 text-sm font-semibold tabular-nums">{{ money(r.amount) }}</span>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
            <span class="rounded-md px-1.5 py-0.5 font-semibold" :class="STATUS[r.status].chip">{{ STATUS[r.status].label }}</span>
            <select v-if="parts.manager && r.status !== 'Rejected'" :value="r.billing" class="input h-7 w-auto py-0 pl-2 pr-7 text-xs font-semibold" :class="BILLING[r.billing].tone" :aria-label="`Billing for ${r.item_name}`" :disabled="busy" @change="setBilling(r, $event.target.value)">
              <option v-for="(b, key) in BILLING" :key="key" :value="key">{{ b.label }}</option>
            </select>
            <span v-else-if="r.status !== 'Rejected'" class="rounded-md px-1.5 py-0.5 font-semibold" :class="BILLING[r.billing].tone">{{ BILLING[r.billing].label }}</span>
            <span class="truncate">{{ r.warehouse }}</span>
            <span v-if="['Draft', 'Requested'].includes(r.status)" :class="r.in_stock >= r.qty ? 'text-green-700' : 'font-semibold text-red-600'">{{ fmt(r.in_stock) }} in stock</span>
            <a v-if="r.material_request" :href="`/desk/material-request/${r.material_request}`" target="_blank" rel="noopener" class="link">{{ r.material_request }}</a>
          </div>
          <p v-if="r.status === 'Rejected' && r.rejection_reason" class="mt-1 text-xs text-red-700">Rejected: {{ r.rejection_reason }}</p>
          <div v-if="r.status === 'Requested' && parts.can_approve" class="mt-2 flex gap-2">
            <button class="btn btn-success btn-sm" :disabled="busy" @click="approve([r.name])"><FeatherIcon name="check" class="h-4 w-4" />Approve</button>
            <button class="btn btn-secondary btn-sm" :disabled="busy" @click="reject([r.name])">Reject</button>
          </div>
        </div>
        <button v-if="parts.can_edit && ['Draft', 'Requested', 'Rejected'].includes(r.status)" class="btn btn-ghost btn-icon btn-sm -mr-2 shrink-0 text-gray-400 hover:text-red-600" :aria-label="`Remove ${r.item_name}`" :disabled="busy" @click="remove(r)"><FeatherIcon name="x" class="h-4 w-4" /></button>
      </li>
    </ul>
    <p v-else class="px-5 py-4 text-sm text-gray-500">{{ parts.can_edit ? 'List the parts you need, then request approval. A manager or stock manager approves them into a Material Request.' : 'No parts on this job.' }}</p>

    <div v-if="parts.drafts && parts.can_edit" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 bg-brand-50/50 px-5 py-3">
      <span class="text-sm text-gray-700">{{ parts.drafts }} part{{ parts.drafts === 1 ? '' : 's' }} not sent yet</span>
      <button class="btn btn-primary btn-sm" :disabled="busy" @click="call('projectit.parts.request_approval', {})"><FeatherIcon name="send" class="h-4 w-4" />Request approval</button>
    </div>
    <div v-if="parts.pending > 1 && parts.can_approve" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 bg-amber-50/60 px-5 py-3">
      <span class="text-sm text-amber-800">{{ parts.pending }} parts waiting for your approval</span>
      <button class="btn btn-success btn-sm" :disabled="busy" @click="approve(null)"><FeatherIcon name="check-circle" class="h-4 w-4" />Approve all</button>
    </div>
    <div v-if="parts.chargeable_total || (parts.manager && parts.cost_total)" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 bg-gray-50/70 px-5 py-3 text-sm">
      <span class="text-gray-600">Approved parts to charge<span v-if="parts.manager" class="text-xs text-gray-400"> · cost {{ money(parts.cost_total) }}</span></span>
      <span class="text-[15px] font-semibold tabular-nums">{{ money(parts.chargeable_total) }}</span>
    </div>
    <PartPicker v-model="picking" :work-order="workOrder" :default-warehouse="parts.default_warehouse" @added="(r) => emit('updated', r)" />
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import PartPicker from './PartPicker.vue'
import { api } from '@/data/ops'

const props = defineProps({ parts: { type: Object, required: true }, workOrder: String })
const emit = defineEmits(['updated', 'error', 'reload'])
const picking = ref(false)
const busy = ref(false)

const STATUS = {
  Draft: { label: 'Not sent', chip: 'bg-gray-100 text-gray-600', icon: 'bg-gray-100 text-gray-500', glyph: 'package' },
  Requested: { label: 'Waiting approval', chip: 'bg-amber-50 text-amber-800', icon: 'bg-amber-50 text-amber-700', glyph: 'clock' },
  Approved: { label: 'Approved', chip: 'bg-green-50 text-green-700', icon: 'bg-green-50 text-green-700', glyph: 'check' },
  Issued: { label: 'Issued', chip: 'bg-brand-50 text-brand-700', icon: 'bg-brand-50 text-brand-700', glyph: 'package' },
  Rejected: { label: 'Rejected', chip: 'bg-red-50 text-red-700', icon: 'bg-red-50 text-red-600', glyph: 'x' },
}
const BILLING = {
  Chargeable: { label: 'Chargeable', tone: 'bg-amber-50 text-amber-800' },
  Contract: { label: 'Contract', tone: 'bg-brand-50 text-brand-700' },
  Warranty: { label: 'Warranty', tone: 'bg-green-50 text-green-700' },
  Internal: { label: 'Internal', tone: 'bg-gray-100 text-gray-600' },
  'No charge': { label: 'No charge', tone: 'bg-gray-100 text-gray-600' },
}
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
const money = (n) => {
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency: props.parts.currency || 'KES', maximumFractionDigits: 0 })
  } catch (e) {
    return `${props.parts.currency || ''} ${fmt(n)}`
  }
}

async function call(method, args) {
  busy.value = true
  try {
    emit('updated', await api(method, { work_order: props.workOrder, ...args }))
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
const remove = (r) => call('projectit.parts.remove_part', { name: r.name })
const setBilling = (r, billing) => call('projectit.parts.set_billing', { name: r.name, billing })

async function approve(lines) {
  busy.value = true
  try {
    const r = await api('projectit.parts.approve_parts', { work_order: props.workOrder, lines })
    toast({ title: `Approved · ${r.material_requests.join(', ')}`, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    r.job ? emit('updated', r.job) : emit('reload')
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
async function reject(lines) {
  const reason = window.prompt('Why are these parts rejected? The technician sees this.')
  if (!reason?.trim()) return
  busy.value = true
  try {
    const r = await api('projectit.parts.reject_parts', { work_order: props.workOrder, lines, reason })
    r.job ? emit('updated', r.job) : emit('reload')
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
</script>
