<template>
  <p class="whitespace-pre-wrap break-words">
    <template v-for="(part, i) in parts" :key="i">
      <span v-if="part.mention" class="rounded px-1 font-medium" :class="inverse ? 'bg-white/20 text-white' : 'bg-brand-50 text-brand-700'">{{ part.text }}</span>
      <LinkChip v-else-if="part.link" :kind="part.link.kind" :name="part.link.name" :inverse="inverse" />
      <template v-else>{{ part.text }}</template>
    </template>
  </p>
</template>
<script setup>
import { computed, watchEffect } from 'vue'
import { tokens } from '@/data/ops'
import { resolveLinks } from '@/data/links'
import LinkChip from './LinkChip.vue'

const props = defineProps({ text: String, names: { type: Object, default: () => ({}) }, inverse: Boolean })
const parts = computed(() => tokens(props.text, props.names))
watchEffect(() => resolveLinks(parts.value.filter((p) => p.link).map((p) => `${p.link.kind}:${p.link.name}`)))
</script>
