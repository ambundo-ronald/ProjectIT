<template>
  <div class="relative">
    <div v-if="modelValue" class="flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-sm shadow-sm">
      <FeatherIcon name="droplet" class="h-4 w-4 shrink-0 text-gray-400" />
      <span class="min-w-0 flex-1 truncate font-medium">{{ label || modelValue }}</span>
      <button type="button" class="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700" aria-label="Clear equipment" @click="clear">
        <FeatherIcon name="x" class="h-4 w-4" />
      </button>
    </div>
    <template v-else>
      <div class="relative">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="query" type="search" class="input pl-9" placeholder="Search by customer, site, model or tag" aria-label="Search customer equipment" autocomplete="off" @input="search" @focus="search" @blur="hide" />
      </div>
      <ul v-if="open && results.length" class="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-pop">
        <li v-for="eq in results" :key="eq.name">
          <button type="button" class="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-gray-50" @mousedown.prevent="pick(eq)">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent-600"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-medium">{{ eq.customer_name }}<span class="font-normal text-gray-500"> · {{ eq.equipment_name }}</span></span>
              <span class="block truncate text-xs text-gray-500">{{ eq.site || 'No site' }} · {{ eq.tag || eq.name }}</span>
            </span>
            <CoverageBadge :kind="eq.coverage.kind" short />
          </button>
        </li>
      </ul>
      <p v-if="open && !results.length && query && !busy" class="mt-1 text-xs text-gray-500">No equipment matches.</p>
      <p v-if="error" class="mt-1 text-xs text-red-600">{{ error }}</p>
    </template>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import CoverageBadge from './CoverageBadge.vue'
import { api } from '@/data/ops'

defineProps({ modelValue: String, label: String })
const emit = defineEmits(['update:modelValue', 'picked'])
const query = ref('')
const results = ref([])
const error = ref('')
const open = ref(false)
const busy = ref(false)
let timer = null

function search() {
  open.value = true
  clearTimeout(timer)
  timer = setTimeout(async () => {
    busy.value = true
    try {
      error.value = ''
      results.value = (await api('projectit.equipment.list_equipment', { search: query.value })).equipment.slice(0, 20)
    } catch (e) {
      results.value = []
      error.value = e.message
    } finally {
      busy.value = false
    }
  }, 250)
}
const hide = () => setTimeout(() => (open.value = false), 150)

function pick(eq) {
  emit('update:modelValue', eq.name)
  emit('picked', eq)
  results.value = []
  query.value = ''
  open.value = false
}

function clear() {
  emit('update:modelValue', '')
  emit('picked', null)
}
</script>
