<template>
  <AppShell title="Techy Work" :tabs="tabs" />
</template>
<script setup>
import AppShell from '@/components/ops/AppShell.vue'

const tabs = [
  { name: 'WorkIT', label: 'Today', icon: 'sun' },
  { name: 'MyTasks', label: 'Tasks', icon: 'check-square' },
  { name: 'WorkHistory', label: 'History', icon: 'clock' },
]
</script>
