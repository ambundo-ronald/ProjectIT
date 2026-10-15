<template>
  <AppShell title="Techy Manage" :tabs="tabs" width="max-w-6xl" />
</template>
<script setup>
import AppShell from '@/components/ops/AppShell.vue'

const tabs = [
  { name: 'ManageIT', label: 'Projects', icon: 'briefcase', match: ['ManageProject'] },
  { name: 'ManageTasks', label: 'Tasks', icon: 'check-square' },
]
</script>
