<template>
  <Modal :model-value="modelValue" :title="equipment ? 'Edit equipment' : 'Register equipment'" :subtitle="equipment ? equipment.name : 'For machines installed before Techy Ops. New deliveries are added automatically from Delivery Notes.'" size="lg" @update:model-value="emit('update:modelValue', $event)">
    <form id="equipment-form" class="grid gap-4 sm:grid-cols-2" @submit.prevent="save">
      <div class="relative sm:col-span-2">
        <label class="label" for="eq-customer">Customer <span class="text-red-500">*</span></label>
        <div v-if="form.customer" class="flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-panel px-3 text-sm">
          <FeatherIcon name="briefcase" class="h-4 w-4 text-gray-400" /><span class="min-w-0 flex-1 truncate font-medium">{{ form.customer_name || form.customer }}</span>
          <button type="button" class="rounded p-0.5 text-gray-400 hover:bg-gray-100" aria-label="Change customer" @click="setCustomer(null)"><FeatherIcon name="x" class="h-4 w-4" /></button>
        </div>
        <template v-else>
          <input id="eq-customer" v-model="customerQuery" class="input" placeholder="Search customers" autocomplete="off" @input="findCustomers" @focus="findCustomers" />
          <ul v-if="customers.length" class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-panel py-1 shadow-pop">
            <li v-for="c in customers" :key="c.name"><button type="button" class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50" @mousedown.prevent="setCustomer(c)">{{ c.customer_name }}<span v-if="c.customer_name !== c.name" class="text-gray-400"> · {{ c.name }}</span></button></li>
          </ul>
        </template>
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="eq-site">Site</label>
        <select id="eq-site" v-model="form.site_address" class="input" :disabled="!form.customer">
          <option value="">{{ form.customer ? (sites.length ? 'Choose a site address' : 'No addresses for this customer yet') : 'Choose a customer first' }}</option>
          <option v-for="s in sites" :key="s.name" :value="s.name">{{ s.label || s.name }}</option>
        </select>
        <p v-if="form.customer && !sites.length" class="mt-1 text-xs text-gray-500">Add the site as an Address on the customer in ERPNext, then reopen this form.</p>
      </div>
      <div>
        <label class="label" for="eq-item">Item</label>
        <select id="eq-item" v-model="form.item_code" class="input" @change="onItem">
          <option value="">Not linked to an item</option>
          <option v-for="i in items" :key="i.name" :value="i.name">{{ i.item_name }}</option>
        </select>
      </div>
      <div>
        <label class="label" for="eq-name">Equipment name <span class="text-red-500">*</span></label>
        <input id="eq-name" v-model="form.equipment_name" required maxlength="140" class="input" placeholder="e.g. RO System 500 LPH" />
      </div>
      <div>
        <label class="label" for="eq-tag">Tag / label no.</label>
        <input id="eq-tag" v-model="form.tag" maxlength="60" class="input" placeholder="Number on the sticker" />
      </div>
      <div>
        <label class="label" for="eq-status">Status</label>
        <select id="eq-status" v-model="form.status" class="input">
          <option v-for="s in statuses" :key="s">{{ s }}</option>
        </select>
      </div>
      <div>
        <label class="label" for="eq-installed">Installed on</label>
        <input id="eq-installed" v-model="form.installed_on" type="date" class="input" />
      </div>
      <div>
        <label class="label" for="eq-warranty">Warranty until</label>
        <input id="eq-warranty" v-model="form.warranty_until" type="date" class="input" />
      </div>
      <div>
        <label class="label" for="eq-contract">Service contract until</label>
        <input id="eq-contract" v-model="form.contract_until" type="date" class="input" />
      </div>
      <div>
        <label class="label" for="eq-log">Plant app log schedule</label>
        <select id="eq-log" v-model="form.log_schedule" class="input">
          <option v-for="s in LOG_SCHEDULES" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <p class="hint">How often their operators should log in the plant app.</p>
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="eq-notes">Notes</label>
        <textarea id="eq-notes" v-model="form.notes" rows="2" maxlength="2000" class="input" placeholder="Membrane type, access instructions, gate code…" />
      </div>
    </form>
    <p v-if="error" role="alert" class="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <template #footer>
      <button type="button" class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button form="equipment-form" class="btn btn-primary" :disabled="busy || !form.customer || !form.equipment_name.trim()"><FeatherIcon name="check" class="h-4 w-4" />{{ busy ? 'Saving…' : equipment ? 'Save changes' : 'Register' }}</button>
    </template>
  </Modal>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import { api } from '@/data/ops'

const props = defineProps({ modelValue: Boolean, equipment: Object })
const emit = defineEmits(['update:modelValue', 'saved'])
const statuses = ['Active', 'Awaiting installation', 'Out of service', 'Decommissioned']
const blank = () => ({ customer: '', customer_name: '', site_address: '', item_code: '', equipment_name: '', tag: '', status: 'Active', installed_on: '', warranty_until: '', contract_until: '', notes: '', log_schedule: 'Daily' })
const LOG_SCHEDULES = [
  { value: 'Daily', label: 'Once a day' },
  { value: 'Twice a day', label: 'Twice a day (each shift)' },
  { value: 'Weekly', label: 'Once a week' },
  { value: 'Not expected', label: 'Not expected' },
]
const form = reactive(blank())
const customers = ref([])
const customerQuery = ref('')
const sites = ref([])
const items = ref([])
const busy = ref(false)
const error = ref('')

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    error.value = ''
    Object.assign(form, blank())
    customerQuery.value = ''
    customers.value = []
    if (props.equipment) for (const k of Object.keys(form)) form[k] = props.equipment[k] ?? ''
    form.log_schedule ||= 'Daily'
    try {
      items.value = (await api('projectit.equipment.register_options')).items
      if (form.customer) await loadSites()
    } catch (e) {
      error.value = e.message
    }
  },
)

let timer = null
function findCustomers() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    try {
      customers.value = (await api('projectit.equipment.register_options', { txt: customerQuery.value })).customers
    } catch (e) {
      error.value = e.message
    }
  }, 200)
}
async function loadSites() {
  sites.value = await api('projectit.equipment.customer_sites', { customer: form.customer })
  if (!sites.value.some((s) => s.name === form.site_address)) form.site_address = sites.value.length === 1 ? sites.value[0].name : ''
}
async function setCustomer(c) {
  form.customer = c?.name || ''
  form.customer_name = c?.customer_name || ''
  customers.value = []
  sites.value = []
  form.site_address = ''
  if (c) await loadSites().catch((e) => (error.value = e.message))
}
function onItem() {
  const item = items.value.find((i) => i.name === form.item_code)
  if (item && !form.equipment_name) form.equipment_name = item.item_name
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const { customer_name, ...data } = form
    const result = await api('projectit.equipment.save_equipment', { name: props.equipment?.name || null, data })
    emit('saved', result)
    emit('update:modelValue', false)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
