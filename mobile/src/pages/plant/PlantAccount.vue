<template>
  <div v-if="plant.me" class="space-y-4">
    <div class="card flex items-center gap-4 p-5">
      <UserAvatar :name="plant.me.full_name" size="lg" />
      <div class="min-w-0 flex-1">
        <p class="truncate text-[17px] font-semibold text-gray-900">{{ plant.me.full_name }}</p>
        <p class="truncate text-sm text-gray-500">{{ plant.me.user }}</p>
        <p class="mt-1 text-xs text-gray-600">{{ plant.me.admin ? 'Admin' : 'Operator' }} · {{ plant.me.customer_name }}</p>
      </div>
    </div>

    <div class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Your machines</h2><span class="text-xs text-gray-500">{{ plant.me.machines.length }}</span></div>
      <ul v-if="plant.me.machines.length" class="divide-y divide-gray-100">
        <li v-for="m in plant.me.machines" :key="m.name" class="flex items-center gap-3 px-5 py-3 text-sm">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
          <span class="min-w-0 flex-1"><span class="block truncate font-medium text-gray-900">{{ m.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ [m.site, m.tag].filter(Boolean).join(' · ') || m.name }}</span></span>
          <span v-if="m.status !== 'Active'" class="shrink-0 rounded bg-gray-100 px-1.5 text-[11px] font-semibold text-gray-600">{{ m.status }}</span>
        </li>
      </ul>
      <p v-else class="px-5 py-4 text-sm text-gray-500">None yet.</p>
    </div>

    <!-- A customer admin manages their own operators -->
    <CustomerAccessCard v-if="plant.me.admin" />

    <div class="card p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="flex items-center gap-3 text-sm font-medium text-gray-900"><FeatherIcon :name="theme.dark ? 'moon' : 'sun'" class="h-4 w-4 text-gray-500" />Appearance</span>
        <span class="segmented" role="group" aria-label="Appearance">
          <button v-for="o in THEMES" :key="o.key" type="button" :aria-pressed="theme.choice === o.key" :title="o.title" @click="setTheme(o.key)">{{ o.label }}</button>
        </span>
      </div>
    </div>

    <div class="card p-5">
      <h2 class="section-label">Need help?</h2>
      <p class="mt-1 text-sm text-gray-600">Ask for service from the Service tab, or contact {{ plant.me.company || 'us' }}:</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <a v-if="plant.me.support_phone" :href="`tel:${plant.me.support_phone}`" class="btn btn-secondary btn-sm"><FeatherIcon name="phone" class="h-4 w-4" />{{ plant.me.support_phone }}</a>
        <a v-if="plant.me.support_email" :href="`mailto:${plant.me.support_email}`" class="btn btn-secondary btn-sm"><FeatherIcon name="mail" class="h-4 w-4" />{{ plant.me.support_email }}</a>
        <router-link :to="{ name: 'PlantService' }" class="btn btn-secondary btn-sm"><FeatherIcon name="tool" class="h-4 w-4" />Ask for service</router-link>
      </div>
    </div>

    <button class="btn btn-secondary w-full text-red-600" :disabled="session.logout.loading" @click="session.logout.submit()"><FeatherIcon name="log-out" class="h-4 w-4" />Sign out</button>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import CustomerAccessCard from '@/components/ops/CustomerAccessCard.vue'
import { plant } from '@/data/plant'
import { session } from '@/data/session'
import { theme, setTheme } from '@/data/theme'

const THEMES = [
  { key: 'light', label: 'Light', title: 'Light' },
  { key: 'dark', label: 'Dark', title: 'Dark navy' },
  { key: 'system', label: 'Auto', title: "Match the phone's setting" },
]
</script>
