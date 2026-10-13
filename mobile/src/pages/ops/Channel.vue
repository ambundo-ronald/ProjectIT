<template>
  <div class="flex h-full">
    <!-- Main channel column -->
    <section class="flex min-w-0 flex-1 flex-col bg-white" :class="thread ? 'hidden lg:flex' : 'flex'">
      <header v-if="channel" class="flex h-16 shrink-0 items-center gap-3 border-b border-gray-200 px-4 md:px-6">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="channel.is_direct ? '' : 'bg-brand-50 text-brand-700'">
          <UserAvatar v-if="channel.is_direct" :name="channel.title" size="lg" />
          <FeatherIcon v-else :name="channel.is_private ? 'lock' : 'hash'" class="h-4 w-4" />
        </span>
        <div class="min-w-0 flex-1">
          <h1 class="truncate text-[16px] font-semibold">{{ channel.title }}</h1>
          <p class="truncate text-xs text-gray-500">{{ channel.description || (channel.is_direct ? 'Direct message' : `${channel.members.length} member${channel.members.length === 1 ? '' : 's'}`) }}<template v-if="channel.project"> · Project {{ channel.project }}</template></p>
        </div>
        <button class="btn btn-secondary btn-sm" :aria-label="`${channel.members.length} members`" @click="showMembers = true">
          <AvatarStack :people="channel.members" :max="3" size="sm" /><span class="hidden sm:inline">{{ channel.members.length }}</span>
        </button>
      </header>
      <p v-if="error" role="alert" class="bg-red-50 px-4 py-2 text-sm text-red-700">{{ error }}</p>

      <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-4" @scroll="onScroll">
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
            <span class="rounded-full border border-gray-200 bg-white px-3 py-0.5 text-[11px] font-semibold text-gray-600 shadow-sm">{{ dayLabel(m.creation) }}</span>
          </div>
          <Message :m="m" :compact="compact(i)" @reply="openThread(m)" @remove="remove(m)" />
        </template>
      </div>

      <div class="shrink-0 px-3 pb-3 pt-1 md:px-6 md:pb-5">
        <Composer v-if="channel?.is_member" ref="composer" :people="channel.members" :placeholder="`Message ${channel.is_direct ? channel.title : '#' + channel.title}`" :submit="(t) => send(t)" />
        <div v-else-if="channel" class="flex flex-col items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 p-4 text-center text-sm sm:flex-row sm:justify-between sm:text-left">
          <span>You're previewing <span class="font-semibold">#{{ channel.title }}</span>. Join to post and get notified.</span>
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="join">Join channel</button>
        </div>
      </div>
    </section>

    <!-- Thread panel -->
    <aside v-if="thread" class="flex w-full flex-col border-l border-gray-200 bg-white lg:w-[26rem]" aria-label="Thread">
      <header class="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 px-4">
        <div><h2 class="font-semibold">Thread</h2><p class="text-xs text-gray-500">{{ channel?.is_direct ? channel.title : `#${channel?.title}` }}</p></div>
        <button class="btn btn-ghost btn-icon" aria-label="Close thread" @click="thread = null"><FeatherIcon name="x" class="h-5 w-5" /></button>
      </header>
      <div ref="threadScroller" class="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-3">
        <Message :m="thread" thread-root />
        <div class="mx-2 my-3 flex items-center gap-3 text-xs font-medium text-gray-500"><span>{{ replies.length }} repl{{ replies.length === 1 ? 'y' : 'ies' }}</span><span class="h-px flex-1 bg-gray-200" /></div>
        <Message v-for="r in replies" :key="r.name" :m="r" thread-root @remove="remove(r)" />
      </div>
      <div class="shrink-0 px-3 pb-3 pt-1">
        <Composer v-if="channel?.is_member" :people="channel.members" placeholder="Reply…" :submit="(t) => send(t, thread.name)" />
      </div>
    </aside>

    <Modal v-model="showMembers" :title="channel?.is_direct ? 'Conversation' : `#${channel?.title}`" :subtitle="channel ? `${channel.members.length} member${channel.members.length === 1 ? '' : 's'}` : ''">
      <ul v-if="channel" class="divide-y divide-gray-100">
        <li v-for="p in channel.members" :key="p.user" class="flex items-center gap-3 py-2.5 text-sm">
          <UserAvatar :name="p.full_name" :image="p.image" size="md" />
          <span class="flex-1 font-medium">{{ p.full_name }}<span v-if="p.user === me.user" class="ml-1 font-normal text-gray-400">(you)</span></span>
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
import { ref, computed, nextTick, onMounted, onBeforeUnmount, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import AvatarStack from '@/components/ops/AvatarStack.vue'
import Composer from '@/components/ops/Composer.vue'
import Modal from '@/components/ops/Modal.vue'
import PeoplePicker from '@/components/ops/PeoplePicker.vue'
import RichText from '@/components/ops/RichText.vue'
import { api, me, onRealtime, formatTime, formatDate, fromNow } from '@/data/ops'
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
let atBottom = true

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
  if (m.system)
    return h('div', { class: 'my-2 flex items-center justify-center gap-2 px-2 text-xs text-gray-500' }, [
      h(FeatherIcon, { name: 'info', class: 'h-3.5 w-3.5 shrink-0' }),
      h(RichText, { text: m.content, names: names.value, class: 'inline' }),
    ])
  const own = m.user === me.user
  return h('div', { class: ['group relative flex gap-3 rounded-lg px-2 transition-colors hover:bg-gray-50', props.compact ? 'py-0.5' : 'mt-3 pb-0.5 pt-1'] }, [
    props.compact
      ? h('span', { class: 'w-9 shrink-0 pt-1 text-right text-[10px] text-transparent group-hover:text-gray-400' }, formatTime(m.creation))
      : h(UserAvatar, { name: m.full_name, image: m.image, size: 'lg', class: 'mt-0.5' }),
    h('div', { class: 'min-w-0 flex-1' }, [
      props.compact ? null : h('p', { class: 'flex items-baseline gap-2' }, [h('span', { class: 'text-[14px] font-semibold text-gray-900' }, m.full_name), h('span', { class: 'text-[11px] text-gray-400' }, formatTime(m.creation))]),
      h(RichText, { text: m.content, names: names.value, class: 'text-[14px] leading-relaxed text-gray-800' }),
      !props.threadRoot && m.reply_count
        ? h('button', { class: '-ml-1.5 mt-1 inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-semibold text-brand-700 hover:bg-brand-50', onClick: () => emit('reply') }, [
            h(FeatherIcon, { name: 'corner-down-right', class: 'h-3.5 w-3.5' }),
            `${m.reply_count} repl${m.reply_count === 1 ? 'y' : 'ies'}`,
            m.last_reply ? h('span', { class: 'font-normal text-gray-400' }, `· ${fromNow(m.last_reply)}`) : null,
          ])
        : null,
    ]),
    h('div', { class: 'absolute -top-3 right-3 hidden gap-0.5 rounded-lg border border-gray-200 bg-white p-0.5 shadow-pop group-focus-within:flex group-hover:flex' }, [
      props.threadRoot ? null : h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800', 'aria-label': 'Reply in thread', title: 'Reply in thread', onClick: () => emit('reply') }, [h(FeatherIcon, { name: 'message-circle', class: 'h-4 w-4' })]),
      own || me.manager ? h('button', { class: 'rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600', 'aria-label': 'Delete message', title: 'Delete', onClick: () => emit('remove') }, [h(FeatherIcon, { name: 'trash-2', class: 'h-4 w-4' })]) : null,
    ]),
  ])
}
Message.props = ['m', 'compact', 'threadRoot']
Message.emits = ['reply', 'remove']

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

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [info, data] = await Promise.all([api('projectit.chat.get_channel', { name }), api('projectit.chat.get_messages', { channel: name })])
    channel.value = info
    messages.value = data.messages
    hasMore.value = data.has_more
    scrollToEnd()
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

function upsert(list, message) {
  if (!list.value.some((m) => m.name === message.name)) list.value = [...list.value, message]
}

async function send(content, threadName = null) {
  error.value = ''
  try {
    const message = await api('projectit.chat.post_message', { channel: name, content, thread: threadName })
    if (threadName) {
      upsert(replies, message)
      bumpReplies(threadName, message.creation)
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
  if (message.thread) {
    if (thread.value?.name === message.thread) {
      upsert(replies, message)
      scrollToEnd(threadScroller.value)
    }
    if (message.user !== me.user) bumpReplies(message.thread, message.creation)
    return
  }
  const follow = atBottom
  upsert(messages, message)
  if (follow) scrollToEnd()
  if (document.visibilityState === 'visible') markRead()
})

onMounted(() => {
  activeChannel.value = name
  load()
})
onBeforeUnmount(() => {
  stop()
  if (activeChannel.value === name) activeChannel.value = null
})
</script>
