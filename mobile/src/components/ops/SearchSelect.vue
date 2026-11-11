<template>
  <div ref="root" class="relative">
    <!-- Closed: the chosen item, tap to change -->
    <button
      v-if="!editing"
      :id="id"
      type="button"
      class="input flex items-center gap-2 text-left"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-label="ariaLabel"
      @click="openList"
    >
      <FeatherIcon :name="icon" class="h-4 w-4 shrink-0 text-gray-400" />
      <span class="min-w-0 flex-1 truncate" :class="selected ? 'font-medium text-gray-900' : 'text-gray-400'">
        {{ selected ? selected.label : loading ? 'Loading…' : placeholder }}
        <span v-if="selected && selected.sub" class="font-normal text-gray-500"> · {{ selected.sub }}</span>
      </span>
      <span
        v-if="selected && clearable && !disabled"
        role="button"
        tabindex="-1"
        class="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        :aria-label="`Clear ${ariaLabel || 'choice'}`"
        @click.stop="choose('')"
      >
        <FeatherIcon name="x" class="h-4 w-4" />
      </span>
      <FeatherIcon v-else name="chevron-down" class="h-4 w-4 shrink-0 text-gray-400" />
    </button>

    <!-- Open: search box and matches -->
    <template v-else>
      <div class="relative">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          :id="id"
          ref="search"
          v-model="query"
          type="search"
          class="input pl-9"
          :placeholder="searchPlaceholder"
          autocomplete="off"
          role="combobox"
          aria-expanded="true"
          :aria-controls="listId"
          :aria-activedescendant="active >= 0 ? `${listId}-${active}` : undefined"
          :aria-label="ariaLabel"
          @keydown.down.prevent="move(1)"
          @keydown.up.prevent="move(-1)"
          @keydown.enter.prevent="pickActive"
          @keydown.esc.prevent="close"
          @keydown.tab="close"
          @blur="onBlur"
        />
      </div>
      <ul :id="listId" role="listbox" class="mt-1 max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-panel py-1 shadow-pop">
        <li
          v-for="(item, i) in shown"
          :id="`${listId}-${i}`"
          :key="item.value || '__none'"
          role="option"
          :aria-selected="item.value === (modelValue || '')"
        >
          <button
            type="button"
            tabindex="-1"
            class="flex w-full items-center gap-2 px-3 py-2 text-left"
            :class="i === active ? 'bg-brand-50' : 'hover:bg-gray-50'"
            @mousedown.prevent="choose(item.value)"
            @mousemove="active = i"
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm" :class="item.value ? 'font-medium text-gray-900' : 'text-gray-500'">{{ item.label }}</span>
              <span v-if="item.sub" class="block truncate text-xs text-gray-500">{{ item.sub }}</span>
            </span>
            <FeatherIcon v-if="item.value === (modelValue || '')" name="check" class="h-4 w-4 shrink-0 text-brand-600" />
          </button>
        </li>
        <li v-if="!matches.length" class="px-3 py-2 text-sm text-gray-500">{{ query ? `Nothing matches “${query}”.` : emptyText }}</li>
        <li v-else-if="matches.length > LIMIT" class="px-3 py-2 text-xs text-gray-500">{{ matches.length - LIMIT }} more. Keep typing to narrow the list.</li>
      </ul>
    </template>
    <!-- Lets a surrounding form's required check see this field -->
    <input v-if="required" class="pointer-events-none absolute bottom-0 left-4 h-px w-px opacity-0" tabindex="-1" aria-hidden="true" :value="modelValue || ''" required @invalid="openList" />
  </div>
</template>
<script setup>
// A select you can type into: tap to open, type any part of the name, code or customer, pick with mouse, touch or keys.
// options: [{ value, label, sub?, keywords? }]. noneLabel adds a first "nothing chosen" row (e.g. "No project").
import { computed, nextTick, ref, watch } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  id: String,
  ariaLabel: String,
  placeholder: { type: String, default: 'Choose…' },
  searchPlaceholder: { type: String, default: 'Type to search' },
  noneLabel: String,
  emptyText: { type: String, default: 'Nothing to choose from yet.' },
  icon: { type: String, default: 'search' },
  required: Boolean,
  disabled: Boolean,
  loading: Boolean,
})
const emit = defineEmits(['update:modelValue', 'change'])

const LIMIT = 50
const listId = `ss-${Math.random().toString(36).slice(2, 9)}`
const editing = ref(false)
const query = ref('')
const active = ref(-1)
const search = ref(null)

const clearable = computed(() => !props.required && !!props.noneLabel)
const selected = computed(() => props.options.find((o) => o.value === props.modelValue) || null)
const haystack = (o) => `${o.label} ${o.sub || ''} ${o.value} ${o.keywords || ''}`.toLowerCase()
const matches = computed(() => {
  const words = query.value.toLowerCase().split(/\s+/).filter(Boolean)
  const found = words.length ? props.options.filter((o) => words.every((w) => haystack(o).includes(w))) : props.options
  return !words.length && props.noneLabel ? [{ value: '', label: props.noneLabel }, ...found] : found
})
const shown = computed(() => matches.value.slice(0, LIMIT))

async function openList() {
  if (props.disabled) return
  editing.value = true
  query.value = ''
  active.value = Math.max(0, shown.value.findIndex((o) => o.value === (props.modelValue || '')))
  await nextTick()
  search.value?.focus()
}
function close() {
  editing.value = false
  query.value = ''
}
function onBlur() {
  setTimeout(close, 120)
}
function move(step) {
  if (!shown.value.length) return
  active.value = (active.value + step + shown.value.length) % shown.value.length
}
function pickActive() {
  const item = shown.value[active.value] || (shown.value.length === 1 ? shown.value[0] : null)
  if (item) choose(item.value)
}
function choose(value) {
  if (value !== (props.modelValue || '')) {
    emit('update:modelValue', value)
    emit('change', value)
  }
  close()
}
// Typing narrows the list; keep the highlight on the first match.
watch(query, () => (active.value = shown.value.length ? 0 : -1))
</script>
