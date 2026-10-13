<template>
  <nav class="inline-flex rounded-lg bg-gray-100 p-0.5" aria-label="Equipment">
    <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors" :class="route.name === t.name ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'" :aria-current="route.name === t.name ? 'page' : undefined">
      <FeatherIcon :name="t.icon" class="h-3.5 w-3.5" /><span class="sm:hidden">{{ t.short }}</span><span class="hidden sm:inline">{{ t.label }}</span>
    </router-link>
  </nav>
</template>
<script setup>
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'

const route = useRoute()
const tabs = [
  { name: 'OpsEquipment', label: 'Customer equipment', short: 'Customers', icon: 'droplet' },
  { name: 'OpsContracts', label: 'Contracts', short: 'Contracts', icon: 'file-text' },
  { name: 'OpsAssets', label: 'Our assets', short: 'Ours', icon: 'box' },
]
</script>
