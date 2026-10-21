<template>
  <section v-if="items.length" class="card overflow-hidden border-amber-200" aria-labelledby="advice-title">
    <div class="flex items-center gap-2 bg-amber-50 px-5 py-3">
      <FeatherIcon name="alert-triangle" class="h-5 w-5 shrink-0 text-amber-600" />
      <h2 id="advice-title" class="flex-1 text-[15px] font-semibold text-amber-900">{{ title }}</h2>
      <button v-if="dismissible" class="btn btn-ghost btn-icon text-amber-800" aria-label="Close" @click="$emit('close')"><FeatherIcon name="x" class="h-4 w-4" /></button>
    </div>
    <ul class="divide-y divide-gray-100">
      <li v-for="a in items" :key="a.meter" class="px-5 py-3 text-sm">
        <p class="font-medium text-gray-900">{{ a.meter_name }}: {{ num(a.value) }} {{ a.unit }} <span class="font-normal text-gray-600">({{ a.direction === 'high' ? 'above' : 'below' }} {{ num(a.limit) }} {{ a.unit }})</span></p>
        <p class="mt-0.5 text-gray-700">{{ a.text }}</p>
      </li>
    </ul>
    <div class="flex flex-wrap gap-2 border-t border-gray-100 px-5 py-3">
      <router-link :to="{ name: 'PlantService', query: { ask: subject } }" class="btn btn-secondary btn-sm"><FeatherIcon name="tool" class="h-4 w-4" />Ask for service</router-link>
      <a v-if="phone" :href="`tel:${phone}`" class="btn btn-ghost btn-sm"><FeatherIcon name="phone" class="h-4 w-4" />Call us</a>
    </div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({ items: { type: Array, default: () => [] }, title: { type: String, default: 'What to do now' }, phone: String, dismissible: Boolean })
defineEmits(['close'])
const num = (v) => Number(Number(v).toFixed(2)).toLocaleString()
const subject = computed(() => props.items.map((a) => `${a.meter_name} ${a.direction === 'high' ? 'high' : 'low'} (${num(a.value)} ${a.unit})`).join(', ').slice(0, 140))
</script>
