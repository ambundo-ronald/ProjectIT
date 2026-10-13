<template>
  <Dropdown>
    <template #trigger="{ open, toggle }">
      <button
        class="flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-2 transition-colors"
        :class="dark ? 'hover:bg-white/10' : 'hover:bg-gray-100'"
        :aria-expanded="open"
        aria-haspopup="menu"
        aria-label="Switch app"
        @click="toggle"
      >
        <img src="/techy-app.svg" alt="" class="h-8 w-8 rounded-lg" />
        <span v-if="!compact" class="text-[17px] font-bold tracking-tight" :class="dark ? 'text-white' : 'text-gray-900'">{{ current?.title || 'Techy App' }}</span>
        <FeatherIcon name="chevron-down" class="h-4 w-4 transition-transform" :class="[open ? 'rotate-180' : '', dark ? 'text-brand-200' : 'text-gray-400']" />
      </button>
    </template>
    <p class="px-2.5 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">Switch to</p>
    <router-link :to="{ name: 'Home' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 hover:bg-gray-50" role="menuitem">
      <span class="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600"><FeatherIcon name="home" class="h-4 w-4" /></span>
      <span class="flex-1 text-sm font-medium">Home</span>
    </router-link>
    <router-link v-for="app in myApps || []" :key="app.module" :to="{ name: app.route }" class="flex items-center gap-3 rounded-lg px-2.5 py-2" :class="app === current ? 'bg-brand-50' : 'hover:bg-gray-50'" role="menuitem" :aria-current="app === current ? 'page' : undefined">
      <span class="flex h-9 w-9 items-center justify-center rounded-lg" :class="app.tone"><FeatherIcon :name="app.icon" class="h-4 w-4" /></span>
      <span class="min-w-0 flex-1">
        <span class="block text-sm font-semibold">{{ app.title }}</span>
        <span class="block truncate text-xs text-gray-500">{{ app.text }}</span>
      </span>
      <FeatherIcon v-if="app === current" name="check" class="h-4 w-4 text-brand-600" />
    </router-link>
  </Dropdown>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import Dropdown from './Dropdown.vue'
import { APPS, myApps, loadApps } from '@/data/apps'

defineProps({ dark: Boolean, compact: Boolean })
const route = useRoute()
const current = computed(() => APPS.find((a) => route.path.startsWith(a.prefix)))
onMounted(loadApps)
</script>
