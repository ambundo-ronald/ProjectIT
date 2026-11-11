<template>
  <div class="relative">
    <div v-if="modelValue" class="flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-panel px-3 text-sm shadow-sm">
      <FeatherIcon name="box" class="h-4 w-4 shrink-0 text-gray-400" />
      <span class="min-w-0 flex-1 truncate font-medium">{{ label || modelValue }}</span>
      <button type="button" class="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700" aria-label="Clear asset" @click="clear">
        <FeatherIcon name="x" class="h-4 w-4" />
      </button>
    </div>
    <template v-else>
      <div class="relative">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="query" type="search" class="input pl-9" placeholder="Search assets by name or code" aria-label="Search assets" autocomplete="off" @input="search" @focus="search" @blur="hide" />
      </div>
      <ul v-if="open && results.length" class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-panel py-1 shadow-pop">
        <li v-for="asset in results" :key="asset.name">
          <button type="button" class="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-gray-50" @mousedown.prevent="pick(asset)">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gray-100 text-gray-500"><FeatherIcon name="box" class="h-4 w-4" /></span>
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium">{{ asset.asset_name }}</span>
              <span class="block truncate text-xs text-gray-500">{{ asset.location || 'No location' }} · {{ asset.name }}</span>
            </span>
          </button>
        </li>
      </ul>
      <p v-if="error" class="hint">{{ error }}</p>
    </template>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { api } from '@/data/ops'

defineProps({ modelValue: String, label: String })
const emit = defineEmits(['update:modelValue', 'picked'])
const query = ref('')
const results = ref([])
const error = ref('')
const open = ref(false)
let timer = null

function search() {
  open.value = true
  clearTimeout(timer)
  timer = setTimeout(async () => {
    try {
      error.value = ''
      results.value = (await api('projectit.maintenance.list_assets', { search: query.value })).assets
    } catch (e) {
      results.value = []
      error.value = e.message
    }
  }, 250)
}
const hide = () => setTimeout(() => (open.value = false), 150)

function pick(asset) {
  emit('update:modelValue', asset.name)
  emit('picked', asset)
  results.value = []
  query.value = ''
  open.value = false
}

function clear() {
  emit('update:modelValue', '')
  emit('picked', null)
}
</script>
