<template>
  <div class="flex h-full">
    <!-- Main channel column -->
    <section class="flex min-w-0 flex-1 flex-col bg-panel" :class="thread ? 'hidden lg:flex' : 'flex'">
      <header v-if="channel" class="flex h-16 shrink-0 items-center gap-3 border-b border-gray-200 px-4 md:px-6">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="channel.is_direct ? '' : 'bg-brand-50 text-brand-700'">
          <span v-if="channel.is_direct" class="relative"><UserAvatar :name="channel.title" size="lg" /><PresenceDot :user="channel.other" class="absolute -bottom-0.5 -right-0.5" /></span>
          <FeatherIcon v-else :name="channel.is_private ? 'lock' : 'hash'" class="h-4 w-4" />
        </span>
        <div class="min-w-0 flex-1">
          <h1 class="truncate text-[16px] font-semibold">{{ channel.title }}</h1>
          <p class="truncate text-xs text-gray-500">{{ channel.is_direct ? [presence[channel.other]?.online ? 'Online' : presence[channel.other]?.away ? 'Away' : 'Offline', statusLine(presence[channel.other])].filter(Boolean).join(' · ') : channel.description || `${channel.members.length} member${channel.members.length === 1 ? '' : 's'}` }}<template v-if="channel.project"> · Project {{ channel.project }}</template></p>
        </div>
        <button class="btn btn-ghost btn-icon" aria-label="Search this conversation" title="Search" @click="openSearch"><FeatherIcon name="search" class="h-4 w-4" /></button>
        <button class="btn btn-ghost btn-sm" :aria-label="`Pinned messages (${pinCount})`" title="Pinned messages" @click="openPins"><FeatherIcon name="bookmark" class="h-4 w-4" /><span v-if="pinCount" class="text-xs">{{ pinCount }}</span></button>
        <button class="btn btn-secondary btn-sm" :aria-label="`${channel.members.length} members`" @click="showMembers = true">
          <AvatarStack :people="channel.members" :max="3" size="sm" /><span class="hidden sm:inline">{{ channel.members.length }}</span>
        </button>
      </header>
      <p v-if="error" role="alert" class="bg-red-50 px-4 py-2 text-sm text-red-700">{{ error }}</p>

      <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-4" @scroll="onScroll" @load.capture="atBottom && !hasNewer && !highlight && scrollToEnd()">
        <div v-if="loading" class="space-y-4 px-2" aria-label="Loading">
          <div v-for="i in 4" :key="i" class="flex gap-3"><div class="h-9 w-9 animate-pulse rounded-full bg-gray-200" /><div class="flex-1 space-y-2"><div class="h-3 w-32 animate-pulse rounded bg-gray-200" /><div class="h-3 w-2/3 animate-pulse rounded bg-gray-100" /></div></div>
        </div>
        <button v-if="hasMore" class="btn btn-ghost btn-sm mx-auto mb-3 flex" :disabled="loadingOlder" @click="older">Load earlier messages</button>
        <div v-if="channel && !messages.length && !loading" class="flex flex-col items-center px-6 py-16 text-center">
          <span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><FeatherIcon :name="channel.is_direct ? 'message-circle' : 'hash'" class="h-6 w-6" /></span>
          <p class="mt-3 font-semibold">{{ channel.is_direct ? `This is the start of your conversation with ${channel.title}` : `Welcome to #${channel.title}` }}</p>
          <p class="mt-1 text-sm text-gray-500">Share updates, @mention teammates, or link a work order with its #ID.</p>
        </div>
        <template v-for="(m, i) in messages" :key="m.name">
          <div v-if="newDay(i)" class="sticky top-0 z-10 my-3 flex justify-center">
            <span class="rounded-full border border-gray-200 bg-panel px-3 py-0.5 text-[11px] font-semibold text-gray-600 shadow-sm">{{ dayLabel(m.creation) }}</span>
          </div>
          <Message :m="m" :compact="compact(i)" @reply="openThread(m)" @remove="remove(m)" @job="toJob(m)" @dismiss="dismiss" />
        </template>
        <button v-if="hasNewer" class="btn btn-secondary btn-sm mx-auto mt-3 flex" @click="load()"><FeatherIcon name="arrow-down" class="h-4 w-4" />Jump to latest messages</button>
      </div>
      <p class="h-5 shrink-0 truncate px-5 text-xs italic text-gray-500 md:px-7" aria-live="polite">{{ typingLine(null) }}</p>

      <div class="shrink-0 px-3 pb-3 pt-1 md:px-6 md:pb-5">
        <Composer v-if="channel?.is_member" ref="composer" :people="channel.members" :placeholder="`Message ${channel.is_direct ? channel.title : '#' + channel.title}`" photos :submit="(t, p) => send(t, null, p)" @typing="sayTyping(null)" />
        <div v-else-if="channel" class="flex flex-col items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 p-4 text-center text-sm sm:flex-row sm:justify-between sm:text-left">
          <span>You're previewing <span class="font-semibold">#{{ channel.title }}</span>. Join to post and get notified.</span>
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="join">Join channel</button>
        </div>
      </div>
    </section>

    <!-- Thread panel -->
    <aside v-if="thread" class="flex w-full flex-col border-l border-gray-200 bg-panel lg:w-[26rem]" aria-label="Thread">
      <header class="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 px-4">
        <div><h2 class="font-semibold">Thread</h2><p class="text-xs text-gray-500">{{ channel?.is_direct ? channel.title : `#${channel?.title}` }}</p></div>
        <button class="btn btn-ghost btn-icon" aria-label="Close thread" @click="thread = null"><FeatherIcon name="x" class="h-5 w-5" /></button>
      </header>
      <div ref="threadScroller" class="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-3" @load.capture="!highlight && scrollToEnd(threadScroller)">
        <Message :m="thread" thread-root @job="toJob(thread)" />
        <div class="mx-2 my-3 flex items-center gap-3 text-xs font-medium text-gray-500"><span>{{ replies.length }} repl{{ replies.length === 1 ? 'y' : 'ies' }}</span><span class="h-px flex-1 bg-gray-200" /></div>
        <Message v-for="r in replies" :key="r.name" :m="r" thread-root @remove="remove(r)" @job="toJob(r)" @dismiss="dismiss" />
      </div>
      <p class="h-5 shrink-0 truncate px-4 text-xs italic text-gray-500" aria-live="polite">{{ typingLine(thread.name) }}</p>
      <div class="shrink-0 px-3 pb-3 pt-1">
        <Composer v-if="channel?.is_member" :people="channel.members" placeholder="Reply…" photos :submit="(t, p) => send(t, thread.name, p)" @typing="sayTyping(thread.name)" />
      </div>
    </aside>

    <Modal v-model="showPins" title="Pinned messages" :subtitle="channel?.is_direct ? channel.title : `#${channel?.title}`">
      <p v-if="pinsLoading" class="py-6 text-center text-sm text-gray-400">Loading…</p>
      <p v-else-if="!pinned.length" class="py-6 text-center text-sm text-gray-500">Nothing pinned yet. Pin a message from its <FeatherIcon name="bookmark" class="inline h-3.5 w-3.5" /> button so everyone can find it.</p>
      <ul v-else class="divide-y divide-gray-100">
        <li v-for="p in pinned" :key="p.name" class="py-3">
          <p class="flex items-baseline gap-2 text-sm"><span class="font-semibold">{{ p.full_name }}</span><span class="text-xs text-gray-400">{{ formatDate(p.creation) }}</span></p>
          <RichText v-if="p.content" :text="p.content" :names="names" class="mt-0.5 line-clamp-3 text-sm text-gray-700" />
          <p v-if="p.photos.length" class="mt-0.5 text-xs text-gray-500">📷 {{ p.photos.length === 1 ? 'Photo' : `${p.photos.length} photos` }}</p>
          <div class="mt-1.5 flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="showPins = false; jump(p.name)">Show in chat</button>
            <button v-if="channel?.is_member" class="btn btn-ghost btn-sm text-gray-500" @click="togglePin(p, false)">Unpin</button>
          </div>
        </li>
      </ul>
    </Modal>

    <Modal v-model="showSearch" title="Search" :subtitle="`In ${channel?.is_direct ? channel.title : '#' + channel?.title}`">
      <form class="relative" role="search" @submit.prevent="runSearch">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input ref="searchInput" v-model="query" type="search" class="input pl-9" placeholder="Search messages" aria-label="Search messages" @input="searchSoon" />
      </form>
      <p v-if="searchError" class="mt-3 text-sm text-red-600">{{ searchError }}</p>
      <p v-else-if="searched && !results.length" class="py-6 text-center text-sm text-gray-500">No messages match “{{ searched }}”.</p>
      <ul class="mt-3 divide-y divide-gray-100">
        <li v-for="r in results" :key="r.message.name">
          <button class="w-full rounded-lg px-2 py-2.5 text-left hover:bg-gray-50" @click="showSearch = false; jump(r.message.name)">
            <p class="flex items-baseline gap-2 text-sm"><span class="font-semibold">{{ r.message.full_name }}</span><span class="text-xs text-gray-400">{{ formatDate(r.message.creation) }} · {{ formatTime(r.message.creation) }}</span><span v-if="r.message.thread" class="text-xs text-gray-400">· in a thread</span></p>
            <p class="mt-0.5 line-clamp-2 text-sm text-gray-700"><Highlight :text="r.message.content" :words="searched" /></p>
          </button>
        </li>
      </ul>
    </Modal>

    <Modal v-model="showMembers" :title="channel?.is_direct ? 'Conversation' : `#${channel?.title}`" :subtitle="channel ? `${channel.members.length} member${channel.members.length === 1 ? '' : 's'}` : ''">
      <ul v-if="channel" class="divide-y divide-gray-100">
        <li v-for="p in channel.members" :key="p.user" class="flex items-center gap-3 py-2.5 text-sm">
          <span class="relative"><UserAvatar :name="p.full_name" :image="p.image" size="md" /><PresenceDot :user="p.user" class="absolute -bottom-0.5 -right-0.5" /></span>
          <span class="min-w-0 flex-1"><span class="block font-medium">{{ p.full_name }}<span v-if="p.user === me.user" class="ml-1 font-normal text-gray-400">(you)</span></span><span v-if="statusLine(presence[p.user])" class="block truncate text-xs text-gray-500">{{ statusLine(presence[p.user]) }}</span></span>
          <button v-if="p.user !== me.user" class="btn btn-ghost btn-sm text-brand-700" @click="directMessage(p.user)"><FeatherIcon name="message-circle" class="h-4 w-4" />Message</button>
        </li>
      </ul>
      <div v-if="channel?.is_member && !channel.is_direct" class="mt-4 space-y-2 border-t border-gray-100 pt-4">
        <span class="label">Add people</span>
        <PeoplePicker v-model="adding" />
      </div>
      <template v-if="channel?.is_member && !channel.is_direct" #footer>
        <button class="btn btn-danger mr-auto" @click="leave">Leave channel</button>
        <button class="btn btn-primary" :disabled="!adding.length || busy" @click="addPeople">Add people</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount, h, inject, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import AvatarStack from '@/components/ops/AvatarStack.vue'
import Composer from '@/components/ops/Composer.vue'
import Modal from '@/components/ops/Modal.vue'
import PeoplePicker from '@/components/ops/PeoplePicker.vue'
import RichText from '@/components/ops/RichText.vue'
import { api, me, onRealtime, formatTime, formatDate, fromNow } from '@/data/ops'
import { REACTIONS, commandReply } from '@/data/chat'
import { presence, statusLine, watchPeople } from '@/data/presence'
import PresenceDot from '@/components/ops/PresenceDot.vue'
import { activeChannel, channels, loadChannels } from '@/data/chat'

const route = useRoute()
const router = useRouter()
const name = route.params.channel
const channel = ref(null)
const messages = ref([])
const hasMore = ref(false)
const loading = ref(true)
const loadingOlder = ref(false)
const busy = ref(false)
const error = ref('')
const thread = ref(null)
const replies = ref([])
const showMembers = ref(false)
const adding = ref([])
const scroller = ref(null)
const threadScroller = ref(null)
const hasNewer = ref(false) // showing older messages around a search result or pin
const highlight = ref('')
const picker = ref('') // message whose reaction picker is open
const reminding = ref('') // message whose "remind me" menu is open
const REMIND = [
  { when: '20m', label: 'In 20 minutes' },
  { when: '1h', label: 'In 1 hour' },
  { when: '3h', label: 'In 3 hours' },
  { when: 'tomorrow', label: 'Tomorrow at 8:00' },
  { when: 'monday', label: 'Next Monday at 8:00' },
]
const pinCount = ref(0)
const showPins = ref(false)
const pinned = ref([])
const pinsLoading = ref(false)
const showSearch = ref(false)
const searchInput = ref(null)
const query = ref('')
const searched = ref('')
const results = ref([])
const searchError = ref('')
const typers = ref({}) // user -> { full_name, thread, until }
let unwatchPeople = () => {}
let atBottom = true

/** The words matched in a search result, in bold. */
const Highlight = (props) => {
  const words = (props.words || '').trim()
  if (!words) return props.text
  const parts = String(props.text || '').split(new RegExp(`(${words.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig'))
  return parts.map((p, i) => (i % 2 ? h('mark', { class: 'rounded bg-amber-100 px-0.5 text-gray-900' }, p) : p))
}
Highlight.props = ['text', 'words']

const names = computed(() => Object.fromEntries((channel.value?.members || []).map((p) => [p.user, p.full_name])))

const sameDay = (a, b) => String(a).slice(0, 10) === String(b).slice(0, 10)
const newDay = (i) => i === 0 || !sameDay(messages.value[i - 1].creation, messages.value[i].creation)
const compact = (i) => {
  const prev = messages.value[i - 1]
  const m = messages.value[i]
  return !!prev && !newDay(i) && !prev.system && !m.system && prev.user === m.user && new Date(m.creation.replace(' ', 'T')) - new Date(prev.creation.replace(' ', 'T')) < 5 * 60000
}
function dayLabel(value) {
  const d = String(value).slice(0, 10)
  const today = new Date()
  const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
  if (d === iso(today)) return 'Today'
  if (d === iso(new Date(today.getTime() - 86400000))) return 'Yesterday'
  return formatDate(value)
}

const Message = (props, { emit }) => {
  const m = props.m
  if (m.ephemeral)
    return h('div', { class: 'my-2 rounded-lg border border-brand-100 bg-brand-50/60 px-3 py-2 text-sm', role: 'status' }, [
      h('div', { class: 'mb-1 flex items-center gap-2 text-[11px] text-gray-500' }, [
        h(FeatherIcon, { name: 'terminal', class: 'h-3.5 w-3.5' }),
        h('span', `/${m.command} · Only you can see this`),
        h('button', { type: 'button', class: 'ml-auto rounded px-1 hover:bg-panel hover:text-gray-800', 'aria-label': 'Dismiss', onClick: () => emit('dismiss', m) }, '✕'),
      ]),
      h(RichText, { text: m.content, names: names.value, class: 'whitespace-pre-line' }),
    ])
  if (m.system)
    return h('div', { class: 'my-2 flex items-center justify-center gap-2 px-2 text-xs text-gray-500' }, [
      h(FeatherIcon, { name: 'info', class: 'h-3.5 w-3.5 shrink-0' }),
      h(RichText, { text: m.content, names: names.value, class: 'inline' }),
    ])
  const own = m.user === me.user
  return h('div', { id: `msg-${m.name}`, class: ['group relative flex gap-3 rounded-lg px-2 transition-colors', highlight.value === m.name ? 'bg-amber-50 ring-1 ring-amber-200' : m.pinned ? 'bg-brand-50/40 hover:bg-gray-50' : 'hover:bg-gray-50', props.compact && !m.pinned ? 'py-0.5' : 'mt-3 pb-0.5 pt-1'] }, [
    props.compact
      ? h('span', { class: 'w-9 shrink-0 pt-1 text-right text-[10px] text-transparent group-hover:text-gray-400' }, formatTime(m.creation))
      : h(UserAvatar, { name: m.full_name, image: m.image, size: 'lg', class: 'mt-0.5' }),
    h('div', { class: 'min-w-0 flex-1' }, [
      m.pinned ? h('p', { class: 'mb-0.5 flex items-center gap-1 text-[11px] font-medium text-brand-700' }, [h(FeatherIcon, { name: 'bookmark', class: 'h-3 w-3' }), 'Pinned']) : null,
      props.compact ? null : h('p', { class: 'flex items-baseline gap-2' }, [h('span', { class: 'text-[14px] font-semibold text-gray-900' }, m.full_name), presence[m.user]?.emoji ? h('span', { class: 'text-[13px]', title: statusLine(presence[m.user]), 'aria-label': `Status: ${statusLine(presence[m.user])}` }, presence[m.user].emoji) : null, h('span', { class: 'text-[11px] text-gray-400' }, formatTime(m.creation))]),
      m.content ? h(RichText, { text: m.content, names: names.value, class: 'text-[14px] leading-relaxed text-gray-800' }) : null,
      m.photos?.length
        ? h('div', { class: 'mt-1.5 flex flex-wrap gap-1.5' }, m.photos.map((p, n) =>
            h('a', { href: p.url, target: '_blank', rel: 'noopener', class: ['block overflow-hidden rounded-lg border border-gray-200 bg-gray-100', m.photos.length === 1 ? 'w-fit max-w-[min(20rem,100%)]' : 'h-28 w-28'] }, [
              h('img', { src: p.url, alt: `Photo ${n + 1} from ${m.full_name}`, loading: 'lazy', class: m.photos.length === 1 ? 'max-h-72 min-h-[6rem] min-w-[8rem] object-cover' : 'h-full w-full object-cover' }),
            ])))
        : null,
      m.reactions?.length
        ? h('div', { class: 'mt-1 flex flex-wrap gap-1' }, m.reactions.map((r) => {
            const mine = r.users.includes(me.user)
            const who = r.users.map((u) => (u === me.user ? 'you' : names.value[u] || u)).join(', ')
            return h('button', { class: ['inline-flex h-6 items-center gap-1 rounded-full border px-2 text-xs transition', mine ? 'border-brand-300 bg-brand-50 font-semibold text-brand-800' : 'border-gray-200 bg-panel text-gray-700 hover:border-gray-300'], title: `${r.emoji} ${who}`, 'aria-label': `${r.emoji} ${r.users.length}, from ${who}. ${mine ? 'Remove your reaction' : 'Add yours'}`, 'aria-pressed': mine, disabled: !channel.value?.is_member, onClick: () => react(m, r.emoji) }, [h('span', r.emoji), h('span', String(r.users.length))])
          }))
        : null,
      !props.threadRoot && m.reply_count
        ? h('button', { class: '-ml-1.5 mt-1 inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-semibold text-brand-700 hover:bg-brand-50', onClick: () => emit('reply') }, [
            h(FeatherIcon, { name: 'corner-down-right', class: 'h-3.5 w-3.5' }),
            `${m.reply_count} repl${m.reply_count === 1 ? 'y' : 'ies'}`,
            m.last_reply ? h('span', { class: 'font-normal text-gray-400' }, `· ${fromNow(m.last_reply)}`) : null,
          ])
        : null,
    ]),
    h('div', { class: ['absolute -top-3 right-3 gap-0.5 rounded-lg border border-gray-200 bg-panel p-0.5 shadow-pop group-focus-within:flex group-hover:flex', picker.value === m.name || reminding.value === m.name ? 'flex' : 'hidden'] }, [
      picker.value === m.name
        ? h('div', { class: 'absolute bottom-full right-0 mb-1 flex gap-0.5 rounded-xl border border-gray-200 bg-panel p-1 shadow-pop', role: 'group', 'aria-label': 'Reactions' }, REACTIONS.map((e) =>
            h('button', { class: 'flex h-8 w-8 items-center justify-center rounded-lg text-lg hover:bg-gray-100', 'aria-label': `React with ${e}`, onClick: () => react(m, e) }, e)))
        : null,
      reminding.value === m.name
        ? h('div', { class: 'absolute right-0 top-full z-10 mt-1 w-52 rounded-xl border border-gray-200 bg-panel p-1 shadow-pop', role: 'menu', 'aria-label': 'Remind me' }, REMIND.map((r) =>
            h('button', { class: 'flex w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-gray-50', role: 'menuitem', onClick: () => remindMe(m, r) }, r.label)))
        : null,
      h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800', 'aria-label': 'Remind me about this', 'aria-expanded': reminding.value === m.name, title: 'Remind me', onClick: () => { picker.value = ''; reminding.value = reminding.value === m.name ? '' : m.name } }, [h(FeatherIcon, { name: 'clock', class: 'h-4 w-4' })]),
      channel.value?.is_member ? h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800', 'aria-label': 'Add reaction', 'aria-expanded': picker.value === m.name, title: 'Add reaction', onClick: () => (picker.value = picker.value === m.name ? '' : m.name) }, [h(FeatherIcon, { name: 'smile', class: 'h-4 w-4' })]) : null,
      channel.value?.is_member ? h('button', { class: ['rounded-md p-1.5 hover:bg-gray-100', m.pinned ? 'text-brand-700' : 'text-gray-500 hover:text-gray-800'], 'aria-label': m.pinned ? 'Unpin message' : 'Pin to this conversation', title: m.pinned ? 'Unpin' : 'Pin', onClick: () => togglePin(m, !m.pinned) }, [h(FeatherIcon, { name: 'bookmark', class: 'h-4 w-4' })]) : null,
      props.threadRoot ? null : h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800', 'aria-label': 'Reply in thread', title: 'Reply in thread', onClick: () => emit('reply') }, [h(FeatherIcon, { name: 'message-circle', class: 'h-4 w-4' })]),
      me.ops_access !== false ? h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800', 'aria-label': 'Create a work order from this message', title: 'Create work order', onClick: () => emit('job') }, [h(FeatherIcon, { name: 'tool', class: 'h-4 w-4' })]) : null,
      own || me.manager ? h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600', 'aria-label': 'Delete message', title: 'Delete', onClick: () => emit('remove') }, [h(FeatherIcon, { name: 'trash-2', class: 'h-4 w-4' })]) : null,
    ]),
  ])
}
Message.props = ['m', 'compact', 'threadRoot']
Message.emits = ['reply', 'remove', 'job', 'dismiss']

function scrollToEnd(el = scroller.value) {
  nextTick(() => el && (el.scrollTop = el.scrollHeight))
}
function onScroll() {
  const el = scroller.value
  atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

async function markRead() {
  if (!channel.value?.is_member) return
  const row = channels.value.find((c) => c.name === name)
  if (row) row.unread = 0
  try {
    me.unread = (await api('projectit.chat.mark_read', { channel: name })).unread
  } catch (e) {
    /* non-critical */
  }
}

async function load(around = null) {
  loading.value = true
  error.value = ''
  try {
    const [info, data] = await Promise.all([
      api('projectit.chat.get_channel', { name }),
      api('projectit.chat.get_messages', { channel: name, around: around || undefined }),
      loadPinCount(),
    ])
    channel.value = info
    unwatchPeople()
    unwatchPeople = watchPeople(info.members.map((p) => p.user))
    messages.value = data.messages
    hasMore.value = data.has_more
    hasNewer.value = data.has_newer
    if (data.focus) await focusOn(data.focus)
    else scrollToEnd()
    markRead()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function older() {
  loadingOlder.value = true
  const el = scroller.value
  const height = el.scrollHeight
  try {
    const data = await api('projectit.chat.get_messages', { channel: name, before: messages.value[0]?.creation })
    messages.value = [...data.messages, ...messages.value]
    hasMore.value = data.has_more
    nextTick(() => (el.scrollTop = el.scrollHeight - height))
  } catch (e) {
    error.value = e.message
  } finally {
    loadingOlder.value = false
  }
}

/** Scroll to a message (opening its thread for a reply) and highlight it for a few seconds. */
async function focusOn({ message, thread: root }) {
  if (root) {
    const rootMessage = messages.value.find((m) => m.name === root)
    if (rootMessage) await openThread(rootMessage)
  }
  highlight.value = message
  await nextTick()
  document.getElementById(`msg-${message}`)?.scrollIntoView({ block: 'center' })
  setTimeout(() => highlight.value === message && (highlight.value = ''), 4000)
}
async function jump(message) {
  const visible = messages.value.some((m) => m.name === message) || replies.value.some((m) => m.name === message)
  if (visible) {
    highlight.value = message
    await nextTick()
    document.getElementById(`msg-${message}`)?.scrollIntoView({ block: 'center' })
    return
  }
  await load(message)
}

async function loadPinCount() {
  try {
    pinCount.value = (await api('projectit.chat.pins', { channel: name })).length
  } catch (e) {
    /* non-critical */
  }
}
async function openPins() {
  showPins.value = true
  pinsLoading.value = true
  try {
    pinned.value = await api('projectit.chat.pins', { channel: name })
    pinCount.value = pinned.value.length
  } catch (e) {
    error.value = e.message
  } finally {
    pinsLoading.value = false
  }
}
async function togglePin(m, on) {
  try {
    await api('projectit.chat.pin', { message: m.name, pinned: on ? 1 : 0 })
    mark(m.name, { pinned: on })
    pinned.value = on ? pinned.value : pinned.value.filter((p) => p.name !== m.name)
    loadPinCount()
  } catch (e) {
    error.value = e.message
  }
}
async function remindMe(m, option) {
  reminding.value = ''
  try {
    await api('projectit.reminders.remind', { message: m.name, when: option.when })
    toast({ title: `I'll remind you ${option.label.charAt(0).toLowerCase()}${option.label.slice(1)}`, icon: 'clock', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  }
}
async function react(m, emoji) {
  picker.value = ''
  try {
    mark(m.name, { reactions: await api('projectit.chat.react', { message: m.name, emoji }) })
  } catch (e) {
    error.value = e.message
  }
}
/** Apply a reaction or pin change to every copy of the message on screen. */
function mark(message, changes) {
  for (const m of [...messages.value, ...replies.value, thread.value]) if (m?.name === message) Object.assign(m, changes)
  messages.value = [...messages.value]
  replies.value = [...replies.value]
  if (atBottom && !hasNewer.value) scrollToEnd() // a new reaction row on the last message stays in view
}

function openSearch() {
  showSearch.value = true
  nextTick(() => searchInput.value?.focus())
}
let searchTimer = null
function searchSoon() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(runSearch, 300)
}
async function runSearch() {
  const words = query.value.trim()
  searchError.value = ''
  if (words.length < 2) {
    results.value = []
    searched.value = ''
    return
  }
  try {
    results.value = await api('projectit.chat.search', { query: words, channel: name })
    searched.value = words
  } catch (e) {
    searchError.value = e.message
  }
}

// Typing: tell the others at most every 3 seconds; show who is typing for 6 seconds after their last signal.
let lastTyping = 0
function sayTyping(threadName) {
  if (Date.now() - lastTyping < 3000) return
  lastTyping = Date.now()
  api('projectit.chat.typing', { channel: name, thread: threadName }).catch(() => {})
}
function typingLine(threadName) {
  const who = Object.values(typers.value).filter((t) => (t.thread || null) === threadName).map((t) => t.full_name.split(' ')[0])
  if (!who.length) return ''
  return who.length === 1 ? `${who[0]} is typing…` : who.length === 2 ? `${who[0]} and ${who[1]} are typing…` : 'Several people are typing…'
}
function stopTyping(user) {
  if (!typers.value[user]) return
  const next = { ...typers.value }
  delete next[user]
  typers.value = next
}
const stopTypingEvents = onRealtime('techy_typing', (t) => {
  if (t.channel !== name || t.user === me.user) return
  typers.value = { ...typers.value, [t.user]: { full_name: t.full_name, thread: t.thread } }
  clearTimeout(typingTimers[t.user])
  typingTimers[t.user] = setTimeout(() => stopTyping(t.user), 6000)
})
const typingTimers = {}
const stopUpdates = onRealtime('techy_chat_update', ({ channel: target, message, ...changes }) => {
  if (target !== name) return
  mark(message, changes)
  if ('pinned' in changes) loadPinCount()
})

function upsert(list, message) {
  if (!list.value.some((m) => m.name === message.name)) list.value = [...list.value, message]
}

async function send(content, threadName = null, photos = []) {
  error.value = ''
  try {
    const result = await api('projectit.chat.post_message', { channel: name, content, thread: threadName, photos })
    const message = result.command ? commandReply(result) : result
    if (threadName) {
      upsert(replies, message)
      if (!message.ephemeral) bumpReplies(threadName, message.creation)
      scrollToEnd(threadScroller.value)
    } else {
      upsert(messages, message)
      scrollToEnd()
    }
  } catch (e) {
    error.value = e.message
    throw e
  }
}

// A command's answer only lives on this screen.
function dismiss(m) {
  messages.value = messages.value.filter((x) => x !== m)
  replies.value = replies.value.filter((x) => x !== m)
}

function bumpReplies(root, creation) {
  const m = messages.value.find((x) => x.name === root)
  if (m) Object.assign(m, { reply_count: (m.reply_count || 0) + 1, last_reply: creation })
}

async function openThread(m) {
  thread.value = m
  replies.value = []
  try {
    const data = await api('projectit.chat.get_messages', { channel: name, thread: m.name, limit: 100 })
    replies.value = data.messages
    m.reply_count = data.messages.length
    scrollToEnd(threadScroller.value)
  } catch (e) {
    error.value = e.message
  }
}

// Message to job: the new work order form opens filled in from the message (OpsLayout owns the form).
const openNewWorkOrder = inject('openNewWorkOrder', null)
const toJob = (m) => openNewWorkOrder?.({ message: { name: m.name, content: m.content, full_name: m.full_name, photos: m.photos?.length || 0, names: names.value } })

async function remove(m) {
  if (!window.confirm('Delete this message?')) return
  try {
    await api('projectit.chat.delete_message', { name: m.name })
    messages.value = messages.value.filter((x) => x.name !== m.name)
    replies.value = replies.value.filter((x) => x.name !== m.name)
    if (thread.value?.name === m.name) thread.value = null
  } catch (e) {
    error.value = e.message
  }
}

async function run(work) {
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
const join = () => run(async () => {
  channel.value = await api('projectit.chat.join_channel', { name })
  await loadChannels()
  markRead()
})
const addPeople = () => run(async () => {
  channel.value = await api('projectit.chat.add_members', { name, users: adding.value })
  adding.value = []
})
const leave = () => run(async () => {
  await api('projectit.chat.leave_channel', { name })
  await loadChannels()
  router.push({ name: 'OpsChat' })
})
const directMessage = (user) => run(async () => {
  const dm = await api('projectit.chat.open_direct', { user })
  showMembers.value = false
  await loadChannels()
  router.push({ name: 'OpsChannel', params: { channel: dm.name } })
})

const stop = onRealtime('techy_chat', ({ channel: target, message }) => {
  if (target !== name) return
  if (message.user) stopTyping(message.user)
  if (message.thread) {
    if (thread.value?.name === message.thread) {
      upsert(replies, message)
      scrollToEnd(threadScroller.value)
    }
    if (message.user !== me.user) bumpReplies(message.thread, message.creation)
    return
  }
  if (hasNewer.value) return // reading older messages; "Jump to latest" loads them
  const follow = atBottom
  upsert(messages, message)
  if (follow) scrollToEnd()
  if (document.visibilityState === 'visible') markRead()
})

onMounted(() => {
  activeChannel.value = name
  load(route.query.message ? String(route.query.message) : null)
})
// A search result in another screen links here with ?message=…
watch(() => route.query.message, (message) => message && jump(String(message)))
onBeforeUnmount(() => {
  stop()
  stopTypingEvents()
  stopUpdates()
  unwatchPeople()
  if (activeChannel.value === name) activeChannel.value = null
})
</script>
