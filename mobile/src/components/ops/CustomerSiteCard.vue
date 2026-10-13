<template>
  <div class="card p-4 text-sm">
    <h3 class="section-label">Customer site</h3>
    <p class="mt-2 font-semibold">{{ equipment.customer_name }}</p>
    <p v-if="equipment.address?.address_title || equipment.site" class="text-gray-700">{{ equipment.address?.address_title || equipment.site }}</p>
    <p v-for="l in equipment.address?.lines || []" :key="l" class="text-gray-500">{{ l }}</p>
    <p v-if="equipment.contact.name" class="mt-2 text-xs text-gray-500">Contact: {{ equipment.contact.name }}</p>
    <div class="mt-3 flex flex-wrap gap-2">
      <a v-if="phone" :href="`tel:${phone}`" class="btn btn-secondary btn-sm"><FeatherIcon name="phone" class="h-4 w-4" />Call</a>
      <a v-if="mapLink(equipment.address)" :href="mapLink(equipment.address)" target="_blank" rel="noopener" class="btn btn-secondary btn-sm"><FeatherIcon name="navigation" class="h-4 w-4" />Directions</a>
      <router-link :to="{ name: 'OpsEquipmentDetail', params: { name: equipment.name } }" class="btn btn-ghost btn-sm">Machine history</router-link>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { mapLink } from '@/data/equipment'

const props = defineProps({ equipment: { type: Object, required: true } })
const phone = computed(() => props.equipment.contact?.phone || props.equipment.address?.phone || '')
</script>
