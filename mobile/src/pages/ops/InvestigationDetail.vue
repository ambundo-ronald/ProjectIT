<template>
  <section class="mx-auto max-w-6xl p-4 md:p-8" :class="d?.can_edit ? 'pb-40 md:pb-28' : ''">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsInvestigations' }" class="hover:text-gray-800">Investigations</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="truncate text-gray-800">{{ form.title || route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="loading" class="space-y-4"><div class="h-32 animate-pulse rounded-xl bg-gray-200/70" /><div class="h-64 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <div v-else-if="d" class="space-y-5">
      <!-- Problem -->
      <div class="card space-y-4 p-5">
        <div>
          <div class="flex items-center justify-between gap-3">
            <label class="section-label" for="inv-title">{{ d.investigation.name }} · Problem</label>
            <span class="shrink-0 rounded-md px-2 py-1 text-xs font-semibold" :class="d.investigation.status === 'Closed' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-800'">
              {{ d.investigation.status === 'Closed' ? `Closed ${formatDate(d.investigation.closed_on)}` : 'Open' }}
            </span>
          </div>
          <input id="inv-title" v-model="form.title" :disabled="!d.can_edit" maxlength="140" class="input mt-1 text-[17px] font-semibold" placeholder="e.g. Excessive chlorine residual" />
        </div>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div><label class="label" for="inv-actual">Actual</label><input id="inv-actual" v-model="form.actual" :disabled="!d.can_edit" maxlength="60" class="input" placeholder="e.g. 10 mg/L" /></div>
          <div><label class="label" for="inv-target">Target</label><input id="inv-target" v-model="form.target" :disabled="!d.can_edit" maxlength="60" class="input" placeholder="e.g. 0.5 mg/L" /></div>
          <div><label class="label" for="inv-on">Site investigation</label><input id="inv-on" v-model="form.investigated_on" type="date" :disabled="!d.can_edit" class="input" /></div>
          <div><label class="label" for="inv-follow">Follow-up</label><input id="inv-follow" v-model="form.follow_up_on" type="date" :disabled="!d.can_edit" class="input" /></div>
          <div class="sm:col-span-2">
            <label class="label">Machine</label>
            <EquipmentPicker v-if="d.can_edit && !form.asset" v-model="form.equipment" :label="machineLabel" @picked="pickMachine" />
            <p v-else-if="d.machine" class="text-sm"><router-link :to="machineLink" class="font-medium text-brand-700 hover:underline">{{ d.machine.label }}</router-link><span class="text-gray-500"> · {{ d.machine.detail }}</span></p>
            <p v-else class="text-sm text-gray-500">None</p>
          </div>
          <div><label class="label" for="inv-site">Site</label><input id="inv-site" v-model="form.site" :disabled="!d.can_edit" maxlength="140" class="input" placeholder="e.g. Karen" /></div>
          <div>
            <p class="label">Customer</p>
            <p class="text-sm">{{ customerName || '—' }}</p>
          </div>
        </div>
        <p class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
          <span v-if="d.job">From job <router-link :to="{ name: 'OpsWorkOrder', params: { name: d.job.name } }" class="font-medium text-brand-600 hover:underline">{{ d.job.subject }}</router-link></span>
          <span v-if="form.prepared_by">Prepared by {{ d.people[form.prepared_by] || form.prepared_by }}</span>
          <span v-if="d.investigation.closed_by">Closed by {{ d.people[d.investigation.closed_by] }}</span>
        </p>
        <div class="grid gap-4 md:grid-cols-2">
          <div><label class="label" for="inv-problem">What happened</label><textarea id="inv-problem" v-model="form.problem" :disabled="!d.can_edit" rows="3" maxlength="4000" class="input" placeholder="What was seen, measured or reported, and when." /></div>
          <div><label class="label" for="inv-focus">RCA focus</label><textarea id="inv-focus" v-model="form.focus" :disabled="!d.can_edit" rows="3" maxlength="1000" class="input" placeholder="What the investigation sets out to verify, e.g. SOP, dose calculation, plumbing design." /></div>
        </div>
      </div>

      <div v-if="d.gaps.length" class="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
        <FeatherIcon name="info" class="mt-0.5 h-4 w-4 shrink-0" />
        <span><b>Before it can be closed:</b> {{ d.gaps.join(' ') }}</span>
      </div>

      <!-- Fishbone -->
      <div class="card overflow-hidden">
        <div class="card-header flex-wrap gap-2">
          <h2 class="card-title">Fishbone diagram</h2>
          <span class="text-xs text-gray-500">{{ dirty ? 'Save to redraw it with your changes' : 'Drawn from the causes below' }}</span>
        </div>
        <div class="overflow-x-auto p-3"><div class="fishbone min-w-[56rem]" v-html="d.fishbone" /></div>
      </div>

      <!-- Causes -->
      <div class="card overflow-hidden">
        <div class="card-header flex-wrap gap-2">
          <h2 class="card-title">Causes and evidence (6M)</h2>
          <span class="text-xs text-gray-500">{{ form.causes.length }} cause{{ form.causes.length === 1 ? '' : 's' }} · {{ actionsDone }} of {{ actionsTotal }} actions done</span>
        </div>
        <div class="divide-y divide-gray-100">
          <div v-for="m in d.options.categories" :key="m" class="px-5 py-4">
            <div class="mb-2 flex items-center justify-between gap-2">
              <h3 class="flex items-center gap-2 text-sm font-semibold"><span class="h-3 w-3 rounded-sm" :style="{ background: COLOURS[m] }" />{{ m }}<span class="font-normal text-gray-400">{{ byCategory(m).length || '' }}</span></h3>
              <button v-if="d.can_edit" class="btn btn-ghost btn-sm" @click="addCause(m)"><FeatherIcon name="plus" class="h-4 w-4" />Add cause</button>
            </div>
            <p v-if="!byCategory(m).length" class="text-sm text-gray-400">None recorded.</p>
            <ul class="space-y-2">
              <li v-for="c in byCategory(m)" :key="c._key" class="rounded-lg border border-gray-200" :style="{ borderLeft: `4px solid ${COLOURS[m]}` }">
                <button type="button" class="flex w-full items-start gap-3 px-3 py-2.5 text-left" :aria-expanded="editing === c._key" @click="editing = editing === c._key ? '' : c._key">
                  <span class="min-w-0 flex-1">
                    <span class="block text-sm font-medium" :class="!c.cause && 'italic text-gray-400'">{{ c.cause || 'New cause' }}</span>
                    <span class="mt-0.5 block truncate text-xs text-gray-500"><template v-if="c.evidence">{{ c.evidence }}</template><template v-else>No evidence yet</template></span>
                  </span>
                  <span class="flex shrink-0 flex-col items-end gap-1">
                    <span class="rounded px-1.5 text-[11px] font-semibold" :class="STATUS_TONE[c.status]">{{ c.status }}</span>
                    <span v-if="c.action" class="text-[11px]" :class="c.done ? 'text-green-700' : 'text-gray-500'">{{ c.done ? 'Action done' : c.due_date ? `Action due ${formatDate(c.due_date)}` : 'Action open' }}</span>
                  </span>
                </button>
                <div v-if="editing === c._key" class="grid gap-3 border-t border-gray-100 p-3 sm:grid-cols-2">
                  <div class="sm:col-span-2"><label class="label" :for="`c-${c._key}-cause`">Cause / failure</label><textarea :id="`c-${c._key}-cause`" v-model="c.cause" :disabled="!d.can_edit" rows="2" maxlength="300" class="input" /></div>
                  <div><label class="label" :for="`c-${c._key}-ev`">Evidence</label><textarea :id="`c-${c._key}-ev`" v-model="c.evidence" :disabled="!d.can_edit" rows="2" maxlength="1000" class="input" placeholder="Where it comes from, e.g. 9 Sep site report" /></div>
                  <div><label class="label" :for="`c-${c._key}-avr`">Actual vs required</label><textarea :id="`c-${c._key}-avr`" v-model="c.actual_vs_required" :disabled="!d.can_edit" rows="2" maxlength="300" class="input" placeholder="e.g. 10 mg/L / 0.5 mg/L target" /></div>
                  <div class="grid grid-cols-2 gap-3 sm:col-span-2 lg:grid-cols-4">
                    <div><label class="label" :for="`c-${c._key}-cat`">6M</label><select :id="`c-${c._key}-cat`" v-model="c.category" :disabled="!d.can_edit" class="input"><option v-for="o in d.options.categories" :key="o">{{ o }}</option></select></div>
                    <div><label class="label" :for="`c-${c._key}-st`">Status</label><select :id="`c-${c._key}-st`" v-model="c.status" :disabled="!d.can_edit" class="input"><option v-for="o in d.options.statuses" :key="o">{{ o }}</option></select></div>
                    <div><label class="label" :for="`c-${c._key}-own`">Owner</label><input :id="`c-${c._key}-own`" v-model="c.owner_name" :disabled="!d.can_edit" maxlength="140" class="input" placeholder="e.g. Engineering / QC" /></div>
                    <div><label class="label" :for="`c-${c._key}-due`">Due</label><input :id="`c-${c._key}-due`" v-model="c.due_date" type="date" :disabled="!d.can_edit" class="input" /></div>
                  </div>
                  <div><label class="label" :for="`c-${c._key}-act`">Corrective / preventive action</label><textarea :id="`c-${c._key}-act`" v-model="c.action" :disabled="!d.can_edit" rows="2" maxlength="1000" class="input" /></div>
                  <div><label class="label" :for="`c-${c._key}-clo`">Closure evidence</label><textarea :id="`c-${c._key}-clo`" v-model="c.closure_evidence" :disabled="!d.can_edit" rows="2" maxlength="1000" class="input" placeholder="What shows it's done, e.g. signed SOP and training record" /></div>
                  <div class="flex flex-wrap items-center justify-between gap-2 sm:col-span-2">
                    <label class="flex items-center gap-2 text-sm"><input v-model="c.done" type="checkbox" :true-value="1" :false-value="0" :disabled="!d.can_edit || !c.action" class="h-4 w-4 rounded border-gray-300" />Action done<span v-if="c.done && c.done_by" class="text-xs text-gray-500">· {{ formatDate(c.done_on) }}</span></label>
                    <button v-if="d.can_edit" type="button" class="btn btn-ghost btn-sm text-red-600" @click="removeCause(c)"><FeatherIcon name="trash-2" class="h-4 w-4" />Remove</button>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 5 Whys -->
      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">5 Whys</h2><button v-if="d.can_edit && form.whys.length < 7" class="btn btn-ghost btn-sm" @click="addWhy"><FeatherIcon name="plus" class="h-4 w-4" />Add why</button></div>
        <ol class="space-y-3 p-5">
          <li v-for="(w, i) in form.whys" :key="w._key" class="rounded-lg border border-gray-200 p-3" :style="{ borderTop: `4px solid ${WHY_COLOURS[i % WHY_COLOURS.length]}` }">
            <div class="mb-2 flex items-center justify-between"><p class="text-sm font-bold">Why {{ i + 1 }}?</p><button v-if="d.can_edit" type="button" class="btn btn-ghost btn-sm text-red-600" :aria-label="`Remove why ${i + 1}`" @click="form.whys.splice(i, 1)"><FeatherIcon name="x" class="h-4 w-4" /></button></div>
            <div class="grid gap-3 md:grid-cols-3">
              <div><label class="label" :for="`w-${w._key}-q`">Question</label><textarea :id="`w-${w._key}-q`" v-model="w.question" :disabled="!d.can_edit" rows="3" maxlength="300" class="input" :placeholder="i === 0 ? 'Why was the treated water over-chlorinated?' : 'Why did that happen?'" /></div>
              <div><label class="label" :for="`w-${w._key}-a`">Answer</label><textarea :id="`w-${w._key}-a`" v-model="w.answer" :disabled="!d.can_edit" rows="3" maxlength="1000" class="input" /></div>
              <div><label class="label" :for="`w-${w._key}-e`">Evidence <span class="font-normal text-gray-400">(one per line)</span></label><textarea :id="`w-${w._key}-e`" v-model="w.evidence" :disabled="!d.can_edit" rows="3" maxlength="1500" class="input" /></div>
            </div>
          </li>
          <li v-if="!form.whys.length" class="text-sm text-gray-500">Ask why the problem happened, then why that happened, until you reach something you can fix for good.</li>
        </ol>
      </div>

      <!-- Conclusion -->
      <div class="card grid gap-4 p-5 md:grid-cols-2">
        <div><label class="label" for="inv-root">Root cause</label><textarea id="inv-root" v-model="form.root_cause" :disabled="!d.can_edit" rows="4" maxlength="2000" class="input" /></div>
        <div><label class="label" for="inv-factors">Contributing factors <span class="font-normal text-gray-400">(one per line)</span></label><textarea id="inv-factors" v-model="form.contributing_factors" :disabled="!d.can_edit" rows="4" maxlength="2000" class="input" /></div>
        <div class="md:col-span-2"><label class="label" for="inv-closure">Closure requirements</label><textarea id="inv-closure" v-model="form.closure_requirements" :disabled="!d.can_edit" rows="3" maxlength="2000" class="input" placeholder="What must be in place before this is closed." /></div>
      </div>

      <!-- Machine history -->
      <div v-if="d.history.length" class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Recent jobs on this machine</h2><span class="text-xs text-gray-500">Evidence you can draw on</span></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="j in d.history" :key="j.name">
            <router-link :to="{ name: 'OpsWorkOrder', params: { name: j.name } }" class="flex items-center gap-3 px-5 py-2.5 text-sm hover:bg-gray-50">
              <span class="w-20 shrink-0 text-xs tabular-nums text-gray-500">{{ formatDate(j.creation) }}</span>
              <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ j.subject }}</span><span v-if="j.problem || j.cause" class="block truncate text-xs text-gray-500">{{ [j.problem, j.cause].filter(Boolean).join(' · ') }}</span></span>
              <span class="shrink-0 text-xs text-gray-500">{{ j.custom_work_category }} · {{ j.status }}</span>
            </router-link>
          </li>
        </ul>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <a :href="pdfUrl" target="_blank" rel="noopener" class="btn btn-secondary" :class="dirty && 'pointer-events-none opacity-50'" :aria-disabled="dirty" :title="dirty ? 'Save your changes first' : ''"><FeatherIcon name="download" class="h-4 w-4" />PDF report</a>
        <button v-if="d.can_close" class="btn btn-secondary" :disabled="busy || dirty || d.gaps.length > 0" :title="d.gaps.join(' ')" @click="act('close')"><FeatherIcon name="check-circle" class="h-4 w-4" />Close investigation</button>
        <button v-if="d.can_reopen" class="btn btn-secondary" :disabled="busy" @click="act('reopen')"><FeatherIcon name="rotate-ccw" class="h-4 w-4" />Reopen</button>
        <button v-if="d.can_delete" class="btn btn-ghost ml-auto text-red-600" :disabled="busy" @click="remove"><FeatherIcon name="trash-2" class="h-4 w-4" />Delete</button>
      </div>
    </div>

    <div v-if="d?.can_edit && !loading" class="fixed inset-x-0 bottom-16 z-30 border-t border-gray-200 bg-panel/95 backdrop-blur md:bottom-0 md:left-64">
      <div class="mx-auto flex max-w-6xl items-center gap-2 p-3 md:pl-8 md:pr-24">
        <span class="text-sm" :class="dirty ? 'font-medium text-amber-700' : 'text-gray-500'">{{ dirty ? 'Unsaved changes' : saved ? 'All changes saved' : '' }}</span>
        <button type="button" class="btn btn-primary ml-auto" :disabled="busy || !dirty || !form.title.trim()" @click="save"><FeatherIcon name="check" class="h-4 w-4" />{{ busy ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import EquipmentPicker from '@/components/ops/EquipmentPicker.vue'
import { api, formatDate } from '@/data/ops'

const COLOURS = { Method: '#2563eb', Machine: '#059669', Material: '#d97706', Manpower: '#ea580c', Measurement: '#7c3aed', Management: '#0d9488' }
const WHY_COLOURS = ['#2563eb', '#059669', '#d97706', '#ea580c', '#dc2626', '#7c3aed', '#0d9488']
const STATUS_TONE = { Confirmed: 'bg-green-100 text-green-800', Reported: 'bg-blue-100 text-blue-800', Potential: 'bg-amber-100 text-amber-800', Open: 'bg-gray-200 text-gray-700' }
const HEADER = ['title', 'actual', 'target', 'customer', 'site', 'equipment', 'asset', 'work_order', 'investigated_on', 'follow_up_on', 'prepared_by', 'problem', 'focus', 'root_cause', 'contributing_factors', 'closure_requirements']

const route = useRoute()
const router = useRouter()
const d = ref(null)
const form = ref({ title: '', causes: [], whys: [] })
const snapshot = ref('')
const loading = ref(true)
const busy = ref(false)
const saved = ref(false)
const error = ref('')
const editing = ref('')
const machineLabel = ref('')
const customerName = ref('')
let seq = 0
const key = () => `k${++seq}`

const payload = () => JSON.stringify({ ...Object.fromEntries(HEADER.map((f) => [f, form.value[f] || null])),
  causes: form.value.causes.map(({ _key, ...c }) => c), whys: form.value.whys.map(({ _key, ...w }) => w) })
const dirty = computed(() => !!d.value && payload() !== snapshot.value)
watch(dirty, (v) => v && (saved.value = false))

function apply(r) {
  // Keep the cause being edited open across a save (rows come back in the same order).
  const open = form.value.causes.findIndex((c) => c._key === editing.value)
  d.value = r
  const inv = r.investigation
  form.value = { ...Object.fromEntries(HEADER.map((f) => [f, inv[f] || ''])),
    causes: r.causes.map((c) => ({ ...c, done: c.done ? 1 : 0, _key: key() })),
    whys: r.whys.map((w) => ({ ...w, _key: key() })) }
  machineLabel.value = r.machine ? r.machine.label : ''
  customerName.value = inv.customer_name || ''
  editing.value = open >= 0 && form.value.causes[open] ? form.value.causes[open]._key : ''
  snapshot.value = payload()
}

const machineLink = computed(() => d.value?.machine?.kind === 'asset' ? { name: 'OpsAsset', params: { name: d.value.machine.name } } : { name: 'OpsEquipmentDetail', params: { name: d.value?.machine?.name } })
function pickMachine(eq) {
  machineLabel.value = eq ? `${eq.customer_name} · ${eq.equipment_name}` : ''
  if (eq) {
    form.value.customer = eq.customer
    customerName.value = eq.customer_name
    if (!form.value.site) form.value.site = eq.site || ''
  }
}

const byCategory = (m) => form.value.causes.filter((c) => c.category === m)
const actionsTotal = computed(() => form.value.causes.filter((c) => (c.action || '').trim()).length)
const actionsDone = computed(() => form.value.causes.filter((c) => (c.action || '').trim() && c.done).length)
function addCause(category) {
  const c = { category, cause: '', evidence: '', actual_vs_required: '', status: 'Potential', action: '', owner_name: '', due_date: '', closure_evidence: '', done: 0, _key: key() }
  form.value.causes.push(c)
  editing.value = c._key
}
function removeCause(c) {
  form.value.causes = form.value.causes.filter((x) => x !== c)
}
function addWhy() {
  form.value.whys.push({ question: '', answer: '', evidence: '', _key: key() })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await api('projectit.investigations.get_investigation', { name: route.params.name }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    apply(await api('projectit.investigations.save', { name: d.value.investigation.name, modified: d.value.investigation.modified, data: payload() }))
    saved.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function act(action) {
  busy.value = true
  error.value = ''
  try {
    apply(await api(`projectit.investigations.${action}`, { name: d.value.investigation.name }))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (!window.confirm('Delete this investigation? This cannot be undone.')) return
  busy.value = true
  try {
    await api('projectit.investigations.delete', { name: d.value.investigation.name })
    snapshot.value = payload()
    d.value = null
    router.replace({ name: 'OpsInvestigations' })
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
}
const pdfUrl = computed(() => `/api/method/projectit.investigations.download?name=${encodeURIComponent(route.params.name)}`)
onBeforeRouteLeave(() => !dirty.value || window.confirm('You have unsaved changes. Leave without saving?'))
onMounted(load)
</script>
<style scoped>
.fishbone :deep(svg) { width: 100%; height: auto; display: block; }
</style>
