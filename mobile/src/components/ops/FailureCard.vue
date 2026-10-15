<template>
  <div id="failure" class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">Failure &amp; downtime</h2>
      <span v-if="f.missing.length" class="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">Needed to complete</span>
      <span v-else-if="f.machine_down && !f.down_to" class="rounded-md bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">Machine down</span>
    </div>
    <div class="space-y-4 p-5">
      <div class="grid gap-3 sm:grid-cols-3">
        <div v-for="k in KINDS" :key="k.key">
          <label class="label" :for="`code-${k.key}`">{{ k.label }}<span v-if="f.required && k.key !== 'remedy'" class="text-red-500"> *</span></label>
          <select :id="`code-${k.key}`" v-model="draft[k.key]" class="input" :class="f.missing.includes(k.kind) && !draft[k.key] ? 'border-amber-400' : ''" :disabled="!f.can_edit" @change="save({ [k.key]: draft[k.key] })">
            <option value="">{{ k.placeholder }}</option>
            <option v-if="f[k.key] && !codes[k.kind].some((c) => c.code === f[k.key].code)" :value="f[k.key].code">{{ f[k.key].title }}</option>
            <option v-for="c in codes[k.kind]" :key="c.code" :value="c.code">{{ c.title }}</option>
          </select>
        </div>
      </div>
      <p v-if="!loading && !codes.Problem.length" class="text-xs text-gray-500">No failure codes yet. A manager can add them from <router-link :to="{ name: 'OpsReports' }" class="font-medium text-brand-600 hover:underline">Reports</router-link>.</p>

      <div v-if="f.has_machine || f.machine_down" class="border-t border-gray-100 pt-4">
        <label class="flex items-center justify-between gap-3">
          <span><span class="block text-sm font-medium">Machine was down</span><span class="block text-xs text-gray-500">Out of service because of this problem. Counts towards its downtime.</span></span>
          <input v-model="draft.machine_down" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-red-600" :disabled="!f.can_edit" @change="save({ machine_down: draft.machine_down ? 1 : 0 })" />
        </label>
        <div v-if="draft.machine_down" class="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label class="label" for="down-from">Down from</label>
            <input id="down-from" v-model="draft.down_from" type="datetime-local" class="input w-auto" :max="nowLocal()" :disabled="!f.can_edit" @change="draft.down_from && save({ down_from: server(draft.down_from) })" />
          </div>
          <div>
            <label class="label" for="down-to">Back in service</label>
            <input id="down-to" v-model="draft.down_to" type="datetime-local" class="input w-auto" :max="nowLocal()" :disabled="!f.can_edit" @change="save({ down_to: draft.down_to ? server(draft.down_to) : '' })" />
          </div>
          <button v-if="!draft.down_to && f.can_edit" class="btn btn-secondary" :disabled="busy" @click="draft.down_to = nowLocal(); save({ down_to: server(draft.down_to) })"><FeatherIcon name="check" class="h-4 w-4" />Back in service now</button>
        </div>
        <p v-if="f.machine_down && f.down_hours !== null" class="mt-2 text-sm" :class="f.down_to ? 'text-gray-600' : 'font-medium text-red-700'">
          {{ f.down_to ? `Down for ${duration(f.down_hours)}.` : `Down for ${duration(f.down_hours)} so far. Completing the job puts it back in service.` }}
        </p>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { api, duration } from '@/data/ops'

const props = defineProps({ failure: { type: Object, required: true }, workOrder: { type: String, required: true } })
const emit = defineEmits(['updated', 'error'])
const f = computed(() => props.failure)
const KINDS = [
  { key: 'problem', kind: 'Problem', label: 'Problem', placeholder: 'What was wrong?' },
  { key: 'cause', kind: 'Cause', label: 'Cause', placeholder: 'Why did it happen?' },
  { key: 'remedy', kind: 'Remedy', label: 'Remedy', placeholder: 'What fixed it?' },
]
const codes = reactive({ Problem: [], Cause: [], Remedy: [] })
const loading = ref(true)
const busy = ref(false)

// Server times are the site's local time without a zone, like datetime-local inputs.
const local = (v) => (v ? String(v).slice(0, 16).replace(' ', 'T') : '')
const server = (v) => `${v.replace('T', ' ')}:00`
const pad = (n) => String(n).padStart(2, '0')
const nowLocal = () => {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// The inputs edit this copy; it follows the server only when no save is waiting, so a reply to an earlier save
// never puts an old value back into a field the person has just changed.
const draft = reactive({})
const fromServer = () => Object.assign(draft, { problem: f.value.problem?.code || '', cause: f.value.cause?.code || '',
  remedy: f.value.remedy?.code || '', machine_down: f.value.machine_down, down_from: local(f.value.down_from), down_to: local(f.value.down_to) })
fromServer()
let pending = 0
watch(() => props.failure, () => !pending && fromServer())

// One save at a time: two writes to the same job at once are refused by the database (a date picker can fire twice).
let queue = Promise.resolve()
function save(values) {
  pending += 1
  busy.value = true
  queue = queue.then(async () => {
    try {
      const result = await api('projectit.failures.set_failure', { work_order: props.workOrder, ...values })
      pending -= 1
      emit('updated', result)
    } catch (e) {
      pending -= 1
      emit('error', e.message)
      if (!pending) fromServer()
    } finally {
      busy.value = pending > 0
    }
  })
  return queue
}
onMounted(async () => {
  try {
    Object.assign(codes, await api('projectit.failures.options'))
  } catch (e) {
    emit('error', e.message)
  } finally {
    loading.value = false
  }
})
</script>
