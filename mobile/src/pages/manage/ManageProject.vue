<template>
  <div class="space-y-5">
    <router-link :to="{ name: 'ManageIT' }" class="btn btn-ghost btn-sm -ml-2"><FeatherIcon name="arrow-left" class="h-4 w-4" />Projects</router-link>
    <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"><FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" /><span class="flex-1">{{ error }}</span><button aria-label="Dismiss" @click="error = ''"><FeatherIcon name="x" class="h-4 w-4" /></button></p>
    <div v-if="!data && !error" class="space-y-4"><div class="h-28 animate-pulse rounded-xl bg-gray-200/70" /><div class="h-64 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <template v-if="data">
      <header class="card flex flex-wrap items-center gap-4 p-5">
        <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><FeatherIcon name="briefcase" class="h-6 w-6" /></span>
        <div class="min-w-[12rem] flex-1">
          <h1 class="text-[22px] font-semibold leading-tight tracking-tight">{{ data.project.project_name }}</h1>
          <p class="text-sm text-gray-500">{{ data.project.name }}<template v-if="data.project.customer"> · {{ data.project.customer }}</template><template v-if="data.project.expected_end_date"> · due {{ formatDate(data.project.expected_end_date) }}</template></p>
        </div>
        <div class="flex w-full gap-6 border-t border-gray-100 pt-3 text-center sm:w-auto sm:border-0 sm:pt-0">
          <div><p class="text-[22px] font-semibold text-green-700">{{ onSite }}</p><p class="text-xs text-gray-500">On site</p></div>
          <div><p class="text-[22px] font-semibold">{{ data.crew.length }}</p><p class="text-xs text-gray-500">Crew</p></div>
        </div>
      </header>

      <div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <!-- Site instructions -->
        <section class="card overflow-hidden lg:sticky lg:top-24">
          <div class="card-header">
            <div><h2 class="card-title">Site instructions</h2><p class="text-xs text-gray-500">Everyone on the crew sees these in Techy Work.</p></div>
            <button v-if="data.can_edit && !editingSite" class="btn btn-secondary btn-sm" @click="editSite"><FeatherIcon name="edit-2" class="h-3.5 w-3.5" />Edit</button>
          </div>
          <div class="p-4">
            <template v-if="editingSite">
              <textarea v-model="siteDraft" rows="8" maxlength="4000" class="input" aria-label="Site instructions" placeholder="Safety requirements, access, working hours, contacts…" />
              <div class="mt-3 flex items-center justify-between gap-2">
                <span class="text-xs text-gray-400">{{ siteDraft.length }}/4000</span>
                <div class="flex gap-2">
                  <button class="btn btn-secondary btn-sm" :disabled="busy" @click="editingSite = false">Cancel</button>
                  <button class="btn btn-primary btn-sm" :disabled="busy || siteDraft === data.work_instruction" @click="saveSite">Save</button>
                </div>
              </div>
            </template>
            <p v-else-if="data.work_instruction" class="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800">{{ data.work_instruction }}</p>
            <button v-else-if="data.can_edit" class="flex w-full flex-col items-center gap-1 rounded-lg border-2 border-dashed border-gray-300 py-6 text-sm text-gray-500 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700" @click="editSite">
              <FeatherIcon name="file-text" class="h-5 w-5" />Add site instructions
            </button>
            <p v-else class="text-sm italic text-gray-400">No site instructions yet.</p>
          </div>
        </section>

        <!-- Crew -->
        <section class="card overflow-hidden">
          <div class="card-header">
            <div><h2 class="card-title">Crew</h2><p class="text-xs text-gray-500">{{ onSite }} of {{ data.crew.length }} on site now</p></div>
            <button v-if="data.can_edit" class="btn btn-primary btn-sm" @click="openAdd"><FeatherIcon name="user-plus" class="h-3.5 w-3.5" />Add people</button>
          </div>
          <ul v-if="data.crew.length" class="divide-y divide-gray-100">
            <li v-for="m in data.crew" :key="m.employee" class="px-4 py-3.5">
              <div class="flex items-center gap-3">
                <span class="relative">
                  <UserAvatar :name="m.name" :image="m.image" size="lg" />
                  <span class="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full ring-2 ring-panel" :class="m.on_site ? 'bg-green-500' : 'bg-gray-300'" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate font-semibold">{{ m.name }}<span v-if="!m.active" class="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-500">Inactive</span></p>
                  <p class="text-xs" :class="m.on_site ? 'font-medium text-green-700' : 'text-gray-500'">{{ m.on_site ? `On site since ${formatTime(m.since)}` : m.designation || 'Not checked in' }}</p>
                </div>
                <button v-if="data.can_edit" class="btn btn-ghost btn-icon text-gray-400 hover:text-red-600" :aria-label="`Remove ${m.name}`" @click="removing = m"><FeatherIcon name="user-minus" class="h-4 w-4" /></button>
              </div>
              <!-- Personal instructions -->
              <div class="ml-12 mt-2">
                <template v-if="editingMember === m.employee">
                  <textarea v-model="memberDraft" rows="3" maxlength="4000" class="input" :aria-label="`Instructions for ${m.name}`" placeholder="Their role, tasks or reminders for this project" />
                  <div class="mt-2 flex justify-end gap-2">
                    <button class="btn btn-secondary btn-sm" :disabled="busy" @click="editingMember = ''">Cancel</button>
                    <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveMember(m)">Save</button>
                  </div>
                </template>
                <button v-else-if="data.can_edit" class="group/ins flex w-full items-start gap-2 rounded-lg px-2 py-1.5 -ml-2 text-left text-sm hover:bg-gray-50" @click="editMember(m)">
                  <FeatherIcon name="message-square" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
                  <span class="flex-1" :class="m.instructions ? 'whitespace-pre-wrap text-gray-700' : 'italic text-gray-400'">{{ m.instructions || 'Add instructions for ' + m.name.split(' ')[0] }}</span>
                  <FeatherIcon name="edit-2" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-300 group-hover/ins:text-brand-600" />
                </button>
                <p v-else-if="m.instructions" class="whitespace-pre-wrap text-sm text-gray-700">{{ m.instructions }}</p>
              </div>
            </li>
          </ul>
          <div v-else class="p-4">
            <EmptyState icon="users" title="No crew yet" text="Add people with Techy Work so they can check in to this project and see its instructions.">
              <button v-if="data.can_edit" class="btn btn-primary btn-sm" @click="openAdd"><FeatherIcon name="user-plus" class="h-4 w-4" />Add people</button>
            </EmptyState>
          </div>
        </section>
      </div>
    </template>

    <!-- Add people -->
    <Modal v-model="adding" title="Add to crew" :subtitle="data?.project.project_name">
      <div class="relative">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="peopleSearch" type="search" class="input pl-9" placeholder="Search people" aria-label="Search people" />
      </div>
      <ul v-if="availablePeople.length" class="mt-3 max-h-64 divide-y divide-gray-100 overflow-y-auto rounded-lg border border-gray-200" role="radiogroup" aria-label="Person">
        <li v-for="p in availablePeople" :key="p.employee">
          <button role="radio" :aria-checked="pick === p.employee" class="flex w-full items-center gap-3 px-3 py-2.5 text-left" :class="pick === p.employee ? 'bg-brand-50' : 'hover:bg-gray-50'" @click="pick = p.employee">
            <UserAvatar :name="p.name" :image="p.image" size="md" />
            <span class="min-w-0 flex-1"><span class="block truncate text-sm font-medium">{{ p.name }}</span><span class="block truncate text-xs text-gray-500">{{ p.designation || p.employee }}</span></span>
            <FeatherIcon v-if="pick === p.employee" name="check-circle" class="h-5 w-5 text-brand-600" />
          </button>
        </li>
      </ul>
      <p v-else class="mt-3 rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-500">{{ data?.available.length ? 'No one matches that search.' : 'Everyone with Techy Work is already on this project. Enable Techy Work on an Employee to add more people.' }}</p>
      <div v-if="pick" class="mt-4">
        <label class="label" for="add-instructions">Instructions for {{ pickedName }} <span class="font-normal text-gray-400">(optional)</span></label>
        <textarea id="add-instructions" v-model="addInstructions" rows="3" maxlength="4000" class="input" placeholder="Their role or tasks on this project" />
      </div>
      <template #footer>
        <button class="btn btn-secondary" @click="adding = false">Cancel</button>
        <button class="btn btn-primary" :disabled="!pick || busy" @click="addMember"><FeatherIcon name="user-plus" class="h-4 w-4" />Add {{ pickedName ? pickedName.split(' ')[0] : '' }}</button>
      </template>
    </Modal>

    <!-- Remove -->
    <Modal :model-value="!!removing" title="Remove from crew?" @update:model-value="removing = null">
      <p class="text-sm text-gray-600"><span class="font-semibold text-gray-900">{{ removing?.name }}</span> will no longer see {{ data?.project.project_name }} in Techy Work or be able to check in to it. Their instructions for this project will be deleted.</p>
      <p v-if="removing?.on_site" class="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"><FeatherIcon name="alert-triangle" class="mt-0.5 h-4 w-4 shrink-0" />They are on site now. They can still check out of their current session.</p>
      <template #footer>
        <button class="btn btn-secondary" @click="removing = null">Keep</button>
        <button class="btn bg-red-600 text-white hover:bg-red-700" :disabled="busy" @click="removeMember">Remove</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import { api, formatDate, formatTime } from '@/data/ops'

const route = useRoute()
const router = useRouter()
const data = ref(null)
const error = ref('')
const busy = ref(false)
const editingSite = ref(false)
const siteDraft = ref('')
const editingMember = ref('')
const memberDraft = ref('')
const adding = ref(false)
const peopleSearch = ref('')
const pick = ref('')
const addInstructions = ref('')
const removing = ref(null)

const project = computed(() => data.value?.project.name || route.params.project)
const onSite = computed(() => data.value?.crew.filter((m) => m.on_site).length || 0)
const availablePeople = computed(() => {
  const q = peopleSearch.value.trim().toLowerCase()
  return (data.value?.available || []).filter((p) => !q || p.name.toLowerCase().includes(q) || (p.designation || '').toLowerCase().includes(q))
})
const pickedName = computed(() => data.value?.available.find((p) => p.employee === pick.value)?.name || '')

async function run(work, done) {
  busy.value = true
  error.value = ''
  try {
    await work()
    if (done) toast({ title: done, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function load() {
  try {
    data.value = await api('projectit.manage.project', { project: route.params.project })
    // Old links used the project name; show the canonical ID in the address bar.
    if (data.value.project.name !== route.params.project) router.replace({ name: 'ManageProject', params: { project: data.value.project.name } })
  } catch (e) {
    error.value = e.message
  }
}

function editSite() {
  siteDraft.value = data.value.work_instruction
  editingSite.value = true
}
const saveSite = () =>
  run(async () => {
    data.value.work_instruction = (await api('projectit.manage.save_instructions', { project: project.value, work_instruction: siteDraft.value })).work_instruction
    editingSite.value = false
  }, 'Site instructions saved')

function editMember(m) {
  memberDraft.value = m.instructions
  editingMember.value = m.employee
}
const saveMember = (m) =>
  run(async () => {
    m.instructions = (await api('projectit.manage.update_member', { project: project.value, employee: m.employee, instructions: memberDraft.value })).instructions
    editingMember.value = ''
  }, `Saved instructions for ${m.name.split(' ')[0]}`)

function openAdd() {
  pick.value = ''
  peopleSearch.value = ''
  addInstructions.value = ''
  adding.value = true
}
const addMember = () =>
  run(async () => {
    const name = pickedName.value
    data.value = await api('projectit.manage.add_member', { project: project.value, employee: pick.value, instructions: addInstructions.value })
    adding.value = false
    return name
  }, 'Added to crew')
const removeMember = () =>
  run(async () => {
    data.value = await api('projectit.manage.remove_member', { project: project.value, employee: removing.value.employee })
    removing.value = null
  }, 'Removed from crew')

onMounted(load)
</script>
