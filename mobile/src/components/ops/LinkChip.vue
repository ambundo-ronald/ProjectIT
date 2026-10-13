<template>
  <component
    :is="target.to ? 'router-link' : info === null ? 'span' : 'a'"
    v-bind="info === null ? {} : target.to ? { to: target.to } : { href: target.href }"
    class="mx-px inline-flex max-w-full items-center gap-1 rounded-md px-1.5 py-px align-baseline text-[0.92em] font-medium no-underline transition-colors"
    :class="tone"
    :title="info ? `${meta.one} ${name} · ${info.title}${info.detail ? ' · ' + info.detail : ''}` : `${meta.one} ${name}`"
  >
    <FeatherIcon :name="meta.icon" class="h-3.5 w-3.5 shrink-0 self-center" />
    <span class="shrink-0 font-mono text-[0.95em]">{{ name }}</span>
    <span v-if="info && info.title && info.title !== name" class="min-w-0 truncate font-normal opacity-80">{{ info.title }}</span>
  </component>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { KIND, linkInfo, linkTarget } from '@/data/links'
import { myApps, loadApps } from '@/data/apps'

const props = defineProps({ kind: String, name: String, inverse: Boolean })
const meta = computed(() => KIND[props.kind])
// undefined while loading, null when missing or not visible to this user.
const info = computed(() => linkInfo[`${props.kind}:${props.name}`])
const target = computed(() => (info.value === null ? {} : linkTarget(props.kind, props.name)))
const tone = computed(() => {
  if (props.inverse) return 'bg-white/20 text-white hover:bg-white/30'
  if (info.value === null) return 'bg-gray-100 text-gray-500'
  return 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100 hover:bg-brand-100'
})
onMounted(() => myApps.value === null && loadApps())
</script>
