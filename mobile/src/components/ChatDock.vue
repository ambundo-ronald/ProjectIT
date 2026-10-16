<template>
  <div v-if="visible || (session.isLoggedIn && shownPopups.length)" class="ops contents">
    <!-- Incoming message pop-ups: banners at the top on phones, cards above the bubble on desktop -->
    <TransitionGroup tag="div" class="pointer-events-none fixed inset-x-3 top-3 z-[70] flex flex-col gap-2 md:inset-x-auto md:right-6 md:w-[22rem]" :class="dock.open ? 'md:top-4' : 'md:bottom-28 md:top-auto md:flex-col-reverse'" enter-from-class="opacity-0 -translate-y-2 md:translate-y-2" leave-to-class="opacity-0" enter-active-class="transition duration-200" leave-active-class="transition duration-150" aria-live="polite">
      <div v-for="p in shownPopups" :key="p.id" class="pointer-events-auto flex w-full items-start gap-3 rounded-2xl border border-gray-200 bg-white/95 p-3 text-left shadow-pop backdrop-blur">
        <button class="flex min-w-0 flex-1 items-start gap-3 text-left" :aria-label="`Open message from ${p.name}`" @click="openFromPopup(p)">
          <span v-if="p.sticky" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700"><FeatherIcon name="clock" class="h-4 w-4" /></span>
          <UserAvatar v-else :name="p.name" :image="p.image" size="lg" />
          <span class="min-w-0 flex-1">
            <span class="flex items-baseline gap-2"><span class="truncate text-sm font-semibold text-gray-900">{{ p.name }}</span><span class="shrink-0 text-[11px] text-gray-400">{{ p.where }}</span></span>
            <span class="mt-0.5 line-clamp-2 block text-[13px] text-gray-600">{{ p.body }}</span>
          </span>
        </button>
        <button class="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700" aria-label="Dismiss" @click="dismiss(p)"><FeatherIcon name="x" class="h-4 w-4" /></button>
      </div>
    </TransitionGroup>

    <template v-if="visible">
    <!-- Floating chat bubble -->
    <button
      v-show="!dock.open"
      class="fixed right-4 z-[45] flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-pop transition hover:scale-105 hover:bg-brand-700 active:scale-95 md:bottom-6 md:right-6"
      :style="{ bottom: isPhone ? `calc(${5.25 + ui.dockLift / 16}rem + env(safe-area-inset-bottom))` : undefined }"
      :aria-label="unread ? `Chat, ${unread} unread` : 'Chat'"
      @click="openDock(null)"
    >
      <FeatherIcon name="message-circle" class="h-6 w-6" />
      <span v-if="unread" class="absolute -right-1 -top-1 flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-bold ring-2 ring-white" :class="pulse ? 'animate-bounce' : ''">{{ unread > 99 ? '99+' : unread }}</span>
    </button>

    <!-- Chat panel -->
    <Transition enter-from-class="opacity-0 translate-y-4" leave-to-class="opacity-0 translate-y-4" enter-active-class="transition duration-200" leave-active-class="transition duration-150">
      <section v-if="dock.open" class="fixed inset-0 z-[65] flex flex-col bg-white md:inset-auto md:bottom-6 md:right-6 md:h-[min(620px,calc(100dvh-3rem))] md:w-[400px] md:rounded-2xl md:border md:border-gray-200 md:shadow-pop" role="dialog" aria-label="Chat" @keydown.esc="close">
        <!-- Header -->
        <header class="flex h-14 shrink-0 items-center gap-2 border-b border-gray-200 px-2 pt-[env(safe-area-inset-top)] md:rounded-t-2xl">
          <button v-if="dock.channel || picking" class="btn btn-ghost btn-icon" aria-label="Back to conversations" @click="back"><FeatherIcon name="arrow-left" class="h-5 w-5" /></button>
          <span v-else class="ml-2 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="message-circle" class="h-4 w-4" /></span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-[15px] font-semibold">{{ picking ? 'New message' : dock.channel ? channelTitle : 'Chat' }}</p>
            <p v-if="dock.channel && info" class="truncate text-xs text-gray-500">{{ info.is_direct ? 'Direct message' : `${info.members.length} members` }}</p>
          </div>
          <router-link v-if="hasOps" :to="dock.channel ? { name: 'OpsChannel', params: { channel: dock.channel } } : { name: 'OpsChat' }" class="btn btn-ghost btn-icon" title="Open full chat" aria-label="Open full chat" @click="close"><FeatherIcon name="maximize-2" class="h-4 w-4" /></router-link>
          <button class="btn btn-ghost btn-icon" aria-label="Close chat" @click="close"><FeatherIcon name="x" class="h-5 w-5" /></button>
        </header>

        <!-- New direct message -->
        <div v-if="picking" class="p-4">
          <PeoplePicker :model-value="[]" single placeholder="Find a teammate" @update:model-value="(u) => startDirect(u[0])" />
          <p v-if="error" role="alert" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Conversation list -->
        <div v-else-if="!dock.channel" class="flex min-h-0 flex-1 flex-col">
          <div v-if="notify.supported && notify.permission === 'default'" class="m-3 flex items-center gap-3 rounded-xl bg-brand-50 p-3 text-sm">
            <FeatherIcon name="bell" class="h-5 w-5 shrink-0 text-brand-600" />
            <span class="flex-1 text-brand-900">Get notified about new messages while you're in another app.</span>
            <button class="btn btn-primary btn-sm" @click="setNotifications(true)">Turn on</button>
          </div>
          <ul class="min-h-0 flex-1 overflow-y-auto py-1">
            <li v-for="c in sorted" :key="c.name">
              <button class="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50" @click="dock.channel = c.name">
                <UserAvatar v-if="c.is_direct" :name="c.title" size="lg" />
                <span v-else class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="c.is_member ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-500'"><FeatherIcon :name="c.is_private ? 'lock' : 'hash'" class="h-4 w-4" /></span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-sm" :class="c.unread ? 'font-bold text-gray-900' : 'font-medium text-gray-800'">{{ c.title }}</span>
                  <span class="block truncate text-xs text-gray-500">{{ c.is_direct ? 'Direct message' : c.is_member ? c.description || 'Channel' : 'Tap to preview and join' }}</span>
                </span>
                <span v-if="c.unread" class="rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white">{{ c.unread }}</span>
              </button>
            </li>
            <li v-if="!sorted.length" class="px-6 py-10 text-center text-sm text-gray-500">No conversations yet. Start one with a teammate.</li>
          </ul>
          <div class="border-t border-gray-100 p-3 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
            <button class="btn btn-secondary w-full" @click="picking = true"><FeatherIcon name="edit" class="h-4 w-4" />New message</button>
          </div>
        </div>

        <!-- Conversation -->
        <template v-else>
          <div ref="scroller" class="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-3" @load.capture="scrollToEnd">
            <p v-if="loading" class="py-10 text-center text-sm text-gray-400">Loading…</p>
            <p v-else-if="!messages.length" class="py-10 text-center text-sm text-gray-500">No messages yet. Say hello 👋</p>
            <template v-for="(m, i) in messages" :key="m.name">
              <div v-if="m.ephemeral" class="my-1 rounded-lg border border-brand-100 bg-brand-50/60 px-2.5 py-1.5 text-xs" role="status">
                <p class="mb-0.5 text-[10px] text-gray-500">/{{ m.command }} · Only you can see this</p>
                <RichText :text="m.content" :names="names" class="whitespace-pre-line" />
              </div>
              <p v-else-if="m.system" class="py-1 text-center text-[11px] text-gray-400">{{ preview(m, names) }}</p>
              <div v-else class="flex items-end gap-2" :class="m.user === me.user ? 'flex-row-reverse' : ''">
                <UserAvatar v-if="m.user !== me.user" :name="m.full_name" :image="m.image" size="sm" :class="sameAuthor(i) ? 'invisible' : ''" />
                <div class="max-w-[78%]">
                  <p v-if="m.user !== me.user && !sameAuthor(i)" class="mb-0.5 ml-1 text-[11px] font-medium text-gray-500">{{ m.full_name }}</p>
                  <div v-if="m.photos?.length" class="mb-1 flex flex-wrap gap-1" :class="m.user === me.user ? 'justify-end' : ''">
                    <a v-for="p in m.photos" :key="p.name" :href="p.url" target="_blank" rel="noopener" class="block overflow-hidden rounded-xl border border-gray-200" :class="m.photos.length === 1 ? 'max-w-[14rem] bg-gray-100' : 'h-24 w-24'">
                      <img :src="p.url" alt="Photo" loading="lazy" :class="m.photos.length === 1 ? 'max-h-60 min-h-[5rem] min-w-[7rem] object-cover' : 'h-full w-full object-cover'" />
                    </a>
                  </div>
                  <div v-if="m.content" class="rounded-2xl px-3 py-2 text-[14px] leading-snug" :class="m.user === me.user ? 'rounded-br-md bg-brand-600 text-white' : 'rounded-bl-md bg-gray-100 text-gray-900'">
                    <RichText :text="m.content" :names="names" :inverse="m.user === me.user" />
                  </div>
                  <p class="mt-0.5 px-1 text-[10px] text-gray-400" :class="m.user === me.user ? 'text-right' : ''">{{ formatTime(m.creation) }}<template v-if="m.reply_count"> · {{ m.reply_count }} repl{{ m.reply_count === 1 ? 'y' : 'ies' }}</template></p>
                </div>
              </div>
            </template>
          </div>
          <p v-if="error" role="alert" class="mx-3 mb-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
          <div class="shrink-0 border-t border-gray-100 p-3 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
            <Composer v-if="info?.is_member" :people="info.members" :placeholder="`Message ${channelTitle}`" photos :submit="send" />
            <button v-else-if="info" class="btn btn-primary w-full" @click="join">Join #{{ info.title }}</button>
          </div>
        </template>
      </section>
    </Transition>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from './ops/UserAvatar.vue'
import Composer from './ops/Composer.vue'
import RichText from './ops/RichText.vue'
import PeoplePicker from './ops/PeoplePicker.vue'
import { api, me, loadMe, onRealtime, formatTime } from '@/data/ops'
import { channels, unread, popups, dock, notify, activeChannel, loadChannels, listenForChat, openDock, setNotifications, preview, commandReply } from '@/data/chat'
import { myApps, loadApps, ui } from '@/data/apps'
import { startPresence } from '@/data/presence'
import { session } from '@/data/session'

const route = useRoute()
const router = useRouter()
const ready = ref(false)
const info = ref(null)
const messages = ref([])
const loading = ref(false)
const error = ref('')
const picking = ref(false)
const scroller = ref(null)
const pulse = ref(false)
const isPhone = ref(window.innerWidth < 768)

const hidden = computed(() => ['Login', 'PublicRequest'].includes(route.name) || route.path.startsWith('/ops/chat'))
const visible = computed(() => ready.value && session.isLoggedIn && !hidden.value)
// On the chat pages the bubble is hidden, but reminders still pop up there.
const shownPopups = computed(() => (visible.value ? popups.value : popups.value.filter((p) => p.sticky)))
const hasOps = computed(() => (myApps.value || []).some((a) => a.module === 'Ops'))
const sorted = computed(() => [...channels.value].sort((a, b) => (b.unread || 0) - (a.unread || 0) || Number(b.is_member) - Number(a.is_member) || a.title.localeCompare(b.title)))
const channelTitle = computed(() => {
  const row = channels.value.find((c) => c.name === dock.channel)
  return info.value?.is_direct ? info.value.title : `#${info.value?.title || row?.title || ''}`
})
const names = computed(() => Object.fromEntries((info.value?.members || []).map((p) => [p.user, p.full_name])))
const sameAuthor = (i) => i > 0 && !messages.value[i - 1].system && messages.value[i - 1].user === messages.value[i].user

async function start() {
  if (ready.value || !session.isLoggedIn || hidden.value) return
  try {
    await loadMe()
    await loadChannels()
    listenForChat()
    startPresence()
    loadApps()
    ready.value = true
  } catch (e) {
    // Not a staff account (or chat unavailable): no bubble.
  }
}

function scrollToEnd() {
  nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight))
}

async function markRead(name) {
  const row = channels.value.find((c) => c.name === name)
  if (row) row.unread = 0
  try {
    await api('projectit.chat.mark_read', { channel: name })
  } catch (e) {
    /* non-member preview */
  }
}

async function openChannel(name) {
  error.value = ''
  info.value = null
  messages.value = []
  if (!name) return
  loading.value = true
  activeChannel.value = name
  try {
    const [channel, data] = await Promise.all([api('projectit.chat.get_channel', { name }), api('projectit.chat.get_messages', { channel: name, limit: 40 })])
    if (dock.channel !== name) return
    info.value = channel
    messages.value = data.messages
    scrollToEnd()
    if (channel.is_member) markRead(name)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function send(content, photos = []) {
  error.value = ''
  try {
    const result = await api('projectit.chat.post_message', { channel: dock.channel, content, photos })
    const message = result.command ? commandReply(result) : result
    if (!messages.value.some((m) => m.name === message.name)) messages.value = [...messages.value, message]
    scrollToEnd()
  } catch (e) {
    error.value = e.message
    throw e
  }
}

async function join() {
  try {
    info.value = await api('projectit.chat.join_channel', { name: dock.channel })
    await loadChannels()
  } catch (e) {
    error.value = e.message
  }
}

async function startDirect(user) {
  if (!user) return
  try {
    const { name } = await api('projectit.chat.open_direct', { user })
    await loadChannels()
    picking.value = false
    dock.channel = name
  } catch (e) {
    error.value = e.message
  }
}

function back() {
  if (picking.value) picking.value = false
  else dock.channel = null
}

function close() {
  dock.open = false
  picking.value = false
}

function openFromPopup(p) {
  dismiss(p)
  // A reminder opens its message in the chat page; a new message opens in the panel.
  if (p.message) router.push({ name: 'OpsChannel', params: { channel: p.channel }, query: { message: p.message } })
  else openDock(p.channel)
}

function dismiss(p) {
  popups.value = popups.value.filter((x) => x.id !== p.id)
}

watch(() => dock.channel, (name) => dock.open && openChannel(name))
watch(() => dock.open, (open) => {
  if (open) openChannel(dock.channel)
  else activeChannel.value = route.params.channel || null
})

// Pop-ups disappear on their own after a few seconds.
watch(popups, (list, old) => {
  const fresh = list.filter((p) => !(old || []).some((o) => o.id === p.id))
  for (const p of fresh) if (!p.sticky) setTimeout(() => dismiss(p), 7000) // reminders stay until dismissed
  if (fresh.length) {
    pulse.value = true
    setTimeout(() => (pulse.value = false), 1200)
  }
})

const stop = onRealtime('techy_chat', ({ channel, message }) => {
  if (!dock.open || channel !== dock.channel || message.thread) return
  if (!messages.value.some((m) => m.name === message.name)) messages.value = [...messages.value, message]
  scrollToEnd()
  if (message.user !== me.user && document.visibilityState === 'visible') markRead(channel)
})

const onResize = () => (isPhone.value = window.innerWidth < 768)
watch(() => [session.isLoggedIn, route.name], start)
onMounted(() => {
  start()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  stop()
  window.removeEventListener('resize', onResize)
})
</script>
