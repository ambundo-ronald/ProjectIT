<template>
  <!-- A contractor job's pay (managers set it; the owner sees it), what the crew bought on site and the materials we
       issued. Crew see quantities to report, never amounts. -->
  <div class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">{{ who === 'crew' ? 'Work to report' : 'Contractor pay' }}</h2>
      <span v-if="data && data.total != null" class="text-sm font-semibold tabular-nums text-gray-900">{{ money(data.total, data.currency) }}</span>
    </div>
    <p v-if="error" role="alert" class="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data" class="m-4 h-16 animate-pulse rounded-lg bg-gray-100" />

    <template v-else>
      <!-- Pay lines -->
      <div v-if="!editing" class="divide-y divide-gray-100">
        <div v-for="l in shownLines" :key="l.name" class="flex items-start gap-3 px-4 py-3">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-gray-900">{{ l.description }}</p>
            <p class="mt-0.5 text-xs text-gray-500">
              {{ PAY_TYPE_LABEL[l.pay_type] }}
              <template v-if="l.pay_type === 'Hourly'"> · hours from {{ l.hours_from === 'Timer' ? 'the job timer' : 'check-in' }}<template v-if="l.status === 'Draft'"> ({{ data.hours[l.hours_from || 'Check-in'] }} h so far)</template></template>
              <template v-if="l.pay_type === 'Per unit'"> · {{ l.qty ? `${Number(l.qty)} ${l.unit || ''}` : l.reported_qty ? `${Number(l.reported_qty)} ${l.unit || ''} reported` : `per ${(l.unit || 'unit').toLowerCase()}` }}</template>
              <template v-if="who !== 'crew' && ['Hourly', 'Per unit', 'Fixed'].includes(l.pay_type) && l.rate"> · {{ money(l.rate, data.currency) }}{{ l.pay_type === 'Fixed' ? '' : ` per ${(l.unit || 'unit').toLowerCase()}` }}</template>
            </p>
            <!-- Crew report how many they did -->
            <div v-if="l.pay_type === 'Per unit' && l.status === 'Draft' && data.can_report" class="mt-2 flex items-center gap-2">
              <label :for="`qty-${l.name}`" class="text-xs text-gray-600">Done</label>
              <input :id="`qty-${l.name}`" v-model.number="qty[l.name]" type="number" min="0" step="any" inputmode="decimal" class="input !h-8 !w-24 text-sm" />
              <span class="text-xs text-gray-500">{{ l.unit }}</span>
              <button class="btn btn-secondary btn-sm" :disabled="busy || qty[l.name] === '' || qty[l.name] == null" @click="report(l)">Save</button>
            </div>
          </div>
          <div class="shrink-0 text-right">
            <p v-if="who !== 'crew'" class="text-sm font-semibold tabular-nums" :class="l.pay_type === 'Deduction' ? 'text-red-700' : 'text-gray-900'">{{ l.pay_type === 'Deduction' ? '−' : '' }}{{ (l.pay_type === 'Hourly' || (l.pay_type === 'Per unit' && !Number(l.qty))) && l.status === 'Draft' ? '—' : money(l.amount, data.currency) }}</p>
            <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium" :class="LINE_STYLE[l.status]">{{ LINE_LABEL[l.status] }}</span>
          </div>
        </div>
        <p v-if="!shownLines.length" class="px-4 py-3 text-sm text-gray-500">{{ data.can_edit ? 'No pay agreed yet. Set it before the contractor accepts.' : 'No pay agreed yet.' }}</p>
        <div v-if="data.can_edit && data.status !== 'Cancelled'" class="flex flex-wrap items-center gap-2 px-4 py-3">
          <button class="btn btn-secondary btn-sm" @click="startEdit"><FeatherIcon name="edit-2" class="h-4 w-4" />{{ jobLines.length ? 'Change pay' : 'Set pay' }}</button>
          <span class="text-xs text-gray-500">Completing the job approves its pay.</span>
        </div>
      </div>

      <!-- Manager: edit the job's fixed, hourly and per-unit lines -->
      <div v-else class="space-y-3 p-4">
        <div v-for="(l, i) in draft" :key="i" class="rounded-lg border border-gray-200 p-3">
          <div class="flex items-center gap-2">
            <select v-model="l.pay_type" class="input !w-auto text-sm" :aria-label="`Pay type ${i + 1}`" :disabled="l.locked">
              <option v-for="t in PAY_TYPES" :key="t" :value="t">{{ PAY_TYPE_LABEL[t] }}</option>
            </select>
            <input v-model="l.description" class="input min-w-0 flex-1 text-sm" maxlength="140" placeholder="What for, e.g. Install 500 LPH RO" :aria-label="`What line ${i + 1} is for`" :disabled="l.locked" />
            <button v-if="!l.locked" class="btn btn-ghost btn-icon" :aria-label="`Remove line ${i + 1}`" @click="draft.splice(i, 1)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button>
          </div>
          <div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div><label class="label" :for="`rate-${i}`">Rate</label><input :id="`rate-${i}`" v-model.number="l.rate" type="number" min="0" step="any" class="input text-sm" :disabled="l.locked" /></div>
            <div v-if="l.pay_type !== 'Hourly'"><label class="label" :for="`q-${i}`">{{ l.pay_type === 'Fixed' ? 'How many' : 'Quantity' }}</label><input :id="`q-${i}`" v-model.number="l.qty" type="number" min="0" step="any" class="input text-sm" :placeholder="l.pay_type === 'Per unit' ? 'As reported' : '1'" :disabled="l.locked" /></div>
            <div v-if="l.pay_type === 'Per unit'"><label class="label" :for="`u-${i}`">Unit</label><input :id="`u-${i}`" v-model="l.unit" class="input text-sm" maxlength="40" placeholder="Piece" :disabled="l.locked" /></div>
            <div v-if="l.pay_type === 'Hourly'" class="col-span-2"><label class="label" :for="`h-${i}`">Hours from</label>
              <select :id="`h-${i}`" v-model="l.hours_from" class="input text-sm" :disabled="l.locked"><option value="Check-in">Site check-in ({{ data.hours['Check-in'] }} h so far)</option><option value="Timer">Job timer ({{ data.hours.Timer }} h so far)</option></select></div>
          </div>
          <p v-if="l.locked" class="mt-1.5 text-xs text-gray-500">{{ LINE_LABEL[l.status] }}: no longer changed here.</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="btn btn-secondary btn-sm" @click="draft.push(blank())"><FeatherIcon name="plus" class="h-4 w-4" />Add a line</button>
          <Dropdown v-if="data.rates.length" align="left">
            <template #trigger="{ open, toggle }"><button class="btn btn-secondary btn-sm" :aria-expanded="open" aria-haspopup="menu" @click="toggle"><FeatherIcon name="list" class="h-4 w-4" />From their rate card</button></template>
            <template #default="{ close }">
              <button v-for="r in data.rates" :key="r.activity + r.unit" class="menu-item" role="menuitem" @click="close(); fromRate(r)">
                <span class="flex-1">{{ r.activity }}</span><span class="text-xs text-gray-500">{{ money(r.rate, data.currency) }} / {{ r.unit.toLowerCase() }}</span>
              </button>
            </template>
          </Dropdown>
        </div>
        <div class="flex gap-2 border-t border-gray-100 pt-3">
          <button class="btn btn-primary" :disabled="busy" @click="save">Save pay</button>
          <button class="btn btn-ghost" :disabled="busy" @click="editing = false">Cancel</button>
        </div>
      </div>

      <!-- Bought on site -->
      <div v-if="data.purchases.length || data.can_report" class="border-t border-gray-100">
        <div class="flex items-center justify-between px-4 pb-1 pt-3">
          <p class="section-label">Bought on site</p>
          <button v-if="data.can_report" class="btn btn-ghost btn-sm -mr-2" @click="buying = true"><FeatherIcon name="plus" class="h-4 w-4" />Add</button>
        </div>
        <ul class="divide-y divide-gray-100">
          <li v-for="p in data.purchases" :key="p.name" class="px-4 py-2.5">
            <div class="flex items-start gap-3">
              <a v-if="p.receipts?.[0]" :href="p.receipts[0]" target="_blank" rel="noopener" class="h-11 w-11 shrink-0 overflow-hidden rounded-lg border border-gray-200"><img :src="p.receipts[0]" alt="Receipt" class="h-full w-full object-cover" /></a>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-gray-900">{{ p.description }} <span v-if="p.qty && p.qty !== 1" class="font-normal text-gray-500">× {{ p.qty }}</span></p>
                <p class="text-xs text-gray-500">{{ p.full_name }} · {{ formatDate(p.bought_on) }}<template v-if="p.status === 'Approved'"> · {{ p.treatment === 'Reimbursed' ? 'paid back' : 'included in the price' }}{{ p.chargeable ? ', charged to the customer' : '' }}</template></p>
                <p v-if="p.status === 'Rejected' && p.rejection_reason" class="mt-0.5 text-xs text-red-700">{{ p.rejection_reason }}</p>
              </div>
              <div class="shrink-0 text-right">
                <p class="text-sm font-semibold tabular-nums">{{ money(p.amount, data.currency) }}</p>
                <span class="text-[11px] font-medium" :class="{ Submitted: 'text-amber-700', Approved: 'text-green-700', Rejected: 'text-red-700' }[p.status]">{{ p.status === 'Submitted' ? 'To review' : p.status }}</span>
              </div>
            </div>
            <div v-if="data.can_edit && p.status === 'Submitted'" class="mt-2 flex flex-wrap items-center gap-2">
              <select v-model="review[p.name].treatment" class="input !h-8 !w-auto text-xs" aria-label="Pay it back?"><option value="Reimbursed">We pay it back</option><option value="Included in price">Included in their price</option></select>
              <label class="flex items-center gap-1.5 text-xs text-gray-700"><input v-model="review[p.name].chargeable" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-brand-600" />Charge the customer</label>
              <button class="btn btn-primary btn-sm" :disabled="busy" @click="reviewPurchase(p, 1)">Accept</button>
              <button class="btn btn-ghost btn-sm text-red-600" :disabled="busy" @click="reviewPurchase(p, 0)">Reject</button>
            </div>
          </li>
          <li v-if="!data.purchases.length" class="px-4 py-2.5 text-sm text-gray-500">Bought something for this job? Add it with a photo of the receipt.</li>
        </ul>
      </div>

      <!-- Materials we issued: what was used and returned -->
      <div v-if="data.materials.length" class="border-t border-gray-100">
        <div class="flex items-center justify-between px-4 pb-1 pt-3">
          <p class="section-label">Materials from our stores</p>
          <button v-if="data.can_report && !reporting" class="btn btn-ghost btn-sm -mr-2" @click="startReport"><FeatherIcon name="edit-3" class="h-4 w-4" />Used and returned</button>
        </div>
        <ul class="divide-y divide-gray-100">
          <li v-for="m in data.materials" :key="m.name" class="px-4 py-2.5 text-sm">
            <div class="flex items-center gap-3">
              <span class="min-w-0 flex-1 truncate font-medium text-gray-900">{{ m.item_name || m.item_code }}</span>
              <span class="shrink-0 text-xs text-gray-500">{{ Number(m.qty) }} {{ m.uom }} issued</span>
            </div>
            <div v-if="reporting" class="mt-2 flex items-center gap-2">
              <label class="text-xs text-gray-600" :for="`used-${m.name}`">Used</label>
              <input :id="`used-${m.name}`" v-model.number="used[m.name].used" type="number" min="0" step="any" class="input !h-8 !w-20 text-sm" :disabled="m.deducted" />
              <label class="text-xs text-gray-600" :for="`ret-${m.name}`">Returned</label>
              <input :id="`ret-${m.name}`" v-model.number="used[m.name].returned" type="number" min="0" step="any" class="input !h-8 !w-20 text-sm" :disabled="m.deducted" />
            </div>
            <p v-else-if="m.materials_reported" class="mt-0.5 text-xs" :class="m.missing ? 'text-amber-800' : 'text-gray-500'">
              Used {{ Number(m.qty_used || 0) }}, returned {{ Number(m.qty_returned || 0) }}<template v-if="m.missing"> · {{ m.missing }} missing</template><template v-if="m.deducted"> · deducted</template>
              <button v-if="data.can_edit && m.missing && !m.deducted" class="ml-2 font-medium text-red-700 underline" :disabled="busy" @click="deduct(m)">Deduct from their pay</button>
            </p>
            <p v-else class="mt-0.5 text-xs text-gray-400">Not reported yet</p>
          </li>
        </ul>
        <div v-if="reporting" class="flex gap-2 px-4 pb-3">
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveMaterials">Save</button>
          <button class="btn btn-ghost btn-sm" :disabled="busy" @click="reporting = false">Cancel</button>
        </div>
      </div>
    </template>

    <Modal v-model="buying" title="Bought on site" subtitle="Add a photo of the receipt. A manager checks it.">
      <form id="buy-form" class="space-y-3" @submit.prevent="logPurchase">
        <div><label class="label" for="buy-what">What you bought</label><input id="buy-what" v-model="buy.description" class="input" maxlength="140" required placeholder="e.g. PVC fittings" /></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="label" for="buy-amount">Amount paid</label><input id="buy-amount" v-model.number="buy.amount" type="number" min="0" step="any" inputmode="decimal" class="input" required /></div>
          <div><label class="label" for="buy-qty">Quantity</label><input id="buy-qty" v-model.number="buy.qty" type="number" min="0" step="any" class="input" /></div>
        </div>
        <div>
          <span class="label">Receipt</span>
          <div class="flex items-center gap-3">
            <img v-if="buy.preview" :src="buy.preview" alt="Receipt" class="h-16 w-16 rounded-lg border border-gray-200 object-cover" />
            <PhotoButtons camera-label="Photo" @photos="(p) => { buy.photo = p[0].content; buy.preview = p[0].preview }" @error="(m) => (error = m)" />
          </div>
        </div>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="buying = false">Cancel</button>
        <button type="submit" form="buy-form" class="btn btn-primary" :disabled="busy || !buy.photo">Send</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from './Modal.vue'
import Dropdown from './Dropdown.vue'
import PhotoButtons from './PhotoButtons.vue'
import { api, formatDate } from '@/data/ops'
import { money, PAY_TYPES, PAY_TYPE_LABEL, LINE_STYLE, LINE_LABEL } from '@/data/contractor'

const props = defineProps({ workOrder: String, reloadKey: [String, Number] })
const emit = defineEmits(['changed'])
const data = ref(null)
const error = ref('')
const busy = ref(false)
const editing = ref(false)
const draft = ref([])
const qty = reactive({})
const review = reactive({})
const buying = ref(false)
const buy = reactive({ description: '', amount: null, qty: 1, photo: '', preview: '' })
const reporting = ref(false)
const used = reactive({})
const who = computed(() => data.value?.who)
const JOB = ['Fixed', 'Hourly', 'Per unit']
const jobLines = computed(() => (data.value?.lines || []).filter((l) => JOB.includes(l.pay_type)))
// Crew see only what they report; owners and managers see every line.
const shownLines = computed(() => (who.value === 'crew' ? (data.value?.lines || []).filter((l) => l.pay_type === 'Per unit') : data.value?.lines || []))
const blank = () => ({ pay_type: 'Fixed', description: '', rate: null, qty: null, unit: '', hours_from: 'Check-in' })

async function load() {
  try {
    set(await api('projectit.contractor_pay.job_pay', { work_order: props.workOrder }))
  } catch (e) {
    error.value = e.message
  }
}
function set(value) {
  data.value = value
  for (const l of value.lines) if (!(l.name in qty)) qty[l.name] = l.reported_qty || null
  for (const p of value.purchases) review[p.name] = review[p.name] || { treatment: p.treatment, chargeable: false }
}
watch(() => [props.workOrder, props.reloadKey], load, { immediate: true })

async function run(method, args, done) {
  busy.value = true
  error.value = ''
  try {
    set(await api(method, args))
    done?.()
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function startEdit() {
  draft.value = jobLines.value.map((l) => ({ ...l, locked: l.status !== 'Draft' }))
  if (!draft.value.length) draft.value.push(blank())
  editing.value = true
}
function fromRate(r) {
  const type = r.unit === 'Hour' ? 'Hourly' : r.unit === 'Job' ? 'Fixed' : 'Per unit'
  draft.value.push({ ...blank(), pay_type: type, description: r.activity, rate: r.rate, unit: r.unit })
}
const save = () => run('projectit.contractor_pay.save_pay_lines', { work_order: props.workOrder, lines: draft.value.filter((l) => !l.locked || l.name) }, () => (editing.value = false))
const report = (l) => run('projectit.contractor_pay.report_quantity', { line: l.name, qty: qty[l.name], work_order: props.workOrder }, () => toast({ title: 'Saved', icon: 'check', position: 'top-center' }))
function reviewPurchase(p, approve) {
  let reason = null
  if (!approve) {
    reason = window.prompt('Why is it not accepted?')
    if (!reason) return
  }
  run('projectit.contractor_pay.review_purchase', { name: p.name, approve, treatment: review[p.name].treatment, chargeable: review[p.name].chargeable ? 1 : 0, reason })
}
function logPurchase() {
  run('projectit.contractor_pay.log_purchase', { work_order: props.workOrder, description: buy.description, amount: buy.amount, qty: buy.qty || 1, photo: buy.photo }, () => {
    buying.value = false
    Object.assign(buy, { description: '', amount: null, qty: 1, photo: '', preview: '' })
    toast({ title: 'Sent for checking', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  })
}
function startReport() {
  for (const m of data.value.materials) used[m.name] = { used: m.materials_reported ? m.qty_used : m.qty, returned: m.materials_reported ? m.qty_returned : 0 }
  reporting.value = true
}
const saveMaterials = () => run('projectit.contractor_pay.report_materials', { work_order: props.workOrder, rows: data.value.materials.filter((m) => !m.deducted).map((m) => ({ name: m.name, ...used[m.name] })) }, () => (reporting.value = false))
const deduct = (m) => window.confirm(`Take ${m.missing} × ${m.item_name || m.item_code} off their pay, at our stock cost?`) && run('projectit.contractor_pay.deduct_missing', { work_order: props.workOrder, part: m.name })
</script>
