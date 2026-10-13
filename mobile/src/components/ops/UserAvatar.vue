<template>
  <span
    class="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold"
    :class="[sizes[size], image && !failed ? 'bg-gray-100' : palette]"
    :title="name"
    role="img"
    :aria-label="name"
  >
    <img v-if="image && !failed" :src="image" alt="" class="h-full w-full object-cover" @error="failed = true" />
    <template v-else>{{ initials }}</template>
  </span>
</template>
<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ name: { type: String, default: '' }, image: String, size: { type: String, default: 'md' } })
const failed = ref(false)
const sizes = { xs: 'h-5 w-5 text-[9px]', sm: 'h-6 w-6 text-[10px]', md: 'h-8 w-8 text-xs', lg: 'h-9 w-9 text-sm', xl: 'h-12 w-12 text-base' }
const colors = [
  'bg-blue-100 text-blue-800',
  'bg-green-100 text-green-800',
  'bg-amber-100 text-amber-800',
  'bg-violet-100 text-violet-800',
  'bg-pink-100 text-pink-800',
  'bg-teal-100 text-teal-800',
  'bg-orange-100 text-orange-800',
  'bg-cyan-100 text-cyan-800',
]
const initials = computed(() => {
  const parts = (props.name || '?').replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean)
  return ((parts[0]?.[0] || '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
})
// Stable colour per person so teammates are recognisable at a glance.
const palette = computed(() => colors[[...(props.name || '')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % colors.length])
</script>
