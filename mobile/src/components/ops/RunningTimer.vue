<template>
  <router-link v-if="me.timer && !here" :to="{ name: 'OpsWorkOrder', params: { name: me.timer.work_order } }" class="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 hover:bg-amber-100 md:px-8" role="status">
    <span class="h-2 w-2 shrink-0 animate-pulse rounded-full bg-amber-500" />
    <span class="min-w-0 flex-1 truncate">Timer running on <span class="font-semibold">{{ me.timer.subject }}</span></span>
    <span class="font-semibold tabular-nums">{{ clock(me.timer.elapsed + (now - loadedAt) / 1000) }}</span>
    <FeatherIcon name="chevron-right" class="h-4 w-4 shrink-0" />
  </router-link>
</template>
<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import { me, now, useTick, clock } from '@/data/ops'

const route = useRoute()
// The job page shows its own clock.
const here = computed(() => route.name === 'OpsWorkOrder' && route.params.name === me.timer?.work_order)
const loadedAt = ref(Date.now())
watch(() => me.timer, () => (loadedAt.value = Date.now()))
const untick = useTick()
onBeforeUnmount(untick)
</script>
