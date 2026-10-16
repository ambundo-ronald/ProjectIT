<template>
  <section class="mx-auto max-w-6xl p-4 md:p-8" :class="editable ? 'pb-40 md:pb-28' : ''">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsProcedures' }" class="hover:text-gray-800">Procedures</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">{{ isNew ? 'New procedure' : form.title || route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="loading" class="space-y-4" aria-label="Loading"><div class="h-32 animate-pulse rounded-xl bg-gray-200/70" /><div class="h-64 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <div v-else class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <!-- Builder (managers) or read-only summary -->
      <div class="min-w-0 space-y-4">
        <div v-if="archivedDoc" class="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"><FeatherIcon name="archive" class="h-4 w-4" />This procedure is archived and can't be added to new work orders.</div>

        <div class="card space-y-4 p-5">
          <template v-if="editable">
            <div>
              <label class="label" for="proc-title">Title <span class="text-red-500">*</span></label>
              <input id="proc-title" v-model="form.title" maxlength="140" class="input h-11 text-[16px] font-semibold" placeholder="e.g. Pump monthly inspection" />
            </div>
            <div class="grid gap-4 sm:grid-cols-[12rem_1fr]">
              <div>
                <label class="label" for="proc-category">Category</label>
                <select id="proc-category" v-model="form.category" class="input">
                  <option value="">Uncategorised</option>
                  <option v-for="c in CATEGORIES" :key="c">{{ c }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="proc-description">Description</label>
                <input id="proc-description" v-model="form.description" maxlength="1000" class="input" placeholder="When to use it, tools needed…" />
              </div>
            </div>
          </template>
          <template v-else>
            <p class="text-xs text-gray-500">{{ form.category || 'Uncategorised' }} · <span class="font-mono">{{ route.params.name }}</span></p>
            <h1 class="text-[22px] font-semibold tracking-tight">{{ form.title }}</h1>
            <p v-if="form.description" class="text-sm text-gray-600">{{ form.description }}</p>
          </template>
        </div>

        <div v-if="editable && isNew && !steps.length" class="card p-5">
          <h2 class="card-title">Start from a template</h2>
          <p class="mt-0.5 text-sm text-gray-500">Pick one to edit, or add steps below.</p>
          <div class="mt-3 grid gap-2 sm:grid-cols-3">
            <button v-for="s in STARTERS" :key="s.key" type="button" class="rounded-lg border border-gray-200 p-3 text-left transition hover:border-brand-400 hover:bg-brand-50" @click="useStarter(s)">
              <p class="text-sm font-semibold">{{ s.title }}</p>
              <p class="mt-0.5 text-xs text-gray-500">{{ s.steps.filter((x) => x.field_type !== 'Heading').length }} steps · {{ s.category }}</p>
            </button>
          </div>
        </div>

        <!-- Steps -->
        <ol v-if="editable" class="space-y-3" aria-label="Steps">
          <li v-for="(s, i) in steps" :key="s.key" class="card overflow-hidden" :class="s.field_type === 'Heading' ? 'border-dashed bg-gray-50/60' : ''">
            <div class="flex flex-wrap items-center gap-2 border-b border-gray-100 px-3 py-2">
              <span class="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-600" :title="STEP_TYPE[s.field_type].label"><FeatherIcon :name="STEP_TYPE[s.field_type].icon" class="h-4 w-4" /></span>
              <select v-model="s.field_type" class="input h-8 w-auto py-0 pl-2 pr-8 text-[13px]" :aria-label="`Step ${i + 1} type`">
                <option v-for="t in STEP_TYPES" :key="t.type" :value="t.type">{{ t.label }}</option>
              </select>
              <label v-if="s.field_type !== 'Heading'" class="ml-1 inline-flex items-center gap-1.5 text-[13px] text-gray-600"><input v-model="s.required" type="checkbox" class="rounded border-gray-300 text-brand-600" />Required</label>
              <span class="ml-auto flex items-center">
                <button type="button" class="btn btn-ghost btn-icon btn-sm" :disabled="i === 0" :aria-label="`Move step ${i + 1} up`" @click="move(i, -1)"><FeatherIcon name="arrow-up" class="h-4 w-4" /></button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" :disabled="i === steps.length - 1" :aria-label="`Move step ${i + 1} down`" @click="move(i, 1)"><FeatherIcon name="arrow-down" class="h-4 w-4" /></button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" :aria-label="`Duplicate step ${i + 1}`" @click="duplicate(i)"><FeatherIcon name="copy" class="h-4 w-4" /></button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm hover:text-red-600" :aria-label="`Delete step ${i + 1}`" @click="steps.splice(i, 1)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button>
              </span>
            </div>
            <div class="space-y-3 p-3">
              <input v-model="s.label" maxlength="140" class="input" :class="s.field_type === 'Heading' ? 'font-semibold uppercase tracking-wide' : 'font-medium'" :aria-label="`Step ${i + 1}`" :placeholder="PLACEHOLDER[s.field_type]" />
              <textarea v-if="s.showHelp || s.help" v-model="s.help" rows="2" maxlength="500" class="input text-sm" :aria-label="`Step ${i + 1} instructions`" placeholder="Instructions shown under the step" />
              <button v-else type="button" class="text-xs font-medium text-brand-600 hover:underline" @click="s.showHelp = true">+ Add instructions</button>

              <div v-if="s.field_type === 'Multiple Choice'" class="space-y-2">
                <p class="text-xs font-medium text-gray-600">Choices</p>
                <div v-for="(o, j) in s.options" :key="j" class="flex items-center gap-2">
                  <span class="h-3.5 w-3.5 shrink-0 rounded-full border-2 border-gray-300" />
                  <input v-model="s.options[j]" maxlength="80" class="input h-9" :aria-label="`Step ${i + 1} choice ${j + 1}`" :placeholder="`Choice ${j + 1}`" />
                  <button type="button" class="btn btn-ghost btn-icon btn-sm text-gray-400 hover:text-red-600" :aria-label="`Remove choice ${j + 1}`" :disabled="s.options.length <= 2" @click="s.options.splice(j, 1)"><FeatherIcon name="x" class="h-4 w-4" /></button>
                </div>
                <button v-if="s.options.length < 20" type="button" class="text-xs font-medium text-brand-600 hover:underline" @click="s.options.push('')">+ Add choice</button>
              </div>

              <div v-if="s.field_type === 'Number'" class="grid grid-cols-3 gap-2">
                <div><label class="text-xs font-medium text-gray-600" :for="`min-${s.key}`">Minimum</label><input :id="`min-${s.key}`" v-model="s.min_value" inputmode="decimal" class="input h-9" placeholder="—" /></div>
                <div><label class="text-xs font-medium text-gray-600" :for="`max-${s.key}`">Maximum</label><input :id="`max-${s.key}`" v-model="s.max_value" inputmode="decimal" class="input h-9" placeholder="—" /></div>
                <div><label class="text-xs font-medium text-gray-600" :for="`unit-${s.key}`">Unit</label><input :id="`unit-${s.key}`" v-model="s.unit" maxlength="20" class="input h-9" placeholder="bar, °C, mm" /></div>
                <div class="col-span-3"><label class="text-xs font-medium text-gray-600" :for="`meter-${s.key}`">Save to meter <span class="font-normal text-gray-400">(optional)</span></label><input :id="`meter-${s.key}`" v-model="s.meter" maxlength="80" class="input h-9" placeholder="e.g. Permeate TDS" /><p class="mt-0.5 text-[11px] text-gray-500">The answer is recorded as a reading on the machine's meter with this name.</p></div>
              </div>

              <label v-if="s.field_type === 'Pass/Fail' || s.field_type === 'Number'" class="flex items-start gap-2 rounded-lg bg-red-50/60 px-3 py-2 text-[13px] text-gray-700">
                <input v-model="s.create_follow_up" type="checkbox" class="mt-0.5 rounded border-gray-300 text-red-600" />
                <span>Raise a <strong class="font-semibold">follow-up work order</strong> when this {{ s.field_type === 'Number' ? 'reading is out of range' : 'fails' }}</span>
              </label>
            </div>
          </li>
        </ol>

        <div v-if="editable" class="card p-3">
          <p class="px-1 pb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Add a step</p>
          <div class="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
            <button v-for="t in STEP_TYPES" :key="t.type" type="button" class="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition hover:bg-gray-50" @click="add(t.type)">
              <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon :name="t.icon" class="h-4 w-4" /></span>
              <span class="min-w-0"><span class="block text-sm font-medium">{{ t.label }}</span><span class="hidden truncate text-[11px] text-gray-500 sm:block">{{ t.hint }}</span></span>
            </button>
          </div>
        </div>
      </div>

      <!-- Preview: what technicians see -->
      <aside class="min-w-0 lg:sticky lg:top-8 lg:self-start">
        <div class="card overflow-hidden">
          <div class="flex items-center justify-between px-5 pb-2 pt-4">
            <div class="min-w-0">
              <p class="section-label">{{ editable ? 'Preview' : 'Steps' }}</p>
              <p class="mt-0.5 truncate font-semibold">{{ form.title || 'Untitled procedure' }}</p>
            </div>
            <button v-if="Object.keys(answers).length" type="button" class="btn btn-ghost btn-sm text-gray-500" @click="clearAnswers">Reset</button>
          </div>
          <ProcedureRun v-if="preview.length" :steps="preview" preview @answer="previewAnswer" />
          <p v-else class="border-t border-gray-100 px-5 py-8 text-center text-sm text-gray-500">Add steps to see them here.</p>
        </div>
        <p v-if="editable" class="mt-2 px-1 text-xs text-gray-500">Try the steps here. Preview answers aren't saved.</p>
      </aside>
    </div>

    <!-- Save bar -->
    <div v-if="editable && !loading" class="fixed inset-x-0 bottom-16 z-30 border-t border-gray-200 bg-panel/95 backdrop-blur md:bottom-0 md:left-64">
      <div class="mx-auto flex max-w-6xl items-center gap-2 p-3 md:pl-8 md:pr-24">
        <button v-if="!isNew" type="button" class="btn btn-ghost text-gray-500" :disabled="saving" @click="toggleArchive">{{ archivedDoc ? 'Restore' : 'Archive' }}</button>
        <span class="ml-auto hidden text-xs text-gray-500 sm:inline">{{ answerable }} step{{ answerable === 1 ? '' : 's' }} to answer</span>
        <router-link :to="{ name: 'OpsProcedures' }" class="btn btn-secondary">Cancel</router-link>
        <button type="button" class="btn btn-primary" :disabled="saving || !form.title.trim() || !answerable" @click="save"><FeatherIcon name="check" class="h-4 w-4" />{{ saving ? 'Saving…' : isNew ? 'Create procedure' : 'Save changes' }}</button>
      </div>
    </div>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import ProcedureRun from '@/components/ops/ProcedureRun.vue'
import { api, me } from '@/data/ops'
import { ui } from '@/data/apps'
import { STEP_TYPES, STEP_TYPE, CATEGORIES, STARTERS, loadProcedures } from '@/data/procedures'

const route = useRoute()
const router = useRouter()
const isNew = computed(() => route.params.name === 'new')
const form = reactive({ title: '', category: '', description: '', modified: null })
const steps = ref([])
const answers = reactive({})
const loading = ref(!isNew.value)
const saving = ref(false)
const error = ref('')
const archivedDoc = ref(false)
const editable = computed(() => me.manager)

const PLACEHOLDER = {
  Heading: 'Section name, e.g. Safety',
  Checkbox: 'e.g. Isolate the power supply',
  'Pass/Fail': 'e.g. Belt tension within spec',
  'Yes/No/N/A': 'e.g. Any visible corrosion?',
  Number: 'e.g. Discharge pressure',
  Text: 'e.g. Describe any damage',
  'Multiple Choice': 'e.g. Filter condition',
  Photo: 'e.g. Photo of the nameplate',
  Signature: 'e.g. Technician sign-off',
}
let seq = 0
const blankStep = (field_type) => ({ key: ++seq, field_type, label: '', help: '', required: false, options: ['', ''], min_value: '', max_value: '', unit: '', meter: '', create_follow_up: false, showHelp: false })
const fromServer = (s) => ({ ...blankStep(s.field_type), ...s, required: !!s.required, create_follow_up: !!s.create_follow_up, options: s.options ? s.options.split('\n') : ['', ''], key: ++seq })
const answerable = computed(() => steps.value.filter((s) => s.field_type !== 'Heading').length)

function add(type) {
  steps.value.push(blankStep(type))
  setTimeout(() => document.querySelector(`[aria-label="Step ${steps.value.length}"]`)?.focus(), 0)
}
function move(i, step) {
  const [s] = steps.value.splice(i, 1)
  steps.value.splice(i + step, 0, s)
}
const duplicate = (i) => steps.value.splice(i + 1, 0, { ...steps.value[i], options: [...steps.value[i].options], key: ++seq })
function useStarter(s) {
  Object.assign(form, { title: s.title, category: s.category, description: s.description })
  steps.value = s.steps.map(fromServer)
}

// Preview answers are local; failures mirror the server rules.
const fails = (s, value) => {
  if (s.field_type === 'Pass/Fail') return value === 'Fail'
  if (s.field_type !== 'Number' || value === '' || isNaN(Number(value))) return false
  return (s.min_value !== '' && Number(value) < Number(s.min_value)) || (s.max_value !== '' && Number(value) > Number(s.max_value))
}
const preview = computed(() =>
  steps.value.map((s) => {
    const value = answers[s.key] || ''
    return { ...s, name: String(s.key), label: s.label || PLACEHOLDER[s.field_type].replace(/^e\.g\. /, ''), required: s.required ? 1 : 0, options: s.options.filter(Boolean).join('\n'), value, failed: fails(s, value), answered_by: '' }
  }),
)
const previewAnswer = (step, { value }) => {
  if (value) answers[step.name] = value
  else delete answers[step.name]
}
const clearAnswers = () => Object.keys(answers).forEach((k) => delete answers[k])

function payload() {
  return steps.value.map((s) => ({ field_type: s.field_type, label: s.label, help: s.help, required: s.required ? 1 : 0, options: s.field_type === 'Multiple Choice' ? s.options : [], min_value: s.min_value, max_value: s.max_value, unit: s.unit, meter: s.field_type === 'Number' ? s.meter : '', create_follow_up: s.create_follow_up ? 1 : 0 }))
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const r = await api('projectit.procedures.save_procedure', { name: isNew.value ? null : route.params.name, title: form.title, category: form.category || null, description: form.description, steps: payload(), modified: form.modified })
    loadProcedures(true).catch(() => {})
    toast({ title: isNew.value ? 'Procedure created' : 'Changes saved', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    if (isNew.value) router.replace({ name: 'OpsProcedure', params: { name: r.name } })
    else apply(r)
  } catch (e) {
    error.value = e.message
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } finally {
    saving.value = false
  }
}

async function toggleArchive() {
  if (!archivedDoc.value && !window.confirm('Archive this procedure? Work orders that already use it keep their copy.')) return
  saving.value = true
  try {
    apply(await api('projectit.procedures.archive_procedure', { name: route.params.name, archived: archivedDoc.value ? 0 : 1 }))
    loadProcedures(true).catch(() => {})
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

function apply(r) {
  Object.assign(form, { title: r.title, category: r.category, description: r.description, modified: r.modified })
  archivedDoc.value = !!r.disabled
  steps.value = r.steps.map(fromServer)
}

onMounted(async () => {
  ui.dockLift = editable.value ? 64 : 0
  if (isNew.value) {
    const starter = STARTERS.find((s) => s.key === route.query.starter)
    if (starter) useStarter(starter)
    return
  }
  try {
    apply(await api('projectit.procedures.get_procedure', { name: route.params.name }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => (ui.dockLift = 0))
</script>
