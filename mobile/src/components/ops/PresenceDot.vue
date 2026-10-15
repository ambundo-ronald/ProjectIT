<template>
  <!-- Green when online, grey ring when away or offline; place it on the corner of an avatar. -->
  <span
    class="inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-2"
    :class="[p.online ? 'bg-green-500' : 'bg-white ring-inset', ring, p.online ? '' : 'border-[1.5px] border-gray-400']"
    role="img"
    :aria-label="label"
    :title="label"
  />
</template>
<script setup>
import { computed } from 'vue'
import { presence, statusLine } from '@/data/presence'

const props = defineProps({ user: String, ring: { type: String, default: 'ring-white' } })
const p = computed(() => presence[props.user] || {})
const label = computed(() => [p.value.online ? 'Online' : p.value.away ? 'Away' : 'Offline', statusLine(p.value)].filter(Boolean).join(' · '))
</script>
