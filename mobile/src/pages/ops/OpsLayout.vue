<template>
  <div class="ops flex h-[100dvh]">
    <!-- Desktop sidebar -->
    <aside class="hidden w-64 shrink-0 flex-col bg-brand-800 text-brand-100 md:flex">
      <div class="px-3 pb-3 pt-4"><AppSwitcher dark /></div>
      <div class="px-3">
        <button v-if="me.ops_access !== false" class="btn w-full bg-accent-400 text-brand-900 shadow-sm hover:bg-accent-500" @click="openNew()">
          <FeatherIcon name="plus" class="h-4 w-4" /> New work order
        </button>
      </div>
      <nav class="mt-4 space-y-0.5 px-3" aria-label="Ops">
        <router-link
          v-for="item in visibleNav"
          :key="item.name"
          :to="{ name: item.name }"
          class="flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors"
          :class="isActive(item) ? 'bg-white/10 text-white' : 'text-brand-100 hover:bg-white/5 hover:text-white'"
        >
          <FeatherIcon :name="item.icon" class="h-4 w-4 opacity-90" />
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="badge(item)" class="rounded-full px-1.5 text-[11px] font-semibold" :class="item.name === 'OpsChat' ? 'bg-red-500 text-white' : 'bg-white/15 text-white'">{{ badge(item) }}</span>
        </router-link>
      </nav>

      <div class="mt-6 flex min-h-0 flex-1 flex-col overflow-y-auto px-3 pb-3">
        <div class="flex items-center justify-between px-3 pb-1">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-brand-300">Channels</span>
          <router-link :to="{ name: 'OpsChat' }" class="rounded p-0.5 text-brand-300 hover:bg-white/10 hover:text-white" aria-label="Browse or create channels"><FeatherIcon name="plus" class="h-3.5 w-3.5" /></router-link>
        </div>
        <ChannelLink v-for="c in joined.filter((c) => !c.is_direct)" :key="c.name" :channel="c" />
        <p v-if="!joined.some((c) => !c.is_direct)" class="px-3 py-1 text-xs text-brand-300">No channels yet</p>
        <div class="mt-4 px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-brand-300">Direct messages</div>
        <ChannelLink v-for="c in joined.filter((c) => c.is_direct)" :key="c.name" :channel="c" />
        <p v-if="!joined.some((c) => c.is_direct)" class="px-3 py-1 text-xs text-brand-300">Message a teammate from Chat</p>
      </div>

      <div class="border-t border-white/10 p-2">
        <UserMenu align="left" placement="top">
          <template #trigger="{ open, toggle }">
            <button class="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-white/10" :aria-expanded="open" aria-haspopup="menu" @click="toggle">
              <span class="relative">
                <UserAvatar :name="me.full_name" :image="me.image" size="md" />
                <span class="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-brand-800" :class="online ? 'bg-green-400' : 'bg-gray-400'" :title="online ? 'Live updates on' : 'Live updates offline'" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium text-white">{{ me.full_name }}</span>
                <span class="block text-xs text-brand-300">{{ me.manager ? 'Manager' : me.ops_access === false ? (me.can_approve_parts ? 'Stock approvals' : 'Billing') : 'Technician' }}</span>
              </span>
              <FeatherIcon name="chevrons-up" class="h-4 w-4 text-brand-300" />
            </button>
          </template>
        </UserMenu>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <!-- Mobile app bar -->
      <header class="flex h-14 shrink-0 items-center gap-2 border-b border-gray-200 bg-white px-2 md:hidden">
        <button v-if="route.meta.back" class="btn btn-ghost btn-icon" aria-label="Back" @click="back"><FeatherIcon name="arrow-left" class="h-5 w-5" /></button>
        <AppSwitcher v-else compact />
        <h1 class="min-w-0 flex-1 truncate text-[17px] font-semibold">{{ title }}</h1>
        <span class="mr-1 h-2 w-2 rounded-full" :class="online ? 'bg-green-500' : 'bg-gray-300'" :title="online ? 'Live updates on' : 'Live updates offline'" />
        <UserMenu class="mr-1" />
      </header>
      <p v-if="error" role="alert" class="bg-red-50 px-4 py-2 text-sm text-red-700">{{ error }}</p>
      <RunningTimer />
      <main class="min-h-0 flex-1 overflow-y-auto" :class="route.name === 'OpsChannel' ? 'pb-16 md:pb-0' : 'pb-24 md:pb-0'">
        <router-view v-if="me.loaded" :key="route.path" />
        <div v-else-if="!error" class="space-y-3 p-6" aria-live="polite" aria-label="Loading">
          <div class="h-7 w-48 animate-pulse rounded bg-gray-200" />
          <div class="h-24 animate-pulse rounded-xl bg-gray-200" />
          <div class="h-24 animate-pulse rounded-xl bg-gray-200" />
        </div>
      </main>
      <!-- Mobile tab bar -->
      <nav v-if="me.ops_access !== false" class="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-gray-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" aria-label="Ops">
        <router-link v-for="item in nav.filter((i) => !i.desktop)" :key="item.name" :to="{ name: item.name }" class="relative flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="isActive(item) ? 'text-brand-700' : 'text-gray-500'">
          <span class="flex h-7 w-12 items-center justify-center rounded-full transition-colors" :class="isActive(item) ? 'bg-brand-50' : ''">
            <FeatherIcon :name="item.icon" class="h-5 w-5" />
          </span>
          {{ item.short }}
          <span v-if="badge(item)" class="absolute left-1/2 top-1 ml-2 min-w-[1.1rem] rounded-full px-1 text-center text-[10px] font-bold text-white" :class="item.name === 'OpsChat' ? 'bg-red-500' : 'bg-brand-600'">{{ badge(item) }}</span>
        </router-link>
      </nav>
    </div>
    <WorkOrderForm v-model="showNew" :asset="newAsset" :equipment="newEquipment" @saved="(r) => router.push({ name: 'OpsWorkOrder', params: { name: r.name } })" />
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, provide, ref, h } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import WorkOrderForm from '@/components/ops/WorkOrderForm.vue'
import AppSwitcher from '@/components/ops/AppSwitcher.vue'
import UserMenu from '@/components/ops/UserMenu.vue'
import RunningTimer from '@/components/ops/RunningTimer.vue'
import { me, loadMe, online, onRealtime } from '@/data/ops'
import { channels, loadChannels, listenForChat, unread } from '@/data/chat'

const route = useRoute()
const router = useRouter()
const error = ref('')
const showNew = ref(false)
const newAsset = ref(null)
const newEquipment = ref(null)

const nav = [
  { name: 'OpsWorkOrders', label: 'Work orders', short: 'Work', icon: 'tool', prefix: '/ops/work-orders' },
  { name: 'OpsRequests', label: 'Requests', short: 'Requests', icon: 'inbox', prefix: '/ops/requests' },
  { name: 'OpsEquipment', label: 'Equipment', short: 'Equipment', icon: 'droplet', prefix: ['/ops/equipment', '/ops/contracts', '/ops/assets'] },
  { name: 'OpsPM', label: 'Preventive maintenance', short: 'PM', icon: 'calendar', prefix: '/ops/pm' },
  { name: 'OpsProcedures', label: 'Procedures', short: 'Procedures', icon: 'clipboard', prefix: '/ops/procedures', desktop: true },
  { name: 'OpsPartsRequests', label: 'Parts requests', short: 'Parts', icon: 'package', prefix: '/ops/parts-requests', desktop: true, show: () => me.can_approve_parts },
  { name: 'OpsBilling', label: 'Billing', short: 'Billing', icon: 'file-text', prefix: '/ops/billing', desktop: true, show: () => me.can_invoice },
  { name: 'OpsReports', label: 'Reports', short: 'Reports', icon: 'bar-chart-2', prefix: '/ops/reports', desktop: true, show: () => me.manager },
  { name: 'OpsChat', label: 'Chat', short: 'Chat', icon: 'message-circle', prefix: '/ops/chat' },
]
// Without the Ops module (e.g. a stock keeper) only the queues the user's roles allow are shown.
const visibleNav = computed(() => nav.filter((i) => (!i.show || i.show()) && (me.ops_access !== false || i.show)))
const isActive = (item) => [].concat(item.prefix).some((p) => route.path.startsWith(p))
const title = computed(() => route.meta.title || nav.find(isActive)?.label || 'Techy Ops')
const joined = computed(() => channels.value.filter((c) => c.is_member))
const cap = (n) => (n > 99 ? '99+' : n || 0)
function badge(item) {
  if (item.name === 'OpsChat') return cap(unread.value)
  if (item.name === 'OpsWorkOrders') return cap(me.counts?.work_orders)
  if (item.name === 'OpsRequests') return cap(me.counts?.pending_requests)
  if (item.name === 'OpsPartsRequests') return cap(me.counts?.pending_parts)
  return 0
}

function back() {
  if (window.history.state?.back) router.back()
  else router.push({ name: nav.find(isActive)?.name || 'OpsWorkOrders' })
}

// openNew(asset) for one of our assets, or openNew({ equipment }) for customer equipment.
function openNew(target = null) {
  newAsset.value = target?.equipment ? null : target
  newEquipment.value = target?.equipment || null
  showNew.value = true
}
provide('openNewWorkOrder', openNew)

const ChannelLink = (props) =>
  h(
    RouterLink,
    {
      to: { name: 'OpsChannel', params: { channel: props.channel.name } },
      class: [
        'flex h-8 items-center gap-2 rounded-lg px-3 text-sm transition-colors',
        route.params.channel === props.channel.name ? 'bg-white/10 text-white' : 'hover:bg-white/5',
        props.channel.unread ? 'font-semibold text-white' : 'text-brand-100',
      ],
    },
    () => [
      props.channel.is_direct
        ? h(UserAvatar, { name: props.channel.title, size: 'xs' })
        : h(FeatherIcon, { name: props.channel.is_private ? 'lock' : 'hash', class: 'h-3.5 w-3.5 text-brand-300' }),
      h('span', { class: 'min-w-0 flex-1 truncate' }, props.channel.title),
      props.channel.unread ? h('span', { class: 'rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white' }, props.channel.unread) : null,
    ],
  )
ChannelLink.props = ['channel']

let timer = null
const stop = onRealtime('techy_work_order', () => {
  clearTimeout(timer)
  timer = setTimeout(() => loadMe(true).catch(() => {}), 1500)
})
onMounted(async () => {
  try {
    await loadMe()
    await loadChannels()
    listenForChat()
  } catch (e) {
    error.value = e.message
  }
})
onBeforeUnmount(stop)
</script>
