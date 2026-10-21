<template>
  <div class="ops min-h-[100dvh] pb-24 md:pb-10">
    <header class="sticky top-0 z-30 border-b border-gray-200 bg-panel/95 backdrop-blur">
      <div class="mx-auto flex h-14 max-w-3xl items-center gap-3 px-3 md:h-16 md:px-6">
        <img src="/techy-app.svg" alt="" class="h-8 w-8 shrink-0 rounded-lg" />
        <div class="min-w-0 flex-1 leading-tight">
          <p class="truncate text-[15px] font-bold tracking-tight text-gray-900">{{ plant.me?.customer_name || 'Your plant' }}</p>
          <!-- Which machine: a picker only when there is more than one -->
          <!-- Many machines (a hotel group, an estate): a searchable list -->
          <button v-if="plant.me?.machines.length > FEW" class="-ml-1 flex max-w-full items-center gap-1 rounded px-1 text-xs font-medium text-brand-700 hover:bg-brand-50" aria-haspopup="dialog" aria-label="Choose a machine" @click="openPicker">
            <span class="truncate">{{ machine?.equipment_name || 'Choose a machine' }}</span><FeatherIcon name="chevron-down" class="h-3.5 w-3.5 shrink-0" />
          </button>
          <Dropdown v-else-if="plant.me?.machines.length > 1" align="left">
            <template #trigger="{ open, toggle }">
              <button class="-ml-1 flex max-w-full items-center gap-1 rounded px-1 text-xs font-medium text-brand-700 hover:bg-brand-50" :aria-expanded="open" aria-haspopup="menu" aria-label="Choose a machine" @click="toggle">
                <span class="truncate">{{ machine?.equipment_name || 'Choose a machine' }}</span><FeatherIcon name="chevron-down" class="h-3.5 w-3.5 shrink-0" />
              </button>
            </template>
            <template #default="{ close }">
              <p class="px-2.5 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">Your machines</p>
              <button v-for="m in plant.me.machines" :key="m.name" class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left" :class="m.name === plant.machine ? 'bg-brand-50' : 'hover:bg-gray-50'" role="menuitemradio" :aria-checked="m.name === plant.machine" @click="chooseMachine(m.name); close()">
                <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
                <span class="min-w-0 flex-1"><span class="block truncate text-sm font-semibold">{{ m.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ m.site || m.tag || m.name }}</span></span>
                <FeatherIcon v-if="m.name === plant.machine" name="check" class="h-4 w-4 text-brand-600" />
              </button>
            </template>
          </Dropdown>
          <p v-else-if="machine" class="truncate text-xs text-gray-500">{{ machine.equipment_name }}</p>
        </div>
        <Modal v-model="picking" title="Choose a machine" :subtitle="`${plant.me?.machines.length} machines`">
          <input v-model="search" type="search" class="input mb-3" placeholder="Search by name, site or tag" aria-label="Search machines" />
          <div role="radiogroup" aria-label="Your machines" class="space-y-1">
            <button v-for="m in found" :key="m.name" role="radio" :aria-checked="m.name === plant.machine" class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left" :class="m.name === plant.machine ? 'bg-brand-50' : 'hover:bg-gray-50'" @click="chooseMachine(m.name); picking = false">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
              <span class="min-w-0 flex-1"><span class="block truncate text-sm font-semibold">{{ m.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ [m.site, m.tag].filter(Boolean).join(' · ') || m.name }}</span></span>
              <FeatherIcon v-if="m.name === plant.machine" name="check" class="h-4 w-4 text-brand-600" />
            </button>
            <p v-if="!found.length" class="px-2.5 py-3 text-sm text-gray-500">No machine matches “{{ search }}”.</p>
          </div>
        </Modal>
        <nav class="hidden h-full items-stretch gap-1 md:flex" aria-label="Plant app">
          <router-link v-for="t in TABS" :key="t.name" :to="{ name: t.name }" class="flex items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors" :class="isActive(t) ? 'border-brand-600 text-brand-700' : 'border-transparent text-gray-500 hover:text-gray-800'">
            <FeatherIcon :name="t.icon" class="h-4 w-4" />{{ t.label }}
          </router-link>
        </nav>
      </div>
    </header>

    <div v-if="plant.me?.preview" class="sticky top-14 z-20 border-b border-amber-200 bg-amber-50 md:top-16" role="status">
      <div class="mx-auto flex max-w-3xl flex-wrap items-center gap-2 px-4 py-2 text-sm text-amber-900 md:px-6">
        <FeatherIcon name="eye" class="h-4 w-4 shrink-0" />
        <span class="min-w-0 flex-1">Preview: what {{ plant.me.customer_name }}'s admin sees. Nothing can be saved.</span>
        <button class="btn btn-secondary btn-sm" @click="leavePreview">Leave preview</button>
      </div>
    </div>

    <main class="mx-auto max-w-3xl px-4 py-5 md:px-6 md:py-8">
      <div v-if="!plant.me && !plant.error" class="space-y-3" aria-busy="true">
        <div v-for="i in 3" :key="i" class="h-24 animate-pulse rounded-2xl bg-gray-200/70" />
      </div>
      <EmptyState v-else-if="plant.error" icon="alert-circle" title="Your plant could not be loaded" :text="plant.error" />
      <EmptyState v-else-if="!plant.me.machines.length && route.name !== 'PlantAccount'" icon="droplet" title="No machines on your account yet" :text="plant.me.admin ? 'Ask us to register your machines to your account.' : 'Ask your admin to give you the machines you look after.'" />
      <router-view v-else />
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-gray-200 bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" aria-label="Plant app">
      <router-link v-for="t in TABS" :key="t.name" :to="{ name: t.name }" class="flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="isActive(t) ? 'text-brand-700' : 'text-gray-500'">
        <span class="flex h-7 w-14 items-center justify-center rounded-full transition-colors" :class="isActive(t) ? 'bg-brand-50' : ''"><FeatherIcon :name="t.icon" class="h-5 w-5" /></span>
        {{ t.label }}
      </router-link>
    </nav>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import Dropdown from '@/components/ops/Dropdown.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import Modal from '@/components/ops/Modal.vue'
import { plant, machine, loadPlant, chooseMachine, setPreview } from '@/data/plant'

const TABS = [
  { name: 'PlantHome', label: 'Home', icon: 'home' },
  { name: 'PlantLog', label: 'Log', icon: 'edit-3' },
  { name: 'PlantService', label: 'Service', icon: 'tool' },
  { name: 'PlantAccount', label: 'Account', icon: 'user' },
]
const route = useRoute()
const FEW = 6 // up to this many machines: a small menu; more: a searchable list
const picking = ref(false)
const search = ref('')
const found = computed(() => {
  const q = search.value.trim().toLowerCase()
  return (plant.me?.machines || []).filter((m) => !q || [m.equipment_name, m.site, m.tag, m.name].some((v) => String(v || '').toLowerCase().includes(q)))
})
function openPicker() {
  search.value = ''
  picking.value = true
}
const isActive = (t) => route.name === t.name || route.matched.some((r) => r.name === t.name)
const router = useRouter()
onMounted(() => {
  // A manager opening the preview from a machine page: /plant?preview=EQ-…
  if (route.query.preview) setPreview(String(route.query.preview))
  loadPlant().catch(() => {})
})
function leavePreview() {
  const eq = window.__techyPreview
  setPreview(null)
  router.push(eq ? { name: 'OpsEquipmentDetail', params: { name: eq } } : { name: 'Home' })
}
</script>
