import { ref, computed, reactive, watch } from 'vue'
import { api, me, onRealtime, tokens } from './ops'
import { KIND } from './links'

/** The reactions offered on messages (the server accepts only these). */
export const REACTIONS = ['👍', '✅', '👀', '🙏', '🎉', '❤️', '😂', '⚠️']

export const channels = ref([])
export const activeChannel = ref(null) // channel currently on screen (chat page or chat panel)
export const unread = computed(() => channels.value.reduce((sum, c) => sum + (c.is_member ? c.unread : 0), 0))

/** In-app pop-ups for incoming messages, newest first; ChatDock renders them. */
export const popups = ref([])
/** The chat panel, opened from the floating bubble or a pop-up. */
export const dock = reactive({ open: false, channel: null })

const NOTIFY_KEY = 'techy_chat_notifications'
const stored = (() => {
  try {
    return localStorage.getItem(NOTIFY_KEY)
  } catch (e) {
    return null
  }
})()
const supported = typeof window !== 'undefined' && 'Notification' in window
/** System notifications for messages that arrive while the app is in the background. */
export const notify = reactive({ supported, permission: supported ? Notification.permission : 'denied', enabled: supported && Notification.permission === 'granted' && stored !== 'off' })

export async function setNotifications(on) {
  if (!supported) return
  if (on && Notification.permission === 'default') notify.permission = await Notification.requestPermission()
  notify.enabled = on && notify.permission === 'granted'
  try {
    localStorage.setItem(NOTIFY_KEY, notify.enabled ? 'on' : 'off')
  } catch (e) {
    /* storage unavailable */
  }
}

export async function loadChannels() {
  channels.value = await api('projectit.chat.list_channels')
  me.unread = unread.value
  return channels.value
}

export function openDock(channel = null) {
  dock.channel = channel
  dock.open = true
  popups.value = channel ? popups.value.filter((p) => p.channel !== channel) : popups.value
}

/** Plain-text preview with @mentions shown as names and links as 'Project PROJ-0001'. */
export function preview(message, names = {}) {
  const text = tokens(message.content, names)
    .map((p) => (p.link ? `${KIND[p.link.kind].one} ${p.text}` : p.text))
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
  const count = message.photos?.length || 0
  const photos = count ? (count === 1 ? '📷 Photo' : `📷 ${count} photos`) : ''
  return (text ? (photos ? `${photos} · ${text}` : text) : photos).slice(0, 140)
}

function announce(channelRow, message) {
  const title = channelRow?.is_direct ? message.full_name : `${message.full_name} in #${channelRow?.title || 'chat'}`
  const body = preview(message)
  popups.value = [{ id: message.name, channel: channelRow?.name, direct: !!channelRow?.is_direct, where: channelRow?.is_direct ? 'Direct message' : `#${channelRow?.title}`, name: message.full_name, image: message.image, body }, ...popups.value.filter((p) => p.channel !== channelRow?.name)].slice(0, 3)
  if (notify.enabled && document.visibilityState === 'hidden') {
    try {
      const n = new Notification(title, { body, tag: `techy-chat-${channelRow?.name}`, icon: `${import.meta.env.BASE_URL}techy-app.svg` })
      n.onclick = () => {
        window.focus()
        openDock(channelRow?.name)
        n.close()
      }
    } catch (e) {
      /* some mobile browsers only allow notifications from a service worker */
    }
  }
}

let listening = false
/** Keep unread counts current and raise pop-ups from realtime chat events. */
export function listenForChat() {
  if (listening) return
  listening = true
  onRealtime('techy_chat', async ({ channel, message }) => {
    let row = channels.value.find((c) => c.name === channel)
    if (!row) {
      await loadChannels().catch(() => {})
      row = channels.value.find((c) => c.name === channel)
    }
    if (!row || message.system || message.user === me.user) return
    const onScreen = channel === activeChannel.value && document.visibilityState === 'visible'
    if (!message.thread && !onScreen) row.unread += 1
    if (!onScreen) announce(row, message)
  })
}

// Unread count in the browser tab title and on the installed app's icon.
const baseTitle = typeof document !== 'undefined' ? document.title : ''
watch(unread, (n) => {
  document.title = n ? `(${n > 99 ? '99+' : n}) ${baseTitle}` : baseTitle
  try {
    if (n && navigator.setAppBadge) navigator.setAppBadge(n)
    else if (navigator.clearAppBadge) navigator.clearAppBadge()
  } catch (e) {
    /* badging unsupported */
  }
})
