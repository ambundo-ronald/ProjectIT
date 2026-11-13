<template>
  <!-- Contractors given a project, with their instructions, and the milestones they are paid by. -->
  <section class="card overflow-hidden">
    <div class="card-header">
      <div><h2 class="card-title">Contractors</h2><p class="text-xs text-gray-500">They see this project and its instructions in their app, and can check in to it.</p></div>
      <button v-if="data?.can_edit && data.available.length" class="btn btn-secondary btn-sm" @click="adding = true"><FeatherIcon name="plus" class="h-3.5 w-3.5" />Add</button>
    </div>
    <p v-if="error" role="alert" class="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data" class="m-4 h-12 animate-pulse rounded-lg bg-gray-100" />
    <ul v-else-if="data.contractors.length" class="divide-y divide-gray-100">
      <li v-for="c in data.contractors" :key="c.contractor" class="px-4 py-3">
        <div class="flex items-center gap-3">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600"><FeatherIcon name="briefcase" class="h-4 w-4" /></span>
          <router-link :to="{ name: 'OpsContractor', params: { name: c.contractor } }" class="min-w-0 flex-1 truncate font-semibold hover:text-brand-700">{{ c.contractor_name }}</router-link>
          <button v-if="data.can_edit" class="btn btn-ghost btn-icon text-gray-400 hover:text-red-600" :aria-label="`Remove ${c.contractor_name}`" @click="remove(c)"><FeatherIcon name="x" class="h-4 w-4" /></button>
        </div>
        <div class="ml-12 mt-1.5">
          <template v-if="editing === c.contractor">
            <textarea v-model="draft" rows="3" maxlength="4000" class="input" :aria-label="`Instructions for ${c.contractor_name}`" />
            <div class="mt-2 flex justify-end gap-2"><button class="btn btn-secondary btn-sm" @click="editing = ''">Cancel</button><button class="btn btn-primary btn-sm" :disabled="busy" @click="saveInstructions(c)">Save</button></div>
          </template>
          <button v-else-if="data.can_edit" class="flex w-full items-start gap-2 rounded-lg px-2 py-1 -ml-2 text-left text-sm hover:bg-gray-50" @click="editing = c.contractor; draft = c.instructions">
            <FeatherIcon name="message-square" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
            <span class="flex-1" :class="c.instructions ? 'whitespace-pre-wrap text-gray-700' : 'italic text-gray-400'">{{ c.instructions || 'Add instructions for them' }}</span>
          </button>
          <p v-else-if="c.instructions" class="whitespace-pre-wrap text-sm text-gray-700">{{ c.instructions }}</p>
        </div>
      </li>
    </ul>
    <p v-else class="px-4 py-4 text-sm text-gray-500">No contractors on this project.</p>

    <!-- Milestones: part of the contract sum, paid when its job is done -->
    <div v-if="ms" class="border-t border-gray-100">
      <div class="flex items-center justify-between px-4 pb-1 pt-3">
        <p class="section-label">Milestones</p>
        <button class="btn btn-ghost btn-sm -mr-2" @click="openMilestone"><FeatherIcon name="plus" class="h-4 w-4" />Add</button>
      </div>
      <ul v-if="ms.milestones.length" class="divide-y divide-gray-100">
        <li v-for="m in ms.milestones" :key="m.name" class="flex items-center gap-3 px-4 py-2.5 text-sm">
          <span class="min-w-0 flex-1">
            <span class="block truncate font-medium text-gray-900">{{ m.description }}</span>
            <span class="block truncate text-xs text-gray-500">{{ m.contractor_name }}<template v-if="m.percent"> · {{ m.percent }}% of {{ money(m.contract_sum) }}</template><template v-if="m.proof_work_order"> · when {{ m.proof_work_order }} is done ({{ m.proof_status || '—' }})</template></span>
          </span>
          <span class="shrink-0 font-semibold tabular-nums">{{ money(m.amount) }}</span>
          <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="LINE_STYLE[m.status]">{{ LINE_LABEL[m.status] }}</span>
          <button v-if="m.status === 'Draft'" class="btn btn-secondary btn-sm" :disabled="busy || (m.proof_work_order && m.proof_status !== 'Completed')" :title="m.proof_work_order && m.proof_status !== 'Completed' ? 'Its job is not completed yet' : ''" @click="approve(m)">Approve</button>
          <button v-if="m.status === 'Draft'" class="btn btn-ghost btn-icon text-gray-400" :aria-label="`Remove ${m.description}`" @click="removeMilestone(m)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button>
        </li>
      </ul>
      <p v-else class="px-4 pb-3 text-sm text-gray-500">Pay a contractor in stages, for example 40% on delivery and 60% at commissioning.</p>
    </div>

    <Modal v-model="adding" title="Add a contractor" subtitle="They are told in their app.">
      <SearchSelect id="pc-contractor" v-model="pick" :options="(data?.available || []).map((c) => ({ value: c.name, label: c.contractor_name, sub: c.trades || c.contractor_type }))" icon="briefcase" aria-label="Contractor" placeholder="Choose a contractor" search-placeholder="Search contractors" />
      <label class="label mt-3" for="pc-ins">Instructions <span class="font-normal text-gray-400">(optional)</span></label>
      <textarea id="pc-ins" v-model="addInstructions" rows="3" maxlength="4000" class="input" placeholder="Their scope on this project" />
      <template #footer>
        <button class="btn btn-secondary" @click="adding = false">Cancel</button>
        <button class="btn btn-primary" :disabled="!pick || busy" @click="add">Add</button>
      </template>
    </Modal>

    <Modal v-model="addingMilestone" title="Add a milestone">
      <form id="pc-ms" class="space-y-3" @submit.prevent="saveMilestone">
        <div><label class="label" for="ms-con">Contractor</label>
          <select id="ms-con" v-model="mform.contractor" class="input" required><option value="" disabled>Choose</option><option v-for="c in ms?.contractors || []" :key="c.name" :value="c.name">{{ c.contractor_name }}</option></select></div>
        <div><label class="label" for="ms-desc">Milestone</label><input id="ms-desc" v-model="mform.description" class="input" required maxlength="140" placeholder="e.g. Delivery and installation" /></div>
        <div class="segmented w-full" role="group" aria-label="Amount as">
          <button type="button" class="flex-1" :aria-pressed="mform.by === 'percent'" @click="mform.by = 'percent'">Percentage</button>
          <button type="button" class="flex-1" :aria-pressed="mform.by === 'amount'" @click="mform.by = 'amount'">Amount</button>
        </div>
        <div v-if="mform.by === 'percent'" class="grid grid-cols-2 gap-3">
          <div><label class="label" for="ms-pct">Percentage</label><input id="ms-pct" v-model.number="mform.percent" type="number" min="0" max="100" step="any" class="input" required /></div>
          <div><label class="label" for="ms-sum">Contract sum</label><input id="ms-sum" v-model.number="mform.contract_sum" type="number" min="0" step="any" class="input" required /></div>
        </div>
        <div v-else><label class="label" for="ms-amt">Amount</label><input id="ms-amt" v-model.number="mform.amount" type="number" min="0" step="any" class="input" required /></div>
        <div><label class="label" for="ms-job">Done when this job is completed <span class="font-normal text-gray-400">(optional)</span></label>
          <select id="ms-job" v-model="mform.proof_work_order" class="input"><option value="">A manager approves it</option><option v-for="j in ms?.jobs || []" :key="j.name" :value="j.name">{{ j.subject }} ({{ j.name }})</option></select></div>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="addingMilestone = false">Cancel</button>
        <button type="submit" form="pc-ms" class="btn btn-primary" :disabled="busy">Add</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import SearchSelect from './SearchSelect.vue'
import { api } from '@/data/ops'
import { money as fmt, LINE_STYLE, LINE_LABEL } from '@/data/contractor'

const props = defineProps({ project: String })
const data = ref(null)
const ms = ref(null)
const error = ref('')
const busy = ref(false)
const editing = ref('')
const draft = ref('')
const adding = ref(false)
const pick = ref('')
const addInstructions = ref('')
const addingMilestone = ref(false)
const mform = reactive({ contractor: '', description: '', by: 'percent', percent: null, contract_sum: null, amount: null, proof_work_order: '' })
const money = (v) => fmt(v, ms.value?.currency)

async function run(work) {
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
const load = () => run(async () => (data.value = await api('projectit.manage.project_contractors', { project: props.project })))
const loadMilestones = () => api('projectit.contractor_pay.milestones', { project: props.project }).then((r) => (ms.value = r)).catch(() => (ms.value = null))
const add = () => run(async () => {
  data.value = await api('projectit.manage.add_contractor', { project: props.project, contractor: pick.value, instructions: addInstructions.value })
  adding.value = false
  pick.value = ''
  addInstructions.value = ''
})
const saveInstructions = (c) => run(async () => {
  data.value = await api('projectit.manage.update_contractor', { project: props.project, contractor: c.contractor, instructions: draft.value })
  editing.value = ''
})
const remove = (c) => window.confirm(`Take ${c.contractor_name} off this project?`) && run(async () => (data.value = await api('projectit.manage.remove_contractor', { project: props.project, contractor: c.contractor })))
function openMilestone() {
  Object.assign(mform, { contractor: data.value?.contractors[0]?.contractor || '', description: '', by: 'percent', percent: null, contract_sum: null, amount: null, proof_work_order: '' })
  addingMilestone.value = true
}
const saveMilestone = () => run(async () => {
  const { by, ...f } = mform
  ms.value = await api('projectit.contractor_pay.save_milestone', { project: props.project, ...f, percent: by === 'percent' ? f.percent : null, contract_sum: by === 'percent' ? f.contract_sum : null, amount: by === 'amount' ? f.amount : null, proof_work_order: f.proof_work_order || null })
  addingMilestone.value = false
})
const approve = (m) => window.confirm(`Approve “${m.description}” for payment (${money(m.amount)})?`) && run(async () => (ms.value = await api('projectit.contractor_pay.approve_milestone', { name: m.name })))
const removeMilestone = (m) => window.confirm(`Remove “${m.description}”?`) && run(async () => (ms.value = await api('projectit.contractor_pay.remove_milestone', { name: m.name })))
onMounted(() => {
  load()
  loadMilestones()
})
</script>
