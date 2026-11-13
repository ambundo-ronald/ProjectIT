<template>
  <div class="ops min-h-[100dvh] pb-24 md:pb-10">
    <header class="sticky top-0 z-30 border-b border-gray-200 bg-panel/95 backdrop-blur">
      <div class="mx-auto flex h-14 max-w-3xl items-center gap-3 px-3 md:h-16 md:px-6">
        <button v-if="route.meta.back" class="btn btn-ghost btn-icon -ml-1" aria-label="Back" @click="back"><FeatherIcon name="arrow-left" class="h-5 w-5" /></button>
        <img v-else src="/techy-app.svg" alt="" class="h-8 w-8 shrink-0 rounded-lg" />
        <div class="min-w-0 flex-1 leading-tight">
          <p class="truncate text-[15px] font-bold tracking-tight text-gray-900">{{ route.meta.title || contractor.me?.contractor_name || 'Your jobs' }}</p>
          <p v-if="contractor.me && !route.meta.title" class="truncate text-xs text-gray-500">{{ contractor.me.full_name }} · {{ contractor.me.member_role }}</p>
        </div>
        <router-link v-if="contractor.me?.visit" :to="{ name: 'ContractorSite' }" class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-800">
          <span class="relative flex h-2 w-2"><span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-500 opacity-60" /><span class="relative inline-flex h-2 w-2 rounded-full bg-green-500" /></span>On site
        </router-link>
        <nav class="hidden h-full items-stretch gap-1 md:flex" aria-label="Contractor app">
          <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="flex items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors" :class="isActive(t) ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-500 hover:text-gray-800'">
            <FeatherIcon :name="t.icon" class="h-4 w-4" />{{ t.label }}
            <span v-if="t.badge" class="rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white">{{ t.badge }}</span>
          </router-link>
        </nav>
      </div>
    </header>
    <OfflineBar />

    <main class="mx-auto max-w-3xl px-4 py-5 md:px-6 md:py-8">
      <div v-if="!contractor.me && !contractor.error" class="space-y-3" aria-busy="true">
        <div v-for="i in 3" :key="i" class="h-24 animate-pulse rounded-2xl bg-gray-200/70" />
      </div>
      <EmptyState v-else-if="contractor.error && !contractor.me" icon="alert-circle" title="Your jobs could not be loaded" :text="contractor.error" />
      <router-view v-else />
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-40 grid border-t border-gray-200 bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" :style="{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }" aria-label="Contractor app">
      <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="relative flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="isActive(t) ? 'text-brand-700' : 'text-gray-500'">
        <span class="flex h-7 w-14 items-center justify-center rounded-full transition-colors" :class="isActive(t) ? 'bg-brand-50' : ''"><FeatherIcon :name="t.icon" class="h-5 w-5" /></span>
        {{ t.label }}
        <span v-if="t.badge" class="absolute right-[calc(50%-1.6rem)] top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">{{ t.badge }}</span>
      </router-link>
    </nav>
  </div>
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import OfflineBar from '@/components/ops/OfflineBar.vue'
import { contractor, loadContractor } from '@/data/contractor'
import { prefetch } from '@/data/offline'

const route = useRoute()
const router = useRouter()
const tabs = computed(() => {
  const me = contractor.me
  return [
    { name: 'ContractorJobs', label: 'Jobs', icon: 'tool', match: ['ContractorJob'], badge: me?.runs_jobs ? me.counts.offered : 0 },
    { name: 'ContractorSite', label: 'Site', icon: 'map-pin' },
    ...(me?.sees_pay ? [{ name: 'ContractorPay', label: 'Pay', icon: 'credit-card' }] : []),
    { name: 'ContractorAccount', label: me?.runs_jobs ? 'Team' : 'Account', icon: me?.runs_jobs ? 'users' : 'user' },
  ]
})
const isActive = (t) => route.name === t.name || (t.match || []).includes(route.name)
function back() {
  if (window.history.state?.back) router.back()
  else router.push({ name: 'ContractorJobs' })
}
onMounted(() => {
  loadContractor().catch(() => {})
  // Save my jobs on the phone, so the day works without signal.
  setTimeout(prefetch, 2000)
})
</script>
