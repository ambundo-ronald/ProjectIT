<template>
  <Modal
    :model-value="modelValue"
    :title="request ? 'Approve request' : 'New work order'"
    :subtitle="request ? 'This creates a work order with the request\'s title, details, asset and photos.' : message ? 'From a chat message. Check the title, then say who, when and where.' : 'Describe the job, then say who, when and where.'"
    size="xl"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <form id="work-order-form" class="grid gap-6 md:grid-cols-[1fr_17rem]" @submit.prevent="save">
      <!-- What -->
      <div class="space-y-5">
        <div v-if="request" class="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p class="font-semibold">{{ request.subject }}</p>
          <p class="mt-0.5 text-sm text-gray-500">Requested by {{ request.raised_by_name || request.raised_by }}</p>
        </div>
        <template v-else>
          <p v-if="message" class="flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
            <FeatherIcon name="message-circle" class="h-4 w-4 shrink-0" />
            <span>From {{ message.full_name }}'s message<template v-if="message.photos"> · {{ message.photos === 1 ? 'its photo is' : `its ${message.photos} photos are` }} added to the job</template>. A link is posted in the chat thread.</span>
          </p>
          <div>
            <label class="label" for="wo-subject">Title <span class="text-red-500">*</span></label>
            <input id="wo-subject" v-model="form.subject" required maxlength="140" class="input h-11 text-[15px] font-medium" placeholder="e.g. Replace conveyor belt on line 2" />
          </div>
          <div>
            <label class="label" for="wo-description">Description</label>
            <textarea id="wo-description" v-model="form.description" rows="3" maxlength="4000" class="input" placeholder="What's wrong, what to check, safety notes…" />
          </div>
        </template>

        <div>
          <span class="label">Priority</span>
          <div class="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Priority">
            <button
              v-for="p in priorities"
              :key="p.value"
              type="button"
              role="radio"
              :aria-checked="form.priority === p.value"
              class="flex h-10 items-center justify-center gap-1.5 rounded-lg border text-sm font-medium transition-colors"
              :class="form.priority === p.value ? p.active : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50'"
              @click="form.priority = p.value"
            >
              <FeatherIcon :name="p.icon" class="h-3.5 w-3.5" />{{ p.value }}
            </button>
          </div>
        </div>

        <div>
          <label class="label" for="wo-procedure">Procedure</label>
          <ProcedureSelect id="wo-procedure" v-model="form.procedure" placeholder="None — or pick from the library" />
          <p class="mt-1 text-xs text-gray-500">Readings, pass/fail checks, photos and sign-off. <router-link :to="{ name: 'OpsProcedures' }" class="link" @click="emit('update:modelValue', false)">Browse the library</router-link></p>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <span class="label">Quick checklist</span>
            <span v-if="steps.length" class="text-xs text-gray-500">{{ steps.length }} step{{ steps.length === 1 ? '' : 's' }}</span>
          </div>
          <ol v-if="steps.length" class="mb-2 space-y-2">
            <li v-for="(step, i) in steps" :key="i" class="flex items-center gap-2">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-600">{{ i + 1 }}</span>
              <input v-model="steps[i]" maxlength="140" class="input h-9" :aria-label="`Step ${i + 1}`" placeholder="Describe this step" @keydown.enter.prevent="addStep(i + 1)" />
              <button type="button" class="btn btn-ghost btn-icon text-gray-400 hover:text-red-600" :aria-label="`Remove step ${i + 1}`" @click="steps.splice(i, 1)">
                <FeatherIcon name="trash-2" class="h-4 w-4" />
              </button>
            </li>
          </ol>
          <button type="button" class="flex h-10 w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-gray-300 text-sm font-medium text-gray-600 hover:border-brand-400 hover:text-brand-700" @click="addStep(steps.length)">
            <FeatherIcon name="plus" class="h-4 w-4" /> Add a step
          </button>
        </div>
      </div>

      <!-- Who, when, where -->
      <div class="space-y-4 md:border-l md:border-gray-100 md:pl-6">
        <div>
          <span class="label">Assign to</span>
          <PeoplePicker v-if="me.manager" v-model="form.assignees" placeholder="Search technicians" />
          <label v-else class="flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-sm">
            <input v-model="assignSelf" type="checkbox" class="rounded border-gray-300 text-brand-600" /> Assign to me
          </label>
        </div>
        <div>
          <label class="label" for="wo-due">Due date</label>
          <input id="wo-due" v-model="form.due_date" type="date" class="input" />
        </div>
        <div>
          <label class="label" for="wo-category">Category</label>
          <select id="wo-category" v-model="form.category" class="input">
            <option v-for="c in categories" :key="c">{{ c }}</option>
          </select>
        </div>
        <template v-if="!request">
          <div>
            <span class="label">Customer equipment</span>
            <EquipmentPicker v-model="form.equipment" :label="equipmentLabel" @picked="onEquipment" />
          </div>
          <div v-if="!form.equipment">
            <span class="label">Our asset</span>
            <AssetPicker v-model="form.asset" :label="assetLabel" @picked="onAsset" />
          </div>
          <div v-if="!form.asset && !form.equipment">
            <label class="label" for="wo-location">Location</label>
            <select id="wo-location" v-model="form.location" class="input">
              <option value="">No location</option>
              <option v-for="l in options.locations" :key="l.name" :value="l.name">{{ l.location_name || l.name }}</option>
            </select>
          </div>
        </template>
        <div>
          <label class="label" for="wo-project">Project <span class="font-normal text-gray-400">(optional)</span></label>
          <select id="wo-project" v-model="form.project" class="input">
            <option value="">No project</option>
            <option v-for="p in options.projects" :key="p.name" :value="p.name">{{ p.project_name }}</option>
          </select>
        </div>
      </div>
    </form>
    <p v-if="error" role="alert" class="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <template #footer>
      <button type="button" class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button form="work-order-form" :disabled="busy" class="btn btn-primary">
        <FeatherIcon :name="request ? 'check' : 'plus'" class="h-4 w-4" />{{ busy ? 'Saving…' : request ? 'Approve & create' : 'Create work order' }}
      </button>
    </template>
  </Modal>
</template>
<script setup>
import { reactive, ref, watch, nextTick } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import PeoplePicker from './PeoplePicker.vue'
import AssetPicker from './AssetPicker.vue'
import EquipmentPicker from './EquipmentPicker.vue'
import ProcedureSelect from './ProcedureSelect.vue'
import { api, me, tokens } from '@/data/ops'
import { KIND } from '@/data/links'

const props = defineProps({
  modelValue: Boolean,
  asset: Object, // { name, asset_name, location } to prefill
  equipment: Object, // customer equipment row to prefill
  request: Object, // Issue row to approve
  message: Object, // chat message to turn into a job: { name, content, full_name, photos (count), names }
})
const emit = defineEmits(['update:modelValue', 'saved'])
const categories = ['Corrective', 'Preventive', 'Inspection', 'Installation', 'Safety', 'Other']
const priorities = [
  { value: 'Low', icon: 'chevrons-down', active: 'border-gray-400 bg-gray-100 text-gray-800' },
  { value: 'Medium', icon: 'flag', active: 'border-brand-500 bg-brand-50 text-brand-700' },
  { value: 'High', icon: 'flag', active: 'border-orange-400 bg-orange-50 text-orange-700' },
  { value: 'Urgent', icon: 'alert-triangle', active: 'border-red-400 bg-red-50 text-red-700' },
]
const options = reactive({ projects: [], locations: [] })
const blank = () => ({ subject: '', description: '', priority: 'Medium', category: 'Corrective', due_date: '', asset: '', equipment: '', location: '', assignees: [], project: '', procedure: '' })
const form = reactive(blank())
const steps = ref([])
const assignSelf = ref(true)
const assetLabel = ref('')
const equipmentLabel = ref('')
const busy = ref(false)
const error = ref('')

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    Object.assign(form, blank())
    steps.value = []
    error.value = ''
    assetLabel.value = props.asset?.asset_name || ''
    if (props.asset) Object.assign(form, { asset: props.asset.name, location: props.asset.location || '' })
    equipmentLabel.value = props.equipment ? `${props.equipment.customer_name} · ${props.equipment.equipment_name}` : ''
    if (props.equipment) Object.assign(form, { equipment: props.equipment.name, project: '' })
    if (props.message) {
      // Mentions become names and links readable text; the first line is the title.
      const text = tokens(props.message.content, props.message.names || {})
        .map((p) => (p.link ? `${KIND[p.link.kind].one} ${p.text}` : p.text))
        .join('')
        .trim()
      const first = (text.split('\n').find((l) => l.trim()) || '').trim()
      Object.assign(form, {
        subject: first.length > 120 ? `${first.slice(0, 117).trimEnd()}…` : first || `Photos from ${props.message.full_name}`,
        description: text ? `${text}\n\n(From ${props.message.full_name} in chat)` : `From ${props.message.full_name} in chat`,
      })
    }
    try {
      Object.assign(options, await api('projectit.work_orders.options'))
    } catch (e) {
      error.value = e.message
    }
  },
)

function addStep(index) {
  steps.value.splice(index, 0, '')
  nextTick(() => document.querySelector(`[aria-label="Step ${index + 1}"]`)?.focus())
}

function onEquipment(eq) {
  equipmentLabel.value = eq ? `${eq.customer_name} · ${eq.equipment_name}` : ''
}

function onAsset(asset) {
  assetLabel.value = asset?.asset_name || ''
  form.location = asset?.location || ''
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const assignees = me.manager ? form.assignees : assignSelf.value ? [me.user] : []
    const common = { priority: form.priority, category: form.category, due_date: form.due_date || null, assignees, project: form.project || null, procedure: form.procedure || null, steps: steps.value.map((s) => s.trim()).filter(Boolean) }
    const result = props.request
      ? await api('projectit.work_requests.approve_request', { name: props.request.name, ...common })
      : await api('projectit.work_orders.create_work_order', { ...common, subject: form.subject, description: form.description, asset: form.equipment ? null : form.asset || null, equipment: form.equipment || null, location: form.asset || form.equipment ? null : form.location || null, chat_message: props.message?.name || null })
    emit('saved', result)
    emit('update:modelValue', false)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
