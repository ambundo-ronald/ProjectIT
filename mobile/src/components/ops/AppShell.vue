<template>
  <div class="ops min-h-[100dvh] pb-20 md:pb-10">
    <header class="sticky top-0 z-30 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div class="mx-auto flex h-14 items-center gap-3 px-3 md:h-16 md:px-6" :class="width">
        <AppSwitcher />
        <nav class="ml-6 hidden h-full items-stretch gap-1 md:flex" :aria-label="title">
          <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="flex items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors" :class="isActive(t) ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-500 hover:text-gray-800'">
            <FeatherIcon :name="t.icon" class="h-4 w-4" />{{ t.label }}
          </router-link>
        </nav>
        <span class="ml-auto" />
        <UserMenu />
      </div>
    </header>

    <main class="mx-auto px-4 py-5 md:px-6 md:py-8" :class="width">
      <router-view />
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-40 grid border-t border-gray-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" :style="{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }" :aria-label="title">
      <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="isActive(t) ? 'text-brand-700' : 'text-gray-500'">
        <span class="flex h-7 w-14 items-center justify-center rounded-full transition-colors" :class="isActive(t) ? 'bg-brand-50' : ''"><FeatherIcon :name="t.icon" class="h-5 w-5" /></span>
        {{ t.label }}
      </router-link>
    </nav>
  </div>
</template>
<script setup>
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import AppSwitcher from './AppSwitcher.vue'
import UserMenu from './UserMenu.vue'

// tabs: [{ name: routeName, label, icon, match?: [extra route names that highlight this tab] }]
const props = defineProps({ title: String, tabs: Array, width: { type: String, default: 'max-w-4xl' } })
const route = useRoute()
const isActive = (t) => route.name === t.name || (t.match || []).includes(route.name)
</script>
