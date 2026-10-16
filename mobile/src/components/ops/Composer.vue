<template>
  <form class="relative" @submit.prevent="send">
    <!-- slash commands, at the start of a message -->
    <ul v-if="trigger?.type === 'command'" class="absolute bottom-full left-0 z-10 mb-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-pop" role="listbox" aria-label="Commands">
      <li v-for="(c, i) in commands" :key="c.name" role="option" :aria-selected="i === active">
        <button type="button" class="flex w-full items-baseline gap-3 px-3 py-2 text-left" :class="i === active ? 'bg-brand-50' : 'hover:bg-gray-50'" @mousedown.prevent="pick(c)">
          <span class="shrink-0 font-mono text-sm font-semibold text-gray-900">/{{ c.name }}</span>
          <span class="min-w-0 truncate text-xs text-gray-500">{{ c.hint }}</span>
        </button>
      </li>
      <li class="border-t border-gray-100 px-3 py-1.5 text-[11px] text-gray-400">Commands aren't posted. Keep typing to link a job instead.</li>
    </ul>

    <!-- @mention suggestions -->
    <ul v-if="trigger?.type === 'mention' && people.length" class="absolute bottom-full left-0 z-10 mb-2 max-h-56 w-72 overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-pop" role="listbox" aria-label="People">
      <li v-for="(person, i) in people" :key="person.user" role="option" :aria-selected="i === active">
        <button type="button" class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm" :class="i === active ? 'bg-brand-50' : 'hover:bg-gray-50'" @mousedown.prevent="pick(person)">
          <UserAvatar :name="person.full_name" :image="person.image" size="sm" />
          <span class="truncate">{{ person.full_name }}</span>
        </button>
      </li>
    </ul>

    <!-- document link picker: / tasks, $ projects, or a typed keyword -->
    <div v-if="trigger?.type === 'link'" class="absolute bottom-full left-0 z-10 mb-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-gray-200 bg-white shadow-pop">
      <div class="flex gap-1 overflow-x-auto border-b border-gray-100 p-1.5" role="tablist" aria-label="Link to">
        <button v-for="k in LINK_KINDS" :key="k.kind" type="button" role="tab" :aria-selected="trigger.kind === k.kind" class="flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors" :class="trigger.kind === k.kind ? 'bg-brand-600 text-white' : 'text-gray-600 hover:bg-gray-100'" @mousedown.prevent="switchKind(k.kind)">
          <FeatherIcon :name="k.icon" class="h-3.5 w-3.5" />{{ k.label }}
        </button>
      </div>
      <ul class="max-h-60 overflow-y-auto py-1" role="listbox" :aria-label="KIND[trigger.kind].label">
        <li v-if="loading && !results.length" class="space-y-2 px-3 py-2" aria-label="Loading">
          <div v-for="i in 3" :key="i" class="h-8 animate-pulse rounded bg-gray-100" />
        </li>
        <li v-else-if="searchError" class="px-3 py-3 text-sm text-red-600">{{ searchError }}</li>
        <li v-else-if="!results.length" class="px-3 py-3 text-sm text-gray-500">No {{ KIND[trigger.kind].label.toLowerCase() }}{{ trigger.query ? ` match “${trigger.query}”` : ' you can open' }}</li>
        <li v-for="(row, i) in results" :key="row.name" role="option" :aria-selected="i === active">
          <button type="button" class="flex w-full items-center gap-3 px-3 py-2 text-left" :class="i === active ? 'bg-brand-50' : 'hover:bg-gray-50'" @mousedown.prevent="pick(row)">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600"><FeatherIcon :name="KIND[row.kind].icon" class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-medium text-gray-900">{{ row.title }}</span>
              <span class="block truncate font-mono text-[11px] text-gray-500">{{ row.name }}</span>
            </span>
            <span v-if="row.detail" class="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600">{{ row.detail }}</span>
          </button>
        </li>
      </ul>
      <p class="border-t border-gray-100 px-3 py-1.5 text-[11px] text-gray-400">
        <template v-if="trigger.keyword">Tap one to link it · <kbd class="font-sans font-semibold">Tab</kbd> picks the first · <kbd class="font-sans font-semibold">Esc</kbd> to keep typing</template>
        <template v-else>Type to search · <kbd class="font-sans font-semibold">Enter</kbd> to link · <kbd class="font-sans font-semibold">Esc</kbd> to close</template>
      </p>
    </div>

    <div class="rounded-xl border border-gray-300 bg-white shadow-sm transition focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
    <!-- photos waiting to be sent -->
    <ul v-if="pending.length" class="flex gap-2 overflow-x-auto px-3 pt-3" aria-label="Photos to send">
      <li v-for="(p, i) in pending" :key="p.preview" class="relative shrink-0">
        <img :src="p.preview" :alt="`Photo ${i + 1}`" class="h-16 w-16 rounded-lg border border-gray-200 object-cover" />
        <button type="button" class="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-gray-800 text-white shadow" :aria-label="`Remove photo ${i + 1}`" @click="unpick(i)"><FeatherIcon name="x" class="h-3 w-3" /></button>
      </li>
    </ul>
    <div class="flex items-end gap-2 p-1.5 pl-3">
      <textarea
        ref="input"
        v-model="text"
        rows="1"
        maxlength="4000"
        class="max-h-40 min-h-[2.25rem] flex-1 resize-none border-0 bg-transparent px-0 py-2 text-[14px] placeholder:text-gray-400 focus:ring-0"
        :placeholder="placeholder"
        :aria-label="placeholder"
        :disabled="disabled"
        @input="onInput"
        @click="detect"
        @keydown="onKey"
        @blur="trigger = null"
      />
      <slot name="actions" />
      <PhotoButtons v-if="photos" variant="icons" multiple :max="MAX_PHOTOS - pending.length" :disabled="disabled || pending.length >= MAX_PHOTOS" @photos="addPhotos" @error="(e) => (photoError = e)" />
      <button type="button" :disabled="disabled" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-gray-800" aria-label="Link a task, work order, project, asset or request" title="Link a record ( / or $ )" @mousedown.prevent="startLink">
        <FeatherIcon name="link-2" class="h-4 w-4" />
      </button>
      <button :disabled="disabled || busy || (!text.trim() && !pending.length)" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white transition hover:bg-brand-700 disabled:bg-gray-200 disabled:text-gray-400" aria-label="Send">
        <FeatherIcon :name="busy ? 'loader' : 'send'" class="h-4 w-4" :class="busy ? 'animate-spin' : ''" />
      </button>
    </div>
    </div>
    <p v-if="photoError" role="alert" class="mt-1.5 text-xs text-red-600">{{ photoError }}</p>
    <p class="mt-1.5 hidden text-[11px] text-gray-400 sm:block">
      <kbd class="font-sans font-semibold">Enter</kbd> to send · <kbd class="font-sans font-semibold">Shift + Enter</kbd> new line · <kbd class="font-sans font-semibold">@</kbd> mention · <kbd class="font-sans font-semibold">/</kbd> task · <kbd class="font-sans font-semibold">$</kbd> project
    </p>
  </form>
</template>
<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from './UserAvatar.vue'
import PhotoButtons from './PhotoButtons.vue'
import { LINK_KINDS, KIND, KEYWORDS, linkToken, searchLinks } from '@/data/links'

const props = defineProps({
  people: { type: Array, default: () => [] }, // [{ user, full_name, image }]
  placeholder: { type: String, default: 'Write a message' },
  disabled: Boolean,
  submit: Function, // async (text, photos) => void; photos are base64 JPEGs when `photos` is on
  photos: Boolean, // offer Camera and Photos buttons
})
const emit = defineEmits(['typing'])
const MAX_PHOTOS = 6
const pending = ref([]) // [{ content, preview }]
const photoError = ref('')
const text = ref('')
const busy = ref(false)
const input = ref(null)
// { type: 'mention' | 'link', start, query, kind?, keyword? } — start is where the typed trigger begins.
const trigger = ref(null)
const active = ref(0)
const dismissed = ref(null) // start of a trigger closed with Esc, so it stays closed while typing on
const results = ref([])
const loading = ref(false)
const searchError = ref('')

const people = computed(() => {
  if (trigger.value?.type !== 'mention') return []
  const q = trigger.value.query.toLowerCase()
  return props.people.filter((p) => p.full_name?.toLowerCase().includes(q) || p.user.toLowerCase().includes(q)).slice(0, 8)
})
// Slash commands (run on the server; see projectit/commands.py).
const COMMANDS = [
  { name: 'job', hint: "Create a repair job: /job Pump leaking @tina !urgent", args: true },
  { name: 'jobs', hint: 'List my open jobs' },
  { name: 'remind', hint: 'Remind me: /remind 1h Call the clinic', args: true },
  { name: 'status', hint: 'Set my status: /status 🚗 On the road', args: true },
  { name: 'away', hint: 'Show me as away' },
  { name: 'back', hint: "Show me as back" },
  { name: 'help', hint: 'All commands' },
]
const commands = computed(() => (trigger.value?.type === 'command' ? COMMANDS.filter((c) => c.name.startsWith(trigger.value.query.toLowerCase())) : []))
const options = computed(() => (trigger.value?.type === 'mention' ? people.value : trigger.value?.type === 'link' ? results.value : commands.value))

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const KEYWORD = new RegExp(`(?:^|\\s)(${KEYWORDS.map(([w]) => escape(w).replace(/ /g, '\\s')).join('|')})[\\s:#]+([^\\s]*)$`, 'i')

/** The trigger typed just before the caret: @name, /task, $project, or a keyword and a space ("project pump"). */
let linkOnly = false // the "/" at the start came from the link button, so it links rather than offers commands
function find(before) {
  let m = before.match(/^\/([a-z]*)$/i)
  if (m && !linkOnly && COMMANDS.some((c) => c.name.startsWith(m[1].toLowerCase()))) return { type: 'command', query: m[1], start: 0 }
  m = before.match(/(?:^|\s)@([\w.+-]*)$/)
  if (m) return { type: 'mention', query: m[1], start: before.length - m[1].length - 1 }
  m = before.match(/(?:^|\s)([/$])([^\s/$]*)$/)
  if (m) return { type: 'link', kind: m[1] === '$' ? 'project' : 'task', query: m[2], start: before.length - m[0].trimStart().length }
  m = before.match(KEYWORD)
  if (m) {
    const word = m[1].toLowerCase().replace(/\s+/g, ' ')
    const kind = (KEYWORDS.find(([w]) => w === word) || [])[1]
    if (kind) return { type: 'link', kind, keyword: true, query: m[2], start: before.length - m[0].trimStart().length }
  }
  return null
}

function detect() {
  const el = input.value
  if (!el) return
  const found = find(text.value.slice(0, el.selectionStart))
  if (!found || found.start === dismissed.value) {
    trigger.value = null
    return
  }
  dismissed.value = null
  const same = trigger.value && trigger.value.start === found.start && trigger.value.type === found.type
  // Keep a kind chosen from the tabs while the user keeps typing the same trigger.
  if (same && found.type === 'link' && trigger.value.picked) Object.assign(found, { kind: trigger.value.kind, picked: true })
  if (!same || trigger.value.kind !== found.kind) active.value = found.keyword ? -1 : 0
  trigger.value = found
}

function onInput() {
  if (text.value.trim()) emit('typing')
  else {
    dismissed.value = null // a cleared box starts afresh
    linkOnly = false
  }
  const el = input.value
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
  detect()
}

let timer = null
let seq = 0
watch(() => trigger.value?.type === 'link' && `${trigger.value.kind}|${trigger.value.query}`, (key) => {
  clearTimeout(timer)
  if (!key) return
  const { kind, query } = trigger.value
  loading.value = true
  searchError.value = ''
  const mine = ++seq
  timer = setTimeout(async () => {
    try {
      const rows = await searchLinks(kind, query)
      if (mine === seq) results.value = rows
    } catch (e) {
      if (mine === seq) {
        results.value = []
        searchError.value = e.message
      }
    } finally {
      if (mine === seq) loading.value = false
    }
  }, query ? 150 : 0)
})
watch(results, () => (active.value = trigger.value?.keyword ? -1 : 0))

function switchKind(kind) {
  if (!trigger.value) return
  trigger.value = { ...trigger.value, kind, picked: true }
  results.value = []
}

/** Replace the typed trigger with the chosen person or record. */
function pick(item) {
  const el = input.value
  const { type, start } = trigger.value
  const insert = type === 'mention' ? `@${item.user} ` : type === 'command' ? `/${item.name}${item.args ? ' ' : ''}` : `${linkToken(item.kind, item.name)} `
  const caret = el.selectionStart
  const before = text.value.slice(0, start) + insert
  const after = text.value.slice(caret)
  text.value = before + (after.startsWith(' ') ? after.slice(1) : after)
  trigger.value = null
  nextTick(() => {
    el.focus()
    el.setSelectionRange(before.length, before.length)
    onInput()
  })
}

/** Link button: type a "/" at the caret so the picker opens (and can switch kinds). */
function startLink() {
  const el = input.value
  const caret = el.selectionStart ?? text.value.length
  const pre = text.value.slice(0, caret)
  const slash = pre && !/\s$/.test(pre) ? ' /' : '/'
  text.value = pre + slash + text.value.slice(caret)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(caret + slash.length, caret + slash.length)
    onInput()
    // The link button always links, even where a typed "/" would offer the slash commands.
    if (trigger.value?.type === 'command') {
      linkOnly = true
      detect()
    }
  })
}

function onKey(event) {
  if (trigger.value) {
    const count = options.value.length
    if (event.key === 'Escape') {
      event.preventDefault()
      dismissed.value = trigger.value.start
      trigger.value = null
      return
    }
    if (count && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      active.value = active.value < 0 ? (step > 0 ? 0 : count - 1) : (active.value + step + count) % count
      return
    }
    // A typed keyword ("task", "project") only links on Tab or after arrowing, so Enter still sends the sentence.
    if (count && (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey && active.value >= 0))) {
      event.preventDefault()
      pick(options.value[Math.max(active.value, 0)])
      return
    }
    if (trigger.value.type === 'link' && !trigger.value.keyword && loading.value && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault() // results are on their way: don't send a half-typed "/pump"
      return
    }
  }
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

function addPhotos(list) {
  photoError.value = ''
  pending.value = [...pending.value, ...list].slice(0, MAX_PHOTOS)
  nextTick(() => input.value?.focus())
}
function unpick(i) {
  URL.revokeObjectURL(pending.value[i].preview)
  pending.value = pending.value.filter((_, j) => j !== i)
}

async function send() {
  const value = text.value.trim()
  if ((!value && !pending.value.length) || busy.value) return
  busy.value = true
  photoError.value = ''
  try {
    if (props.photos) await props.submit(value, pending.value.map((p) => p.content))
    else await props.submit(value)
    text.value = ''
    pending.value.forEach((p) => URL.revokeObjectURL(p.preview))
    pending.value = []
    trigger.value = null
    dismissed.value = null
    linkOnly = false
    nextTick(() => {
      if (input.value) input.value.style.height = 'auto'
    })
  } catch (e) {
    // The caller shows the error; keep the draft so it can be retried.
  } finally {
    busy.value = false
  }
}

defineExpose({ focus: () => input.value?.focus() })
</script>
