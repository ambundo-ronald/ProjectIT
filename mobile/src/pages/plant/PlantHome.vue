<template>
  <div v-if="machine" class="space-y-4">
    <div class="card p-5">
      <p class="section-label">Your plant</p>
      <h1 class="mt-1 text-[22px] font-semibold tracking-tight text-gray-900">{{ machine.equipment_name }}</h1>
      <p class="text-sm text-gray-500">{{ [machine.site, machine.tag].filter(Boolean).join(' · ') }}</p>
    </div>
    <router-link :to="{ name: 'PlantLog' }" class="card flex items-center gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-pop">
      <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><FeatherIcon name="edit-3" class="h-6 w-6" /></span>
      <span class="min-w-0 flex-1"><span class="block font-semibold text-gray-900">Log today's readings</span><span class="block text-sm text-gray-500">Pressures, water quality and flows from the gauges</span></span>
      <FeatherIcon name="arrow-right" class="h-5 w-5 text-gray-400" />
    </router-link>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
import { machine } from '@/data/plant'
</script>
