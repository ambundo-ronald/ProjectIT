<template>
  <section v-if="data && (data.supplies.length || canEdit)" class="card overflow-hidden" aria-labelledby="supplies-title">
    <div class="card-header flex-wrap gap-2">
      <div class="min-w-0">
        <h2 id="supplies-title" class="card-title">Filters and chemicals</h2>
        <p class="text-xs text-gray-500">{{ plant ? 'Tap when you change a filter or top up a chemical: we keep count.' : 'What the machine uses, when it is due and what is on site.' }}</p>
      </div>
      <button v-if="canEdit" class="btn btn-secondary btn-sm" @click="openEdit"><FeatherIcon name="edit-2" class="h-4 w-4" />{{ data.supplies.length ? 'Edit' : 'Add supplies' }}</button>
    </div>

    <ul v-if="data.supplies.length" class="divide-y divide-gray-100">
      <li v-for="s in data.supplies" :key="s.name" class="px-5 py-3 text-sm">
        <div class="flex flex-wrap items-start gap-3">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon :name="s.kind === 'Filter' ? 'filter' : 'droplet'" class="h-4 w-4" /></span>
          <span class="min-w-0 flex-1 basis-40">
            <span class="block font-medium text-gray-900">{{ s.supply_name }}</span>
            <span class="mt-0.5 flex flex-wrap gap-1.5 text-xs">
              <span v-if="s.due" class="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 font-semibold text-red-700"><FeatherIcon name="alert-triangle" class="h-3 w-3" />Due now</span>
              <span v-else-if="s.soon" class="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 font-semibold text-amber-800"><FeatherIcon name="clock" class="h-3 w-3" />Due in {{ s.days_left }} day{{ s.days_left === 1 ? '' : 's' }}</span>
              <span v-else-if="s.due_on" class="text-gray-500">Next {{ formatDate(s.due_on) }}</span>
              <span v-else-if="s.change_every_days && !s.last_changed_on" class="text-gray-500">Not recorded yet</span>
              <span class="text-gray-500">· {{ num(s.stock) }} {{ s.unit }} on site</span>
              <span v-if="s.low && !s.ordered_on" class="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 font-semibold text-amber-800"><FeatherIcon name="alert-circle" class="h-3 w-3" />Running low</span>
              <span v-if="s.ordered_on" class="inline-flex items-center gap-1 rounded bg-brand-50 px-1.5 font-semibold text-brand-700"><FeatherIcon name="shopping-cart" class="h-3 w-3" />Ordered {{ formatDate(s.ordered_on) }}</span>
            </span>
            <span v-if="s.last_changed_on" class="block text-xs text-gray-500">Last {{ s.kind === 'Filter' ? 'changed' : 'topped up' }} {{ fromNow(s.last_changed_on) }}</span>
          </span>
          <span class="flex shrink-0 flex-wrap gap-1.5">
            <button class="btn btn-secondary btn-sm" :disabled="busy" @click="s.kind === 'Filter' ? quick(s) : ask(s, 'Refilled')"><FeatherIcon name="check" class="h-4 w-4" />{{ s.kind === 'Filter' ? 'Changed' : 'Topped up' }}</button>
            <button v-if="plant && !s.ordered_on && (s.low || s.item_code)" class="btn btn-ghost btn-sm" :disabled="busy" @click="orderMore(s)"><FeatherIcon name="shopping-cart" class="h-4 w-4" />Order more</button>
            <Dropdown align="right">
              <template #trigger="{ toggle, open }"><button class="btn btn-ghost btn-icon btn-sm" :aria-expanded="open" aria-haspopup="menu" :aria-label="`More for ${s.supply_name}`" @click="toggle"><FeatherIcon name="more-horizontal" class="h-4 w-4" /></button></template>
              <template #default="{ close }">
                <button class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" @click="close(); ask(s, 'Received')"><FeatherIcon name="package" class="h-4 w-4 text-gray-500" />A delivery arrived</button>
                <button class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" @click="close(); ask(s, 'Counted')"><FeatherIcon name="hash" class="h-4 w-4 text-gray-500" />Correct what is on site</button>
              </template>
            </Dropdown>
          </span>
        </div>
      </li>
    </ul>
    <p v-else class="px-5 py-4 text-sm text-gray-500">No supplies yet. Add the cartridge filters and chemicals this machine uses, so the customer is reminded and can order more.</p>

    <details v-if="data.history.length" class="border-t border-gray-100 px-5 py-2.5 text-xs text-gray-600">
      <summary class="cursor-pointer font-medium text-gray-700">Recent changes</summary>
      <ul class="mt-2 space-y-1">
        <li v-for="(h, i) in data.history" :key="i">{{ formatDate(h.changed_on) }} · {{ h.supply_name }}: {{ ACTION_WORDS[h.action] || h.action }}<template v-if="h.qty !== null"> {{ num(h.qty) }}</template><template v-if="h.by"> · {{ h.by }}</template><template v-if="h.source === 'Customer' && !plant"> (customer)</template></li>
      </ul>
    </details>
    <p v-if="error" role="alert" class="px-5 pb-3 text-sm text-red-600">{{ error }}</p>

    <!-- How much -->
    <Modal :model-value="!!asking" :title="asking ? TITLES[asking.action] : ''" :subtitle="asking?.supply.supply_name" @update:model-value="asking = null">
      <form v-if="asking" id="supply-qty" class="space-y-3" @submit.prevent="sendAsk">
        <div>
          <label class="label" for="supply-qty-input">{{ asking.action === 'Counted' ? 'How much is on site now?' : 'How much?' }}</label>
          <div class="relative">
            <input id="supply-qty-input" v-model="asking.qty" type="text" inputmode="decimal" class="input pr-16 tabular-nums" required />
            <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-gray-500">{{ asking.supply.unit }}</span>
          </div>
        </div>
        <div>
          <label class="label" for="supply-note">Note <span class="font-normal text-gray-500">(optional)</span></label>
          <input id="supply-note" v-model="asking.note" class="input" maxlength="300" />
        </div>
      </form>
      <template #footer>
        <button class="btn btn-secondary" type="button" @click="asking = null">Cancel</button>
        <button class="btn btn-primary" type="submit" form="supply-qty" :disabled="busy">{{ busy ? 'Saving…' : 'Save' }}</button>
      </template>
    </Modal>

    <!-- Managers: which supplies the machine has -->
    <Modal v-model="editing" title="Filters and chemicals" subtitle="What this machine uses" size="xl">
      <div class="space-y-3">
        <div v-for="(r, i) in rows" :key="i" class="rounded-xl border border-gray-200 p-3">
          <div class="grid gap-3 sm:grid-cols-6">
            <div class="sm:col-span-3"><label class="label" :for="`s-name-${i}`">Name</label><input :id="`s-name-${i}`" v-model="r.supply_name" class="input" maxlength="80" placeholder="e.g. 5 micron cartridge filters" /></div>
            <div><label class="label" :for="`s-kind-${i}`">Kind</label><select :id="`s-kind-${i}`" v-model="r.kind" class="input"><option v-for="k in data.kinds" :key="k">{{ k }}</option></select></div>
            <div class="sm:col-span-2"><label class="label" :for="`s-item-${i}`">Item code <span class="font-normal text-gray-500">(to quote)</span></label><input :id="`s-item-${i}`" v-model="r.item_code" class="input" maxlength="140" /></div>
            <div><label class="label" :for="`s-every-${i}`">Every (days)</label><input :id="`s-every-${i}`" v-model="r.change_every_days" type="number" min="0" class="input" /></div>
            <div><label class="label" :for="`s-per-${i}`">Per change</label><input :id="`s-per-${i}`" v-model="r.per_change" type="number" min="0" step="any" class="input" /></div>
            <div><label class="label" :for="`s-unit-${i}`">Unit</label><input :id="`s-unit-${i}`" v-model="r.unit" class="input" maxlength="20" /></div>
            <div><label class="label" :for="`s-stock-${i}`">On site</label><input :id="`s-stock-${i}`" v-model="r.stock" type="number" min="0" step="any" class="input" /></div>
            <div><label class="label" :for="`s-reorder-${i}`">Reorder at</label><input :id="`s-reorder-${i}`" v-model="r.reorder_at" type="number" min="0" step="any" class="input" /></div>
            <div class="flex items-end gap-2"><div class="flex-1"><label class="label" :for="`s-order-${i}`">Order qty</label><input :id="`s-order-${i}`" v-model="r.order_qty" type="number" min="0" step="any" class="input" /></div>
              <button type="button" class="btn btn-ghost btn-icon text-gray-400 hover:text-red-600" :aria-label="`Remove ${r.supply_name || 'supply'}`" @click="rows.splice(i, 1)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button></div>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button type="button" class="btn btn-secondary btn-sm" @click="rows.push(blank('Filter'))"><FeatherIcon name="plus" class="h-4 w-4" />Filter</button>
          <button type="button" class="btn btn-secondary btn-sm" @click="rows.push(blank('Chemical'))"><FeatherIcon name="plus" class="h-4 w-4" />Chemical</button>
        </div>
        <p v-if="editError" role="alert" class="text-sm text-red-600">{{ editError }}</p>
      </div>
      <template #footer>
        <button class="btn btn-secondary" type="button" @click="editing = false">Cancel</button>
        <button class="btn btn-primary" type="button" :disabled="busy" @click="saveEdit">{{ busy ? 'Saving…' : 'Save' }}</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import Dropdown from '@/components/ops/Dropdown.vue'
import { api, request, formatDate, fromNow } from '@/data/ops'

// plant: the customer app (their own endpoints); otherwise our staff on the machine page.
const props = defineProps({ equipment: { type: String, required: true }, plant: Boolean })
const emit = defineEmits(['changed'])
const TITLES = { Refilled: 'Topped up', Received: 'A delivery arrived', Counted: 'Correct what is on site', Changed: 'Changed' }
const ACTION_WORDS = { Changed: 'changed', Refilled: 'topped up', Received: 'delivery', Counted: 'counted' }
const data = ref(null)
const busy = ref(false)
const error = ref('')
const asking = ref(null)
const editing = ref(false)
const editError = ref('')
const rows = ref([])
const canEdit = computed(() => !props.plant && data.value?.manager)
const num = (v) => Number(Number(v || 0).toFixed(2)).toLocaleString()
const blank = (kind) => ({ supply_name: '', kind, item_code: '', change_every_days: kind === 'Filter' ? 30 : '', per_change: 1, unit: kind === 'Filter' ? 'pcs' : 'L', stock: 0, reorder_at: '', order_qty: '' })

async function load() {
  try {
    data.value = props.plant ? await api('projectit.plant.supplies', { equipment: props.equipment }) : await api('projectit.supplies.list_supplies', { equipment: props.equipment })
  } catch (e) {
    data.value = null
  }
}
onMounted(load)
watch(() => props.equipment, load)

async function send(supply, action, qty = null, note = null) {
  busy.value = true
  error.value = ''
  try {
    const args = { equipment: props.equipment, supply: supply.name, action, qty, note }
    const r = props.plant ? await request('projectit.plant.record_supply', args) : await request('projectit.supplies.record_change', args)
    data.value = { ...data.value, ...r }
    emit('changed')
    return true
  } catch (e) {
    error.value = e.message
    return false
  } finally {
    busy.value = false
  }
}
async function quick(s) {
  if (await send(s, 'Changed')) toast({ title: `${s.supply_name}: change recorded`, icon: 'check', iconClasses: 'text-green-600', position: 'top-center' })
}
function ask(s, action) {
  asking.value = { supply: s, action, qty: action === 'Counted' ? String(s.stock) : String(s.per_change || ''), note: '' }
}
async function sendAsk() {
  const qty = String(asking.value.qty).trim().replace(',', '.')
  if (!Number.isFinite(Number(qty))) return
  if (await send(asking.value.supply, asking.value.action, qty, asking.value.note || null)) asking.value = null
}
async function orderMore(s) {
  if (!window.confirm(`Ask us for more ${s.supply_name}? We will send you a quotation.`)) return
  busy.value = true
  error.value = ''
  try {
    data.value = await request('projectit.plant.order_supply', { equipment: props.equipment, supply: s.name })
    toast({ title: 'Asked for more. We will send you a quotation.', icon: 'shopping-cart', iconClasses: 'text-brand-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function openEdit() {
  rows.value = data.value.supplies.map((s) => ({ ...s, item_code: s.item_code || '', change_every_days: s.change_every_days ?? '', per_change: s.per_change ?? '', reorder_at: s.reorder_at ?? '', order_qty: s.order_qty ?? '' }))
  if (!rows.value.length) rows.value.push(blank('Filter'))
  editError.value = ''
  editing.value = true
}
async function saveEdit() {
  busy.value = true
  editError.value = ''
  try {
    data.value = await request('projectit.supplies.save_supplies', { equipment: props.equipment, supplies: rows.value.filter((r) => r.supply_name.trim()) })
    editing.value = false
    emit('changed')
  } catch (e) {
    editError.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
