<template>
  <section class="mx-auto max-w-3xl space-y-6 p-4 md:p-8">
    <PageHeader title="Chat" subtitle="Channels for your teams and sites, plus direct messages.">
      <button class="btn btn-secondary" @click="dm = true"><FeatherIcon name="edit" class="h-4 w-4" /><span class="hidden sm:inline">New message</span></button>
      <button class="btn btn-primary" @click="creating = true"><FeatherIcon name="plus" class="h-4 w-4" /><span class="hidden sm:inline">New channel</span><span class="sm:hidden">Channel</span></button>
    </PageHeader>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-for="group in groups" :key="group.label">
      <h2 class="section-label mb-2 px-1">{{ group.label }}</h2>
      <ul class="card divide-y divide-gray-100 overflow-hidden">
        <li v-for="c in group.rows" :key="c.name">
          <router-link :to="{ name: 'OpsChannel', params: { channel: c.name } }" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
            <UserAvatar v-if="c.is_direct" :name="c.title" size="lg" />
            <span v-else class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="c.is_member ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-500'"><FeatherIcon :name="c.is_private ? 'lock' : 'hash'" class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate" :class="c.unread ? 'font-bold text-gray-900' : 'font-medium text-gray-800'">{{ c.title }}</span>
              <span class="block truncate text-xs text-gray-500">{{ c.description || (c.is_direct ? 'Direct message' : c.is_private ? 'Private channel' : 'Public channel') }}</span>
            </span>
            <span v-if="c.unread" class="rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white">{{ c.unread }}</span>
            <span v-else-if="!c.is_member" class="btn btn-secondary btn-sm pointer-events-none">Join</span>
            <FeatherIcon v-else name="chevron-right" class="h-4 w-4 text-gray-300" />
          </router-link>
        </li>
      </ul>
    </div>
    <EmptyState v-if="!channels.length && !error" icon="message-circle" title="Start the conversation" text="Create #general for the whole team, or a channel per site or shift.">
      <button class="btn btn-primary btn-sm" @click="creating = true"><FeatherIcon name="plus" class="h-4 w-4" />New channel</button>
    </EmptyState>

    <Modal v-model="creating" title="New channel" subtitle="Channels are where your team talks about a site, shift or topic.">
      <form id="channel-form" class="space-y-4" @submit.prevent="create">
        <div>
          <label class="label" for="ch-name">Name <span class="text-red-500">*</span></label>
          <div class="relative">
            <FeatherIcon name="hash" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input id="ch-name" v-model="form.channel_name" required maxlength="60" class="input pl-9" placeholder="plant-maintenance" />
          </div>
          <p class="hint">Lowercase letters, numbers and dashes.</p>
        </div>
        <div>
          <label class="label" for="ch-purpose">Purpose</label>
          <input id="ch-purpose" v-model="form.description" maxlength="250" class="input" placeholder="What is this channel about?" />
        </div>
        <label class="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
          <input v-model="form.is_private" type="checkbox" class="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600" />
          <span><span class="block text-sm font-medium">Make private</span><span class="block text-xs text-gray-500">Only invited people can find and read it.</span></span>
        </label>
        <div v-if="me.manager">
          <label class="label" for="ch-project">Linked project <span class="font-normal text-gray-400">(optional)</span></label>
          <select id="ch-project" v-model="form.project" class="input">
            <option value="">None</option>
            <option v-for="p in projects" :key="p.name" :value="p.name">{{ p.project_name }}</option>
          </select>
          <p class="hint">Work orders for this project post their updates here.</p>
        </div>
        <div>
          <span class="label">Add people</span>
          <PeoplePicker v-model="form.members" />
        </div>
        <p v-if="formError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ formError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-secondary" @click="creating = false">Cancel</button>
        <button form="channel-form" :disabled="busy" class="btn btn-primary">Create channel</button>
      </template>
    </Modal>

    <Modal v-model="dm" title="New message" subtitle="Start a direct conversation with a teammate.">
      <PeoplePicker :model-value="[]" single placeholder="Find a teammate" @update:model-value="(u) => openDirect(u[0])" />
      <p v-if="formError" role="alert" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ formError }}</p>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import PeoplePicker from '@/components/ops/PeoplePicker.vue'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import { api, me } from '@/data/ops'
import { channels, loadChannels } from '@/data/chat'

const router = useRouter()
const error = ref('')
const formError = ref('')
const busy = ref(false)
const creating = ref(false)
const dm = ref(false)
const projects = ref([])
const form = reactive({ channel_name: '', description: '', is_private: false, project: '', members: [] })

const groups = computed(() =>
  [
    { label: 'Your channels', rows: channels.value.filter((c) => c.is_member && !c.is_direct) },
    { label: 'Direct messages', rows: channels.value.filter((c) => c.is_direct) },
    { label: 'Browse channels', rows: channels.value.filter((c) => !c.is_member) },
  ].filter((g) => g.rows.length),
)

watch(creating, async (open) => {
  if (!open) return
  Object.assign(form, { channel_name: '', description: '', is_private: false, project: '', members: [] })
  formError.value = ''
  if (me.manager && !projects.value.length) {
    try {
      projects.value = (await api('projectit.work_orders.options')).projects
    } catch (e) {
      projects.value = []
    }
  }
})

async function create() {
  busy.value = true
  formError.value = ''
  try {
    const { name } = await api('projectit.chat.create_channel', { ...form, is_private: form.is_private ? 1 : 0, project: form.project || null })
    creating.value = false
    await loadChannels()
    router.push({ name: 'OpsChannel', params: { channel: name } })
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function openDirect(user) {
  if (!user) return
  formError.value = ''
  try {
    const { name } = await api('projectit.chat.open_direct', { user })
    dm.value = false
    await loadChannels()
    router.push({ name: 'OpsChannel', params: { channel: name } })
  } catch (e) {
    formError.value = e.message
  }
}

onMounted(() => loadChannels().catch((e) => (error.value = e.message)))
</script>
