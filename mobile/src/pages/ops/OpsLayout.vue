<template>
  <div class="ops flex h-[100dvh]">
    <!-- Desktop sidebar -->
    <aside class="palette-light hidden w-64 shrink-0 flex-col bg-brand-800 text-brand-100 md:flex">
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
      <header class="flex h-14 shrink-0 items-center gap-2 border-b border-gray-200 bg-panel px-2 md:hidden">
        <button v-if="route.meta.back" class="btn btn-ghost btn-icon" aria-label="Back" @click="back"><FeatherIcon name="arrow-left" class="h-5 w-5" /></button>
        <AppSwitcher v-else compact />
        <h1 class="min-w-0 flex-1 truncate text-[17px] font-semibold">{{ title }}</h1>
        <span class="mr-1 h-2 w-2 rounded-full" :class="online ? 'bg-green-500' : 'bg-gray-300'" :title="online ? 'Live updates on' : 'Live updates offline'" />
        <UserMenu class="mr-1" />
      </header>
      <p v-if="error" role="alert" class="bg-red-50 px-4 py-2 text-sm text-red-700">{{ error }}</p>
      <OfflineBar />
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
      <nav v-if="me.ops_access !== false" class="fixed inset-x-0 bottom-0 grid grid-cols-5 border-t border-gray-200 bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" :class="moreOpen ? 'z-[48]' : 'z-40'" aria-label="Ops">
        <router-link v-for="item in nav.filter((i) => i.tab)" :key="item.name" :to="{ name: item.name }" class="relative flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="isActive(item) && !moreOpen ? 'text-brand-700' : 'text-gray-500'">
          <span class="flex h-7 w-12 items-center justify-center rounded-full transition-colors" :class="isActive(item) && !moreOpen ? 'bg-brand-50' : ''">
            <FeatherIcon :name="item.icon" class="h-5 w-5" />
          </span>
          {{ item.short }}
          <span v-if="badge(item)" class="absolute left-1/2 top-1 ml-2 min-w-[1.1rem] rounded-full px-1 text-center text-[10px] font-bold text-white" :class="item.name === 'OpsChat' ? 'bg-red-500' : 'bg-brand-600'">{{ badge(item) }}</span>
        </router-link>
        <button type="button" class="relative flex flex-col items-center gap-0.5 pb-1.5 pt-2 text-[11px] font-medium" :class="moreOpen || moreActive ? 'text-brand-700' : 'text-gray-500'" aria-label="More pages" aria-haspopup="dialog" :aria-expanded="moreOpen" @click="moreOpen = !moreOpen">
          <span class="flex h-7 w-12 items-center justify-center rounded-full transition-colors" :class="moreOpen || moreActive ? 'bg-brand-50' : ''">
            <FeatherIcon name="grid" class="h-5 w-5" />
          </span>
          More
          <span v-if="moreBadge" class="absolute left-1/2 top-1 ml-2 min-w-[1.1rem] rounded-full bg-brand-600 px-1 text-center text-[10px] font-bold text-white">{{ moreBadge }}</span>
        </button>
      </nav>

      <!-- Mobile "More": every page that has no tab of its own. It sits above the chat bubble (z-45), with the tab
           bar lifted above it while open so More closes it again. -->
      <Transition enter-from-class="opacity-0" leave-to-class="opacity-0" enter-active-class="transition-opacity duration-150" leave-active-class="transition-opacity duration-150">
        <div v-if="moreOpen" class="fixed inset-0 z-[46] bg-black/30 md:hidden" @click="moreOpen = false" />
      </Transition>
      <Transition enter-from-class="translate-y-full" leave-to-class="translate-y-full" enter-active-class="transition-transform duration-200 ease-out" leave-active-class="transition-transform duration-150 ease-in">
        <div v-if="moreOpen" ref="moreSheet" class="fixed inset-x-0 bottom-0 z-[47] rounded-t-2xl bg-panel px-4 pb-[calc(5rem+env(safe-area-inset-bottom))] pt-3 shadow-pop md:hidden" role="dialog" aria-modal="true" aria-label="More" tabindex="-1">
          <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-200" aria-hidden="true" />
          <ul class="grid grid-cols-3 gap-2">
            <li v-for="item in moreItems" :key="item.name">
              <router-link :to="{ name: item.name }" class="relative flex flex-col items-center gap-1.5 rounded-xl px-1 py-3 text-center text-xs font-medium" :class="isActive(item) ? 'bg-brand-50 text-brand-700' : 'text-gray-700 hover:bg-gray-50'" @click="moreOpen = false">
                <FeatherIcon :name="item.icon" class="h-6 w-6" />
                {{ item.label }}
                <span v-if="badge(item)" class="absolute right-3 top-2 min-w-[1.1rem] rounded-full bg-brand-600 px-1 text-[10px] font-bold text-white">{{ badge(item) }}</span>
              </router-link>
            </li>
            <li>
              <router-link :to="{ name: 'Home' }" class="flex flex-col items-center gap-1.5 rounded-xl px-1 py-3 text-center text-xs font-medium text-gray-700 hover:bg-gray-50" @click="moreOpen = false">
                <FeatherIcon name="home" class="h-6 w-6" />All apps
              </router-link>
            </li>
          </ul>
        </div>
      </Transition>
    </div>
    <WorkOrderForm v-model="showNew" :asset="newAsset" :equipment="newEquipment" :message="newMessage" @saved="(r) => router.push({ name: 'OpsWorkOrder', params: { name: r.name } })" />
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, provide, ref, h, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import WorkOrderForm from '@/components/ops/WorkOrderForm.vue'
import AppSwitcher from '@/components/ops/AppSwitcher.vue'
import UserMenu from '@/components/ops/UserMenu.vue'
import RunningTimer from '@/components/ops/RunningTimer.vue'
import OfflineBar from '@/components/ops/OfflineBar.vue'
import { prefetch } from '@/data/offline'
import { me, loadMe, online, onRealtime } from '@/data/ops'
import { channels, loadChannels, listenForChat, unread } from '@/data/chat'
import { startPresence, watchPeople } from '@/data/presence'
import PresenceDot from '@/components/ops/PresenceDot.vue'

const route = useRoute()
const router = useRouter()
const error = ref('')
const showNew = ref(false)
const newAsset = ref(null)
const newEquipment = ref(null)
const newMessage = ref(null)

const nav = [
  { name: 'OpsWorkOrders', label: 'Work orders', short: 'Work', icon: 'tool', prefix: '/ops/work-orders', tab: true },
  { name: 'OpsRequests', label: 'Requests', short: 'Requests', icon: 'inbox', prefix: '/ops/requests', tab: true },
  { name: 'OpsEquipment', label: 'Equipment', short: 'Equipment', icon: 'droplet', prefix: ['/ops/equipment', '/ops/contracts', '/ops/assets'], tab: true },
  { name: 'OpsPM', label: 'Preventive maintenance', short: 'PM', icon: 'calendar', prefix: '/ops/pm' },
  { name: 'OpsDispatch', label: 'Dispatch', short: 'Dispatch', icon: 'columns', prefix: '/ops/dispatch', desktop: true, show: () => me.manager },
  { name: 'OpsInvestigations', label: 'Investigations', short: 'RCA', icon: 'crosshair', prefix: '/ops/investigations', desktop: true },
  { name: 'OpsProcedures', label: 'Procedures', short: 'Procedures', icon: 'clipboard', prefix: '/ops/procedures', desktop: true },
  { name: 'OpsPartsRequests', label: 'Parts requests', short: 'Parts', icon: 'package', prefix: '/ops/parts-requests', desktop: true, show: () => me.can_approve_parts },
  { name: 'OpsBilling', label: 'Billing', short: 'Billing', icon: 'file-text', prefix: '/ops/billing', desktop: true, show: () => me.can_invoice },
  { name: 'OpsReports', label: 'Reports', short: 'Reports', icon: 'bar-chart-2', prefix: '/ops/reports', desktop: true, show: () => me.manager },
  { name: 'OpsChat', label: 'Chat', short: 'Chat', icon: 'message-circle', prefix: '/ops/chat', tab: true },
]
// Without the Ops module (e.g. a stock keeper) only the queues the user's roles allow are shown.
const visibleNav = computed(() => nav.filter((i) => (!i.show || i.show()) && (me.ops_access !== false || i.show)))
const isActive = (item) => [].concat(item.prefix).some((p) => route.path.startsWith(p))
// Phones: four tabs (tab: true) and More for the rest, limited to what the person may open.
const moreOpen = ref(false)
const moreSheet = ref(null)
const moreItems = computed(() => visibleNav.value.filter((i) => !i.tab))
const moreActive = computed(() => moreItems.value.some(isActive))
const moreBadge = computed(() => moreItems.value.reduce((n, i) => n + (Number(badge(i)) || 0), 0))
watch(() => route.fullPath, () => (moreOpen.value = false))
const closeMore = (e) => e.key === 'Escape' && (moreOpen.value = false)
watch(moreOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', closeMore)
    setTimeout(() => moreSheet.value?.focus(), 50)
  } else window.removeEventListener('keydown', closeMore)
})
onBeforeUnmount(() => window.removeEventListener('keydown', closeMore))
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

// openNew(asset) for one of our assets, openNew({ equipment }) for customer equipment, or openNew({ message })
// for a chat message.
function openNew(target = null) {
  newAsset.value = target?.equipment || target?.message ? null : target
  newEquipment.value = target?.equipment || null
  newMessage.value = target?.message || null
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
        ? h('span', { class: 'relative shrink-0' }, [h(UserAvatar, { name: props.channel.title, size: 'xs' }), h(PresenceDot, { user: props.channel.other, ring: 'ring-brand-800', class: 'absolute -bottom-0.5 -right-0.5 !h-2 !w-2' })])
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
    // Save my open jobs on this phone for use without a connection (in the background).
    if (me.ops_access !== false) setTimeout(prefetch, 2000)
    await loadChannels()
    listenForChat()
    startPresence()
  } catch (e) {
    error.value = e.message
  }
})
// Online dots for the people in my direct messages.
let unwatch = () => {}
watch(() => channels.value.filter((c) => c.is_direct).map((c) => c.other).join(','), (users) => {
  unwatch()
  unwatch = watchPeople(users.split(',').filter(Boolean))
}, { immediate: true })
onBeforeUnmount(() => {
  stop()
  unwatch()
})
</script>
