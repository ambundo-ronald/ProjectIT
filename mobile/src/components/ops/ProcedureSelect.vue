<template>
  <select :value="modelValue" class="input" :aria-label="label" :disabled="procedureList === null" @change="emit('update:modelValue', $event.target.value)">
    <option value="">{{ procedureList === null ? 'Loading procedures…' : placeholder }}</option>
    <optgroup v-for="group in groups" :key="group.name" :label="group.name">
      <option v-for="p in group.items" :key="p.name" :value="p.name">{{ p.title }} · {{ p.steps }} step{{ p.steps === 1 ? '' : 's' }}</option>
    </optgroup>
  </select>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { procedureList, loadProcedures } from '@/data/procedures'

defineProps({ modelValue: String, label: { type: String, default: 'Procedure' }, placeholder: { type: String, default: 'No procedure' } })
const emit = defineEmits(['update:modelValue'])
const groups = computed(() => {
  const by = {}
  for (const p of procedureList.value || []) (by[p.category || 'Other'] ||= []).push(p)
  return Object.keys(by).sort().map((name) => ({ name, items: by[name] }))
})
onMounted(() => loadProcedures().catch(() => {}))
</script>
