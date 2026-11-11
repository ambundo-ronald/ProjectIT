<template>
  <!-- compact: a plain select for tight table rows (PM schedule). Everywhere else you can type to search. -->
  <select v-if="compact" :value="modelValue" class="input" :aria-label="label" :disabled="disabled || procedureList === null" @change="emit('update:modelValue', $event.target.value)">
    <option value="">{{ procedureList === null ? 'Loading procedures…' : placeholder }}</option>
    <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }} · {{ o.sub }}</option>
  </select>
  <SearchSelect
    v-else
    :id="id"
    :model-value="modelValue || ''"
    :options="options"
    :aria-label="label"
    :placeholder="placeholder"
    :none-label="allowNone ? placeholder : undefined"
    :loading="procedureList === null"
    :disabled="disabled || procedureList === null"
    icon="list"
    search-placeholder="Search procedures by name or category"
    empty-text="No procedures in the library yet."
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
</template>
<script setup>
import { computed, onMounted } from 'vue'
import SearchSelect from './SearchSelect.vue'
import { procedureList, loadProcedures } from '@/data/procedures'

defineProps({
  modelValue: String,
  id: String,
  label: { type: String, default: 'Procedure' },
  placeholder: { type: String, default: 'No procedure' },
  disabled: Boolean,
  compact: Boolean,
  allowNone: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])
// Sorted by category, then title; the category and step count show under each name and are searchable.
const options = computed(() =>
  [...(procedureList.value || [])]
    .sort((a, b) => (a.category || 'Other').localeCompare(b.category || 'Other') || a.title.localeCompare(b.title))
    .map((p) => ({ value: p.name, label: p.title, sub: `${p.category || 'Other'} · ${p.steps} step${p.steps === 1 ? '' : 's'}` })),
)
onMounted(() => loadProcedures().catch(() => {}))
</script>
