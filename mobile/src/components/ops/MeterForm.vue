<template>
  <Modal :model-value="modelValue" :title="meter ? `Edit ${meter.meter_name}` : 'Add meter'" subtitle="Readings can raise jobs automatically." size="lg" @update:model-value="emit('update:modelValue', $event)">
    <form id="meter-form" class="space-y-4" @submit.prevent="save">
      <div v-if="!meter" class="flex flex-wrap gap-1.5" role="group" aria-label="Common meters">
        <button v-for="p in PRESETS" :key="p.meter_name" type="button" class="chip" @click="usePreset(p)">{{ p.meter_name }}</button>
      </div>
      <div class="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <div>
          <label class="label" for="meter-name">Meter</label>
          <input id="meter-name" v-model="form.meter_name" class="input" maxlength="80" placeholder="e.g. Running hours" required />
        </div>
        <div>
          <label class="label" for="meter-unit">Unit</label>
          <input id="meter-unit" v-model="form.unit" class="input" maxlength="20" placeholder="h, m³, ppm" required />
        </div>
      </div>
      <div>
        <span class="label">Type</span>
        <div class="segmented" role="group" aria-label="Meter type">
          <button v-for="t in TYPES" :key="t.value" type="button" :aria-pressed="form.meter_type === t.value" :disabled="locked" @click="setType(t.value)">{{ t.label }}</button>
        </div>
        <p class="mt-1 text-xs text-gray-500">{{ form.meter_type === 'Counter' ? 'Only goes up, like running hours or water produced.' : 'Goes up and down, like TDS or pressure.' }}<template v-if="locked"> The type can't change once there are readings.</template></p>
      </div>

      <fieldset class="space-y-2">
        <legend class="label">Raise a job when…</legend>
        <div v-for="(t, i) in form.triggers" :key="i" class="space-y-3 rounded-lg border border-gray-200 p-3">
          <div class="flex flex-wrap items-end gap-2">
            <div>
              <label class="label" :for="`t-type-${i}`">When</label>
              <select :id="`t-type-${i}`" v-model="t.trigger_type" class="input w-auto">
                <option v-if="form.meter_type === 'Counter'" value="Every">Every</option>
                <option value="Above">Goes above</option>
                <option value="Below">Goes below</option>
              </select>
            </div>
            <div>
              <label class="label" :for="`t-value-${i}`">{{ t.trigger_type === 'Every' ? 'Interval' : 'Limit' }}</label>
              <div class="relative w-32">
                <input :id="`t-value-${i}`" v-model="t.value" type="number" step="any" class="input pr-12" required />
                <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-gray-500">{{ form.unit }}</span>
              </div>
            </div>
            <div v-if="t.trigger_type === 'Every'">
              <label class="label" :for="`t-next-${i}`">Next due at</label>
              <input :id="`t-next-${i}`" v-model="t.next_due" type="number" step="any" class="input w-32" placeholder="Auto" />
            </div>
            <div>
              <label class="label" :for="`t-priority-${i}`">Priority</label>
              <select :id="`t-priority-${i}`" v-model="t.priority" class="input w-auto">
                <option v-for="p in ['Low', 'Medium', 'High', 'Urgent']" :key="p">{{ p }}</option>
              </select>
            </div>
            <button type="button" class="btn btn-ghost btn-icon ml-auto text-gray-400 hover:text-red-600" :aria-label="`Remove trigger ${i + 1}`" @click="form.triggers.splice(i, 1)"><FeatherIcon name="x" class="h-4 w-4" /></button>
          </div>
          <div class="grid gap-2 sm:grid-cols-2">
            <div>
              <label class="label" :for="`t-title-${i}`">Job title</label>
              <input :id="`t-title-${i}`" v-model="t.job_title" class="input" maxlength="140" :placeholder="t.trigger_type === 'Every' ? `${form.meter_name || 'Meter'} service` : `${form.meter_name || 'Meter'} ${t.trigger_type === 'Above' ? 'over' : 'under'} limit`" />
            </div>
            <div>
              <span class="label">Procedure</span>
              <ProcedureSelect v-model="t.procedure" :label="`Procedure for trigger ${i + 1}`" />
            </div>
          </div>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" :disabled="form.triggers.length >= 10" @click="addTrigger"><FeatherIcon name="plus" class="h-4 w-4" />Add trigger</button>
      </fieldset>

      <div>
        <label class="label" for="meter-notes">Notes</label>
        <textarea id="meter-notes" v-model="form.notes" class="input min-h-[4rem]" maxlength="1000" placeholder="Where to read it, normal range…" />
      </div>
      <label v-if="meter" class="flex items-center gap-2 text-sm"><input v-model="form.active" type="checkbox" class="rounded border-gray-300 text-brand-600" />In use</label>
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    </form>
    <template #footer>
      <button class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button class="btn btn-primary" form="meter-form" :disabled="busy">{{ meter ? 'Save' : 'Add meter' }}</button>
    </template>
  </Modal>
</template>
<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import ProcedureSelect from '@/components/ops/ProcedureSelect.vue'
import { api } from '@/data/ops'

const props = defineProps({ modelValue: Boolean, meter: Object, equipment: String, asset: String })
const emit = defineEmits(['update:modelValue', 'saved'])
const TYPES = [{ value: 'Counter', label: 'Counter' }, { value: 'Gauge', label: 'Gauge' }]
const PRESETS = [
  { meter_name: 'Running hours', unit: 'h', meter_type: 'Counter', triggers: [{ trigger_type: 'Every', value: 500, priority: 'Medium' }] },
  { meter_name: 'Product water', unit: 'm³', meter_type: 'Counter', triggers: [] },
  { meter_name: 'Permeate TDS', unit: 'ppm', meter_type: 'Gauge', triggers: [{ trigger_type: 'Above', value: 50, priority: 'High' }] },
  { meter_name: 'Feed pressure', unit: 'bar', meter_type: 'Gauge', triggers: [{ trigger_type: 'Above', value: 16, priority: 'High' }] },
  { meter_name: 'Filter pressure drop', unit: 'bar', meter_type: 'Gauge', triggers: [{ trigger_type: 'Above', value: 1, priority: 'Medium', job_title: 'Change cartridge filters' }] },
]
const blank = () => ({ meter_name: '', unit: '', meter_type: 'Counter', notes: '', active: true, triggers: [] })
const form = reactive(blank())
const busy = ref(false)
const error = ref('')
const locked = computed(() => !!props.meter && props.meter.last_reading !== null)

const row = (t = {}) => ({ name: t.name || null, trigger_type: t.trigger_type || 'Above', value: t.value ?? '', next_due: t.next_due ?? '', priority: t.priority || 'High', procedure: t.procedure || '', job_title: t.job_title || '' })
watch(() => props.modelValue, (open) => {
  if (!open) return
  error.value = ''
  const m = props.meter
  Object.assign(form, blank(), m ? { meter_name: m.meter_name, unit: m.unit, meter_type: m.meter_type, notes: m.notes || '', active: !!m.active, triggers: m.triggers.map(row) } : {})
})
function usePreset(p) {
  Object.assign(form, { meter_name: p.meter_name, unit: p.unit, meter_type: p.meter_type, triggers: p.triggers.map(row) })
}
function setType(t) {
  form.meter_type = t
  if (t === 'Gauge') for (const x of form.triggers) if (x.trigger_type === 'Every') x.trigger_type = 'Above'
}
const addTrigger = () => form.triggers.push(row(form.meter_type === 'Counter' ? { trigger_type: 'Every', priority: 'Medium' } : {}))

async function save() {
  busy.value = true
  error.value = ''
  try {
    const data = { ...form, active: form.active ? 1 : 0, equipment: props.equipment || null, asset: props.asset || null,
      triggers: form.triggers.map((t) => ({ ...t, next_due: t.trigger_type === 'Every' && t.next_due !== '' ? t.next_due : null })) }
    emit('saved', await api('projectit.meters.save_meter', { data, name: props.meter?.name || null }))
    emit('update:modelValue', false)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
