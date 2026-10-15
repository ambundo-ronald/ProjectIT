<template>
  <Modal :model-value="modelValue" title="Set a status" subtitle="Let the team know where you are. It shows next to your name in chat." @update:model-value="emit('update:modelValue', $event)">
    <form id="status-form" class="space-y-4" @submit.prevent="save">
      <div class="flex gap-2">
        <div>
          <label class="label" for="status-emoji">Emoji</label>
          <input id="status-emoji" v-model="form.emoji" maxlength="8" class="input w-16 text-center text-lg" placeholder="💬" />
        </div>
        <div class="flex-1">
          <label class="label" for="status-text">Status</label>
          <input id="status-text" v-model="form.text" maxlength="100" class="input" placeholder="e.g. On site at Bahari Clinic" />
        </div>
      </div>
      <div>
        <span class="label">Quick picks</span>
        <div class="flex flex-wrap gap-2">
          <button v-for="p in PRESETS" :key="p.text" type="button" class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 px-3 py-1 text-sm hover:border-brand-300 hover:bg-brand-50" @click="Object.assign(form, { emoji: p.emoji, text: p.text, clear_after: p.clear })"><span>{{ p.emoji }}</span>{{ p.text }}</button>
        </div>
      </div>
      <div>
        <label class="label" for="status-clear">Clear after</label>
        <select id="status-clear" v-model="form.clear_after" class="input">
          <option value="30m">30 minutes</option>
          <option value="1h">1 hour</option>
          <option value="4h">4 hours</option>
          <option value="today">Today</option>
          <option value="never">Don't clear</option>
        </select>
      </div>
      <label class="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2.5">
        <span><span class="block text-sm font-medium">Show me as away</span><span class="block text-xs text-gray-500">Teammates see a grey dot even while the app is open.</span></span>
        <input v-model="form.away" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-brand-600" />
      </label>
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    </form>
    <template #footer>
      <button v-if="current.emoji || current.text" type="button" class="btn btn-ghost mr-auto text-gray-600" :disabled="busy" @click="clear">Clear status</button>
      <button type="button" class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button form="status-form" class="btn btn-primary" :disabled="busy">Save</button>
    </template>
  </Modal>
</template>
<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { toast } from 'frappe-ui'
import Modal from './Modal.vue'
import { me } from '@/data/ops'
import { presence, setStatus } from '@/data/presence'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const PRESETS = [
  { emoji: '🚐', text: 'On site', clear: '4h' },
  { emoji: '🚗', text: 'Driving', clear: '1h' },
  { emoji: '🍽️', text: 'At lunch', clear: '1h' },
  { emoji: '🤝', text: 'In a meeting', clear: '1h' },
  { emoji: '🤒', text: 'Off sick', clear: 'today' },
  { emoji: '🏖️', text: 'On leave', clear: 'never' },
]
const current = computed(() => presence[me.user] || {})
const form = reactive({ emoji: '', text: '', clear_after: '4h', away: false })
const busy = ref(false)
const error = ref('')

watch(
  () => props.modelValue,
  (open) => open && Object.assign(form, { emoji: current.value.emoji || '', text: current.value.text || '', clear_after: current.value.clear_at ? '4h' : current.value.text ? 'never' : '4h', away: !!current.value.away }),
)

async function submit(values, message) {
  busy.value = true
  error.value = ''
  try {
    await setStatus(values)
    emit('update:modelValue', false)
    toast({ title: message, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
const save = () => submit({ emoji: form.emoji, text: form.text, clear_after: form.clear_after, away: form.away ? 1 : 0 }, 'Status updated')
const clear = () => submit({ emoji: '', text: '', away: form.away ? 1 : 0 }, 'Status cleared')
</script>
