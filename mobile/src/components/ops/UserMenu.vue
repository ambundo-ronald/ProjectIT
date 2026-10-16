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
          <p class="truncate text-xs text-gray-500">{{ statusLine(mine) || userId }}</p>
        </div>
      </div>
      <div class="py-1">
        <button class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" @click="close(); statusDialog.open = true">
          <FeatherIcon name="smile" class="h-4 w-4 text-gray-500" /><span class="flex-1">{{ mine.emoji || mine.text ? 'Change status' : 'Set a status' }}</span>
        </button>
        <button class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitemcheckbox" :aria-checked="!!mine.away" @click="toggleAway">
          <PresenceDot :user="me.user" />
          <span class="flex-1">{{ mine.away ? 'Away · set yourself active' : 'Active · set yourself away' }}</span>
        </button>
        <button v-if="notify.supported" class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" :disabled="notify.permission === 'denied'" @click="toggleNotifications">
          <FeatherIcon :name="notify.enabled ? 'bell' : 'bell-off'" class="h-4 w-4 text-gray-500" />
          <span class="flex-1">
            Notifications
            <span v-if="notify.permission === 'denied'" class="block text-xs text-gray-400">Blocked in browser settings</span>
            <span v-else-if="notify.enabled && push.subscribed" class="block text-xs text-gray-400">Also when the app is closed</span>
          </span>
          <span class="relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors" :class="notify.enabled ? 'bg-brand-600' : 'bg-gray-300'" aria-hidden="true">
            <span class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all" :class="notify.enabled ? 'left-[18px]' : 'left-0.5'" />
          </span>
        </button>
        <button v-if="notify.enabled && push.subscribed" class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-gray-50" role="menuitem" :disabled="testing" @click="sendTest">
          <FeatherIcon :name="tested ? 'check' : 'send'" class="h-4 w-4 text-gray-500" /><span class="flex-1">{{ tested ? 'Test sent: check your notifications' : 'Send a test notification' }}</span>
        </button>
        <router-link v-if="me.can_approve_parts" :to="{ name: 'OpsPartsRequests' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem" @click="close"><FeatherIcon name="package" class="h-4 w-4 text-gray-500" /><span class="flex-1">Parts requests</span><span v-if="me.counts?.pending_parts" class="rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white">{{ me.counts.pending_parts }}</span></router-link>
        <router-link v-if="me.manager" :to="{ name: 'OpsDispatch' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem" @click="close"><FeatherIcon name="columns" class="h-4 w-4 text-gray-500" />Dispatch</router-link>
        <router-link v-if="me.manager" :to="{ name: 'OpsReports' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem" @click="close"><FeatherIcon name="bar-chart-2" class="h-4 w-4 text-gray-500" />Reports</router-link>
        <router-link v-if="me.can_invoice" :to="{ name: 'OpsBilling' }" class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm hover:bg-gray-50" role="menuitem" @click="close"><FeatherIcon name="file-text" class="h-4 w-4 text-gray-500" />Billing</router-link>
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
import { computed, ref } from 'vue'
import { me } from '@/data/ops'
import PresenceDot from './PresenceDot.vue'
import { presence, setStatus, statusDialog, statusLine } from '@/data/presence'
import { notify, setNotifications } from '@/data/chat'
import { push, testPush } from '@/data/push'

defineProps({ align: { type: String, default: 'right' }, placement: { type: String, default: 'bottom' } })
const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
const fullName = cookies.get('full_name') || ''
const userId = cookies.get('user_id') || ''
const toggleNotifications = () => setNotifications(!notify.enabled)
const testing = ref(false)
const tested = ref(false)
async function sendTest() {
  testing.value = true
  try {
    await testPush()
    tested.value = true
    setTimeout(() => (tested.value = false), 4000)
  } catch (e) {
    /* the toggle above shows whether notifications are on */
  } finally {
    testing.value = false
  }
}
const mine = computed(() => presence[me.user] || {})
// Away only; the status text stays as it is.
const toggleAway = () => setStatus({ away: mine.value.away ? 0 : 1 }).catch(() => {})
</script>
