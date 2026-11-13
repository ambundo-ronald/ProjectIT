<template>
  <!-- Who does the job when it goes to a contractor. Managers give or take it back; the contractor's owner or lead
       accepts it and chooses their crew. -->
  <!-- Most jobs are ours: managers see a single line until they choose to give one out. -->
  <div v-if="manager && !info?.contractor && !opened" class="card flex items-center gap-3 px-4 py-3">
    <FeatherIcon name="briefcase" class="h-4 w-4 shrink-0 text-gray-400" />
    <span class="flex-1 text-sm text-gray-600">Done by an external technician?</span>
    <button class="btn btn-secondary btn-sm" @click="opened = true; loadOptions()">Give to a contractor</button>
  </div>
  <div v-else class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">Contractor</h2>
      <span v-if="info?.contractor" class="rounded-full px-2 py-0.5 text-xs font-medium" :class="STATE_STYLE[info.state]">{{ STATE_LABEL[info.state] || info.state }}</span>
    </div>
    <div class="space-y-3 p-4">
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

      <!-- Manager, no contractor yet -->
      <template v-if="manager && !info?.contractor">
        <p class="text-sm text-gray-600">Give this job to an external technician or company. They accept it in their app and choose who does it.</p>
        <div class="flex flex-col gap-2 sm:flex-row">
          <SearchSelect id="wo-contractor" v-model="picked" :options="contractorOptions" :loading="!options" icon="briefcase" aria-label="Contractor" placeholder="Choose a contractor" search-placeholder="Search by name or trade" class="min-w-0 flex-1" />
          <button class="btn btn-primary" :disabled="!picked || busy" @click="give">Offer the job</button>
        </div>
      </template>

      <template v-else-if="info?.contractor">
        <div class="flex items-center gap-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600"><FeatherIcon name="briefcase" class="h-5 w-5" /></span>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold text-gray-900">{{ info.contractor.contractor_name }}</p>
            <p class="text-xs text-gray-500">{{ info.contractor.contractor_type }} · bought on site: {{ info.purchases === 'Included in price' ? 'included in the price' : 'paid back' }}</p>
          </div>
          <router-link v-if="manager" :to="{ name: 'OpsContractor', params: { name: info.contractor.name } }" class="btn btn-ghost btn-sm">Open</router-link>
        </div>
        <p v-if="info.note" class="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700"><span class="font-medium">{{ info.state === 'Declined' ? 'Reason' : 'Note' }}:</span> {{ info.note }}</p>

        <!-- The contractor answers an offer -->
        <div v-if="runs && info.state === 'Offered'" class="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p class="text-sm font-medium text-amber-900">Can you do this job?</p>
          <p v-if="!declining" class="mt-0.5 text-xs text-amber-800">Check the pay below first. Once you accept, choose who on your team does it.</p>
          <textarea v-if="declining" v-model="reason" rows="2" maxlength="1000" class="input mt-2" placeholder="Why not? e.g. no one free this week" aria-label="Reason for declining" />
          <div class="mt-2 flex flex-wrap gap-2">
            <template v-if="!declining">
              <button class="btn btn-primary btn-sm" :disabled="busy" @click="respond(1)"><FeatherIcon name="check" class="h-4 w-4" />Accept</button>
              <button class="btn btn-secondary btn-sm" :disabled="busy" @click="declining = true">Decline</button>
            </template>
            <template v-else>
              <button class="btn btn-primary btn-sm" :disabled="busy || !reason.trim()" @click="respond(0)">Decline the job</button>
              <button class="btn btn-ghost btn-sm" :disabled="busy" @click="declining = false">Back</button>
            </template>
          </div>
        </div>

        <!-- Crew -->
        <div v-if="info.state === 'Accepted' || manager">
          <p class="section-label mb-1.5">Crew on this job</p>
          <div v-if="editingCrew" class="space-y-1">
            <label v-for="p in info.people" :key="p.user" class="flex min-h-[2.75rem] cursor-pointer items-center gap-3 rounded-lg px-2 hover:bg-gray-50">
              <input v-model="crew" type="checkbox" :value="p.user" class="h-5 w-5 rounded-md border-gray-300 text-brand-600" />
              <UserAvatar :name="p.full_name" size="sm" />
              <span class="flex-1 text-sm">{{ p.full_name }} <span class="text-xs text-gray-400">{{ p.member_role }}</span></span>
            </label>
            <p v-if="!info.people.length" class="text-sm text-gray-500">No active people yet.</p>
            <div class="flex gap-2 pt-1">
              <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveCrew">Save crew</button>
              <button class="btn btn-ghost btn-sm" :disabled="busy" @click="editingCrew = false">Cancel</button>
            </div>
          </div>
          <div v-else class="flex flex-wrap items-center gap-1.5">
            <span v-for="p in onJob" :key="p.user" class="inline-flex items-center gap-1.5 rounded-full bg-gray-100 py-0.5 pl-0.5 pr-2.5 text-xs font-medium text-gray-700"><UserAvatar :name="p.full_name" size="xs" />{{ p.full_name }}</span>
            <span v-if="!onJob.length" class="text-sm text-gray-500">{{ runs ? 'Nobody yet: choose who does it.' : 'Nobody yet.' }}</span>
            <button v-if="canCrew" class="btn btn-ghost btn-sm" @click="startCrew"><FeatherIcon name="users" class="h-4 w-4" />Choose crew</button>
          </div>
        </div>

        <div v-if="manager && !closed" class="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
          <select v-model="purchases" class="input !w-auto text-sm" aria-label="Materials bought on site" @change="setPurchases">
            <option value="Reimbursed">Bought on site: we pay it back</option>
            <option value="Included in price">Bought on site: included in the price</option>
          </select>
          <button class="btn btn-ghost btn-sm ml-auto text-gray-500" :disabled="busy" @click="takeBack">Take the job back</button>
        </div>
      </template>
      <div v-else class="h-12 animate-pulse rounded-lg bg-gray-100" />
    </div>
  </div>
</template>
<script setup>
import { ref, computed, watch } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import SearchSelect from './SearchSelect.vue'
import UserAvatar from './UserAvatar.vue'
import { api } from '@/data/ops'
import { contractor as app, loadContractor } from '@/data/contractor'

const props = defineProps({ workOrder: String, initial: Object, manager: Boolean, status: String })
const emit = defineEmits(['changed'])
const STATE_LABEL = { Offered: 'Waiting for an answer', Accepted: 'Accepted', Declined: 'Declined' }
const STATE_STYLE = { Offered: 'bg-amber-100 text-amber-800', Accepted: 'bg-green-100 text-green-800', Declined: 'bg-gray-100 text-gray-600' }
const info = ref(props.initial || null)
const options = ref(null)
const picked = ref('')
const error = ref('')
const busy = ref(false)
const declining = ref(false)
const reason = ref('')
const editingCrew = ref(false)
const crew = ref([])
const purchases = ref(props.initial?.purchases || 'Reimbursed')
const opened = ref(false)
watch(() => props.initial, (v) => {
  info.value = v
  purchases.value = v?.purchases || 'Reimbursed'
})
const closed = computed(() => ['Completed', 'Cancelled'].includes(props.status))
const runs = computed(() => !props.manager && !!app.me?.runs_jobs)
const onJob = computed(() => (info.value?.people || []).filter((p) => p.on_job))
const canCrew = computed(() => !closed.value && (props.manager || (runs.value && info.value?.state === 'Accepted')))
const contractorOptions = computed(() => (options.value || []).map((c) => ({ value: c.name, label: c.contractor_name, sub: [c.contractor_type, c.trades].filter(Boolean).join(' · '), keywords: c.trades || '' })))

async function loadOptions() {
  if (options.value) return
  try {
    options.value = await api('projectit.contractors.options')
  } catch (e) {
    error.value = e.message
  }
}

async function run(method, args, done) {
  busy.value = true
  error.value = ''
  try {
    info.value = await api(method, { work_order: props.workOrder, ...args })
    done?.()
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
const give = () => run('projectit.contractors.give_job', { contractor: picked.value }, () => toast({ title: 'Job offered', text: 'They are told in their app.', icon: 'send', position: 'top-center' }))
const takeBack = () => window.confirm('Take this job back from the contractor? Their crew comes off it, and pay not yet approved is cancelled.') && run('projectit.contractors.give_job', { contractor: null })
const setPurchases = () => run('projectit.contractors.give_job', { contractor: info.value.contractor.name, purchases: purchases.value })
function respond(accept) {
  run('projectit.contractors.respond', { accept, note: accept ? null : reason.value }, () => {
    declining.value = false
    loadContractor(true).catch(() => {})
    if (accept) startCrew()
  })
}
function startCrew() {
  crew.value = onJob.value.map((p) => p.user)
  editingCrew.value = true
}
function saveCrew() {
  if (props.manager) run('projectit.contractors.give_job', { contractor: info.value.contractor.name, crew: crew.value }, () => (editingCrew.value = false))
  else run('projectit.contractors.assign_crew', { users: crew.value }, () => (editingCrew.value = false))
}
</script>
