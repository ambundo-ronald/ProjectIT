<template>
  <div class="space-y-4">
    <div class="card p-5">
      <h1 class="text-[18px] font-semibold text-gray-900">Service</h1>
      <p class="mt-1 text-sm text-gray-600">To ask for service, contact {{ plant.me?.company || 'us' }}.</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <a v-if="plant.me?.support_phone" :href="`tel:${plant.me.support_phone}`" class="btn btn-secondary btn-sm"><FeatherIcon name="phone" class="h-4 w-4" />{{ plant.me.support_phone }}</a>
        <a v-if="plant.me?.support_email" :href="`mailto:${plant.me.support_email}`" class="btn btn-secondary btn-sm"><FeatherIcon name="mail" class="h-4 w-4" />{{ plant.me.support_email }}</a>
      </div>
    </div>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
import { plant } from '@/data/plant'
</script>
