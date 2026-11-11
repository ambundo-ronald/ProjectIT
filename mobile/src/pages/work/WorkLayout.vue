<template>
  <AppShell title="Techy Work" :tabs="tabs" />
</template>
<script setup>
import { onMounted } from 'vue'
import AppShell from '@/components/ops/AppShell.vue'
import { prefetch } from '@/data/offline'

// Save today's projects and my jobs on the phone, so the day works without signal.
onMounted(() => setTimeout(prefetch, 2000))

const tabs = [
  { name: 'WorkIT', label: 'Today', icon: 'sun' },
  { name: 'MyTasks', label: 'Tasks', icon: 'check-square' },
  { name: 'WorkHistory', label: 'History', icon: 'clock' },
]
</script>
