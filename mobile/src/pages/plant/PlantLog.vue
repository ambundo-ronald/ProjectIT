<template>
  <div class="space-y-4">
    <!-- How logging is going -->
    <div v-if="form" class="card flex items-center gap-3 px-5 py-3" :class="form.status.due ? 'border-amber-200 bg-amber-50' : ''" role="status">
      <FeatherIcon :name="form.status.due ? 'clock' : 'check-circle'" class="h-5 w-5 shrink-0" :class="form.status.due ? 'text-amber-600' : 'text-green-600'" />
      <p class="min-w-0 flex-1 text-sm">
        <span class="font-semibold text-gray-900">{{ statusTitle }}</span>
        <span class="block text-xs text-gray-600">{{ statusText }}</span>
      </p>
    </div>

    <AdviceCard :items="advice" title="Some readings are out of range: what to do now" :phone="plant.me?.support_phone" dismissible @close="advice = []" />

    <div v-if="waiting.items.length || waiting.failed.length" class="card space-y-1 px-5 py-3 text-sm" role="status">
      <p v-if="waiting.items.length" class="flex items-center gap-2 text-amber-800">
        <FeatherIcon name="wifi-off" class="h-4 w-4 shrink-0" />{{ waiting.items.length }} log{{ waiting.items.length === 1 ? '' : 's' }} waiting to send. {{ online ? 'Sending…' : 'They send by themselves when you are back online.' }}
      </p>
      <p v-for="(f, i) in waiting.failed" :key="i" class="flex items-start gap-2 text-red-700"><FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" />A log from {{ formatDate(f.when) }} was not saved: {{ f.message }}</p>
    </div>

    <div v-if="!form && !error" class="h-64 animate-pulse rounded-2xl bg-gray-200/70" />
    <EmptyState v-else-if="error" icon="alert-circle" title="The log could not be loaded" :text="error" />
    <EmptyState v-else-if="!form.meters.length" icon="activity" title="Nothing to log on this machine yet" text="We set up the readings to log when we service it. Ask us if you need it sooner." />

    <!-- The log -->
    <form v-else class="card overflow-hidden" @submit.prevent="save()">
      <div class="card-header">
        <h2 class="card-title">New log</h2>
        <span class="text-xs text-gray-500">{{ machine?.equipment_name }}</span>
      </div>
      <div class="divide-y divide-gray-100">
        <div v-for="m in form.meters" :key="m.name" class="px-5 py-3">
          <label :for="`v-${m.name}`" class="flex items-baseline justify-between gap-3">
            <span class="text-sm font-medium text-gray-900">{{ m.meter_name }}<span v-if="!m.ro" class="ml-1 font-normal text-gray-500">(optional)</span></span>
            <span v-if="m.last !== null" class="shrink-0 text-xs text-gray-500">Last {{ num(m.last) }} {{ m.unit }} · {{ fromNow(m.last_on) }}</span>
          </label>
          <div class="relative mt-1.5">
            <input :id="`v-${m.name}`" v-model="values[m.name]" type="text" inputmode="decimal" autocomplete="off" class="input h-12 pr-20 text-[18px] tabular-nums" :class="flagged[m.name] ? 'border-amber-400 bg-amber-50' : ''" :aria-describedby="flagged[m.name] ? `w-${m.name}` : undefined" />
            <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-gray-500">{{ m.unit }}</span>
          </div>
          <p v-if="flagged[m.name]" :id="`w-${m.name}`" class="mt-1 flex items-start gap-1.5 text-xs text-amber-800"><FeatherIcon name="alert-triangle" class="mt-0.5 h-3.5 w-3.5 shrink-0" />{{ flagged[m.name] }}</p>
        </div>
        <div class="space-y-3 px-5 py-4">
          <div>
            <label class="label" for="log-note">Note <span class="font-normal text-gray-500">(optional)</span></label>
            <textarea id="log-note" v-model="note" rows="2" maxlength="500" class="input" placeholder="Anything unusual: a leak, a noise, an alarm, filters changed…" />
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <PhotoButtons camera-label="Photo of the gauges" :disabled="saving" @photos="(p) => (photo = p[0])" @error="(m) => (formError = m)" />
            <span v-if="photo" class="flex items-center gap-2">
              <img :src="photo.preview" alt="Photo to save with this log" class="h-12 w-12 rounded-lg object-cover" />
              <button type="button" class="btn btn-ghost btn-icon text-gray-500" aria-label="Remove the photo" @click="photo = null"><FeatherIcon name="x" class="h-4 w-4" /></button>
            </span>
          </div>
        </div>
      </div>
      <div class="space-y-2 border-t border-gray-100 bg-gray-50/60 px-5 py-4">
        <p v-if="formError" role="alert" class="text-sm text-red-600">{{ formError }}</p>
        <template v-if="Object.keys(flagged).length">
          <p class="text-sm text-amber-800">Some readings look unusual. Check them on the gauges: correct a typo, or save them as they are.</p>
          <div class="grid gap-2 sm:grid-cols-2">
            <button type="button" class="btn btn-secondary btn-lg" :disabled="saving" @click="flagged = {}">Let me correct them</button>
            <button type="button" class="btn btn-primary btn-lg" :disabled="saving" @click="save(1)">{{ saving ? 'Saving…' : 'They are right, save' }}</button>
          </div>
        </template>
        <button v-else type="submit" class="btn btn-primary btn-lg w-full" :disabled="saving || !filled"><FeatherIcon name="check" class="h-5 w-5" />{{ saving ? 'Saving…' : `Save log${filled ? ` (${filled} reading${filled === 1 ? '' : 's'})` : ''}` }}</button>
      </div>
    </form>

    <SuppliesCard v-if="plant.machine" :key="plant.machine" :equipment="plant.machine" plant />

    <!-- History -->
    <div v-if="form?.recent.length" class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Recent logs</h2><span class="text-xs text-gray-500">{{ form.recent.length }}</span></div>
      <ul class="divide-y divide-gray-100">
        <li v-for="l in form.recent" :key="l.name" class="px-5 py-3 text-sm">
          <div class="flex flex-wrap items-baseline justify-between gap-x-3">
            <span class="font-medium text-gray-900">{{ formatDateTime(l.log_on) }}</span>
            <span class="text-xs text-gray-500">{{ l.mine ? 'You' : l.by }}<template v-if="l.source === 'Technician'"> (our technician)</template><template v-if="l.edited_on"> · corrected</template></span>
          </div>
          <p class="mt-1 flex flex-wrap gap-1.5">
            <span v-for="r in l.readings" :key="r.meter" class="rounded px-1.5 py-0.5 text-xs tabular-nums" :class="r.unusual ? 'bg-amber-50 text-amber-800' : 'bg-gray-100 text-gray-700'" :title="r.unusual ? 'Marked as unusual' : undefined">{{ r.meter_name }} <b>{{ num(r.value) }}</b> {{ r.unit }}</span>
          </p>
          <p v-if="l.note" class="mt-1 whitespace-pre-wrap text-xs text-gray-600">{{ l.note }}</p>
          <div v-if="l.has_photo || l.can_fix" class="mt-1.5 flex gap-1.5">
            <button v-if="l.has_photo" class="btn btn-ghost btn-sm" @click="showPhoto(l)"><FeatherIcon name="image" class="h-4 w-4" />Photo</button>
            <button v-if="l.can_fix" class="btn btn-ghost btn-sm" @click="startFix(l)"><FeatherIcon name="edit-2" class="h-4 w-4" />Correct a typo</button>
          </div>
        </li>
      </ul>
    </div>

    <Modal :model-value="!!fixing" title="Correct this log" :subtitle="fixing ? formatDateTime(fixing.log_on) : ''" @update:model-value="fixing = null">
      <form v-if="fixing" id="fix-form" class="space-y-3" @submit.prevent="saveFix">
        <div v-for="r in fixing.readings" :key="r.meter">
          <label class="label" :for="`f-${r.meter}`">{{ r.meter_name }}</label>
          <div class="relative">
            <input :id="`f-${r.meter}`" v-model="fixing.values[r.meter]" type="text" inputmode="decimal" class="input pr-20 tabular-nums" required />
            <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-gray-500">{{ r.unit }}</span>
          </div>
        </div>
        <p class="hint">You can correct your own log for a day after saving it. We see that it was corrected.</p>
        <p v-if="fixError" role="alert" class="text-sm text-red-600">{{ fixError }}</p>
      </form>
      <template #footer>
        <button class="btn btn-secondary" type="button" @click="fixing = null">Cancel</button>
        <button class="btn btn-primary" type="submit" form="fix-form" :disabled="saving">{{ saving ? 'Saving…' : 'Save correction' }}</button>
      </template>
    </Modal>

    <Modal :model-value="!!photoUrl" title="Photo" @update:model-value="photoUrl = ''">
      <img v-if="photoUrl" :src="photoUrl" alt="Photo saved with the log" class="w-full rounded-lg" />
    </Modal>
  </div>
</template>
<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import Modal from '@/components/ops/Modal.vue'
import PhotoButtons from '@/components/ops/PhotoButtons.vue'
import AdviceCard from '@/components/plant/AdviceCard.vue'
import SuppliesCard from '@/components/ops/SuppliesCard.vue'
import { api, request, formatDate, fromNow } from '@/data/ops'
import { plant, machine, waiting, queueLog, sendWaiting } from '@/data/plant'

const form = ref(null)
const error = ref('')
const values = reactive({})
const note = ref('')
const photo = ref(null)
const saving = ref(false)
const formError = ref('')
const flagged = ref({}) // meter -> why it looks unusual
const advice = ref([]) // readings just logged that crossed a limit, and what to do
const fixing = ref(null)
const fixError = ref('')
const photoUrl = ref('')
const online = ref(navigator.onLine)

// The phone's local time as the server stores it (the site and its customers share a time zone).
const pad = (n) => String(n).padStart(2, '0')
function localStamp(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
const num = (v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
const formatDateTime = (v) => `${formatDate(v)} ${String(v).slice(11, 16)}`
const filled = computed(() => (form.value?.meters || []).filter((m) => String(values[m.name] ?? '').trim() !== '').length)
const SCHEDULE_TEXT = { Daily: 'once a day', 'Twice a day': 'twice a day', Weekly: 'once a week' }
const statusTitle = computed(() => {
  const s = form.value.status
  if (!s.expected) return 'No regular log is needed for this machine'
  if (s.due) return s.expected > 1 ? `Log ${s.done + 1} of ${s.expected} is due today` : s.schedule === 'Weekly' ? "This week's log is due" : "Today's log is due"
  return s.schedule === 'Weekly' ? "This week's log is done" : "Today's log is done"
})
const statusText = computed(() => {
  const s = form.value.status
  const last = s.last_on ? `Last log ${fromNow(s.last_on)}.` : 'No logs yet.'
  return s.expected ? `This machine is logged ${SCHEDULE_TEXT[s.schedule]}. ${last}` : last
})

async function load() {
  if (!plant.machine) return
  error.value = ''
  try {
    form.value = await api('projectit.plant.log_form', { equipment: plant.machine })
  } catch (e) {
    if (!form.value) error.value = e.message
  }
}
function reset() {
  for (const k of Object.keys(values)) delete values[k]
  note.value = ''
  photo.value = null
  flagged.value = {}
  formError.value = ''
}
watch(() => plant.machine, () => {
  form.value = null
  reset()
  load()
})

function entry() {
  const v = {}
  for (const m of form.value.meters) {
    const raw = String(values[m.name] ?? '').trim().replace(',', '.')
    if (raw !== '') v[m.name] = raw
  }
  return { equipment: plant.machine, values: v, note: note.value.trim() || null, photo: photo.value?.content || null, taken_on: localStamp() }
}

async function save(confirm = 0) {
  formError.value = ''
  const e = entry()
  const bad = Object.entries(e.values).filter(([, v]) => !Number.isFinite(Number(v)))
  if (bad.length) {
    formError.value = `Enter ${form.value.meters.find((m) => m.name === bad[0][0]).meter_name} as a number.`
    return
  }
  // taken_on is the phone's local time; the server only uses it for logs sent late, so send it only then.
  const payload = { ...e, taken_on: null, confirm }
  saving.value = true
  try {
    const r = await request('projectit.plant.save_log', payload)
    if (r.needs_confirm) {
      flagged.value = Object.fromEntries(r.warnings.map((w) => [w.meter, w.warning]))
      return
    }
    form.value.status = r.status
    form.value.recent.unshift(r.log)
    reset()
    advice.value = r.advice || []
    if (advice.value.length) window.scrollTo({ top: 0, behavior: 'smooth' })
    toast({ title: 'Log saved. Thank you!', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    load()
  } catch (err) {
    if (err.offline) {
      queueLog(e)
      reset()
      toast({ title: 'No signal: the log is saved on this phone and will send by itself.', icon: 'wifi-off', iconClasses: 'text-amber-600', position: 'top-center' })
    } else {
      formError.value = err.message
    }
  } finally {
    saving.value = false
  }
}

function startFix(l) {
  fixError.value = ''
  fixing.value = { name: l.name, log_on: l.log_on, readings: l.readings, values: Object.fromEntries(l.readings.map((r) => [r.meter, String(r.value)])) }
}
async function saveFix() {
  saving.value = true
  fixError.value = ''
  try {
    const r = await request('projectit.plant.fix_log', { log: fixing.value.name, values: fixing.value.values })
    const i = form.value.recent.findIndex((l) => l.name === r.log.name)
    if (i >= 0) form.value.recent[i] = r.log
    fixing.value = null
    toast({ title: r.changed ? 'Log corrected' : 'Nothing changed', icon: 'check', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (err) {
    fixError.value = err.message
  } finally {
    saving.value = false
  }
}
async function showPhoto(l) {
  try {
    photoUrl.value = (await request('projectit.plant.log_photo', { log: l.name })) || ''
  } catch (err) {
    toast({ title: err.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}

const setOnline = () => {
  online.value = navigator.onLine
  if (online.value) sendWaiting().then((n) => n && load())
}
onMounted(() => {
  load()
  window.addEventListener('online', setOnline)
  window.addEventListener('offline', setOnline)
  sendWaiting().then((n) => n && load())
})
onBeforeUnmount(() => {
  window.removeEventListener('online', setOnline)
  window.removeEventListener('offline', setOnline)
})
</script>
