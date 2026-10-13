<template>
  <Dropdown :align="align" :placement="placement" :close-on-click="false">
    <template #trigger="{ open, toggle }">
      <slot name="trigger" :open="open" :toggle="toggle">
        <button class="rounded-full ring-offset-2 transition hover:ring-2 hover:ring-brand-200" :aria-expanded="open" aria-haspopup="menu" aria-label="Account menu" @click="toggle">
          <UserAvatar :name="fullName" size="md" />
        </button>
      </slot>
    </template>
    <template #default="{ close }">
      <div class="flex items-center gap-3 border-b border-gray-100 px-2.5 pb-3 pt-2">
        <UserAvatar :name="fullName" size="lg" />
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold">{{ fullName }}</p>
          <p class="truncate text-xs text-gray-500">{{ userId }}</p>
        </div>
      </div>
      <div class="py-1">
        <button v-if="notify.supported" class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" :disabled="notify.permission === 'denied'" @click="toggleNotifications">
          <FeatherIcon :name="notify.enabled ? 'bell' : 'bell-off'" class="h-4 w-4 text-gray-500" />
          <span class="flex-1">
            Message notifications
            <span v-if="notify.permission === 'denied'" class="block text-xs text-gray-400">Blocked in browser settings</span>
          </span>
          <span class="relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors" :class="notify.enabled ? 'bg-brand-600' : 'bg-gray-300'" aria-hidden="true">
            <span class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all" :class="notify.enabled ? 'left-[18px]' : 'left-0.5'" />
          </span>
        </button>
        <router-link :to="{ name: 'Home' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem" @click="close"><FeatherIcon name="grid" class="h-4 w-4 text-gray-500" />All apps</router-link>
        <a href="/desk" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem"><FeatherIcon name="external-link" class="h-4 w-4 text-gray-500" />Open ERPNext</a>
      </div>
      <div class="border-t border-gray-100 pt-1">
        <button class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm text-red-600 hover:bg-red-50" role="menuitem" :disabled="session.logout.loading" @click="session.logout.submit()"><FeatherIcon name="log-out" class="h-4 w-4" />Sign out</button>
      </div>
    </template>
  </Dropdown>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
import Dropdown from './Dropdown.vue'
import UserAvatar from './UserAvatar.vue'
import { session } from '@/data/session'
import { notify, setNotifications } from '@/data/chat'

defineProps({ align: { type: String, default: 'right' }, placement: { type: String, default: 'bottom' } })
const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
const fullName = cookies.get('full_name') || ''
const userId = cookies.get('user_id') || ''
const toggleNotifications = () => setNotifications(!notify.enabled)
</script>
