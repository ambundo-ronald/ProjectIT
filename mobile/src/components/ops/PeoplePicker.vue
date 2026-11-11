<template>
  <div class="relative">
    <div v-if="modelValue.length" class="mb-2 flex flex-wrap gap-1.5">
      <span v-for="user in modelValue" :key="user" class="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 py-0.5 pl-0.5 pr-1.5 text-[13px] text-gray-800">
        <UserAvatar :name="names[user] || user" size="sm" />
        {{ names[user] || user }}
        <button type="button" class="rounded-full p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-700" :aria-label="`Remove ${names[user] || user}`" @click="remove(user)">
          <FeatherIcon name="x" class="h-3 w-3" />
        </button>
      </span>
    </div>
    <div class="relative">
      <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <input
        v-model="query"
        type="search"
        class="input pl-9"
        :placeholder="placeholder"
        :aria-label="placeholder"
        autocomplete="off"
        @input="search"
        @focus="search"
        @blur="hide"
      />
    </div>
    <ul v-if="open && results.length" class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-panel py-1 shadow-pop" role="listbox">
      <li v-for="person in results" :key="person.user">
        <button type="button" class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-gray-50" @mousedown.prevent="pick(person)">
          <UserAvatar :name="person.full_name" :image="person.image" size="sm" />
          <span class="min-w-0 flex-1 truncate font-medium">{{ person.full_name }}</span>
          <span class="truncate text-xs text-gray-400">{{ person.user }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import UserAvatar from './UserAvatar.vue'
import { api } from '@/data/ops'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Search people' },
  initial: { type: Array, default: () => [] },
  single: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const query = ref('')
const results = ref([])
const open = ref(false)
const names = reactive(Object.fromEntries(props.initial.map((p) => [p.user, p.full_name])))
let timer = null

function search() {
  open.value = true
  clearTimeout(timer)
  timer = setTimeout(async () => {
    try {
      const rows = await api('projectit.ops.search_users', { txt: query.value })
      results.value = rows.filter((p) => !props.modelValue.includes(p.user))
    } catch (e) {
      results.value = []
    }
  }, 200)
}
const hide = () => setTimeout(() => (open.value = false), 150)

function pick(person) {
  names[person.user] = person.full_name
  emit('update:modelValue', props.single ? [person.user] : [...props.modelValue, person.user])
  query.value = ''
  results.value = []
  open.value = false
}

const remove = (user) => emit('update:modelValue', props.modelValue.filter((u) => u !== user))
</script>
