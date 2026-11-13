<template>
  <div v-if="contractor.me" class="space-y-4">
    <div class="card flex items-center gap-4 p-5">
      <UserAvatar :name="contractor.me.full_name" size="lg" />
      <div class="min-w-0 flex-1">
        <p class="truncate text-[17px] font-semibold text-gray-900">{{ contractor.me.full_name }}</p>
        <p class="truncate text-sm text-gray-500">{{ contractor.me.user }}</p>
        <p class="mt-1 text-xs text-gray-600">{{ contractor.me.member_role }} · {{ contractor.me.contractor_name }}</p>
      </div>
    </div>

    <!-- Owners and leads: the team; owners add and switch off people -->
    <div v-if="contractor.me.runs_jobs" class="card overflow-hidden">
      <div class="card-header">
        <h2 class="card-title">Your team</h2>
        <button v-if="team?.can_manage" class="btn btn-secondary btn-sm -mr-2" @click="openInvite"><FeatherIcon name="user-plus" class="h-4 w-4" />Add</button>
      </div>
      <p v-if="teamError" class="px-5 py-3 text-sm text-red-700">{{ teamError }}</p>
      <ul v-else-if="team" class="divide-y divide-gray-100">
        <li v-for="m in team.members" :key="m.user" class="flex items-center gap-3 px-5 py-3">
          <UserAvatar :name="m.full_name" size="md" />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-medium" :class="m.enabled ? 'text-gray-900' : 'text-gray-400 line-through'">{{ m.full_name }}<span v-if="m.me" class="ml-1 font-normal text-gray-400">(you)</span></span>
            <span class="block truncate text-xs text-gray-500">{{ m.member_role }} · {{ m.enabled ? (m.joined ? 'Signed in before' : 'Invited, not signed in yet') : 'Switched off' }}</span>
          </span>
          <Dropdown v-if="team.can_manage && !m.me && m.member_role !== 'Owner'">
            <template #trigger="{ open, toggle }">
              <button class="btn btn-ghost btn-icon" :aria-expanded="open" aria-haspopup="menu" :aria-label="`Change ${m.full_name}`" @click="toggle"><FeatherIcon name="more-vertical" class="h-4 w-4" /></button>
            </template>
            <template #default="{ close }">
              <button v-if="m.enabled" class="menu-item" role="menuitem" @click="close(); update(m, { member_role: m.member_role === 'Lead' ? 'Crew' : 'Lead' })"><FeatherIcon name="award" class="h-4 w-4" />{{ m.member_role === 'Lead' ? 'Make crew' : 'Make lead' }}</button>
              <button v-if="m.enabled && !m.joined" class="menu-item" role="menuitem" @click="close(); resend(m)"><FeatherIcon name="send" class="h-4 w-4" />Send the invite again</button>
              <button class="menu-item" :class="m.enabled ? 'text-red-600' : ''" role="menuitem" @click="close(); update(m, { enabled: m.enabled ? 0 : 1 })"><FeatherIcon :name="m.enabled ? 'user-x' : 'user-check'" class="h-4 w-4" />{{ m.enabled ? 'Switch off' : 'Switch on' }}</button>
            </template>
          </Dropdown>
        </li>
      </ul>
      <div v-else class="h-20 animate-pulse bg-gray-100" />
      <p class="border-t border-gray-100 px-5 py-2.5 text-xs text-gray-500">Leads accept jobs and choose who does them. Only the owner sees pay.</p>
    </div>

    <div class="card p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="flex items-center gap-3 text-sm font-medium text-gray-900"><FeatherIcon :name="theme.dark ? 'moon' : 'sun'" class="h-4 w-4 text-gray-500" />Appearance</span>
        <span class="segmented" role="group" aria-label="Appearance">
          <button v-for="o in THEMES" :key="o.key" type="button" :aria-pressed="theme.choice === o.key" :title="o.title" @click="setTheme(o.key)">{{ o.label }}</button>
        </span>
      </div>
    </div>

    <div class="card p-5">
      <div class="flex items-center gap-3">
        <FeatherIcon :name="push.subscribed ? 'bell' : 'bell-off'" class="h-4 w-4 shrink-0 text-gray-500" />
        <span class="min-w-0 flex-1 text-sm"><span class="block font-medium text-gray-900">Notifications on this phone</span><span class="block text-xs text-gray-500">New jobs, approvals and messages about your work.</span></span>
        <button type="button" role="switch" :aria-checked="String(push.subscribed)" aria-label="Notifications on this phone" :disabled="!push.supported || push.permission === 'denied' || busy" class="relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50" :class="push.subscribed ? 'bg-brand-600' : 'bg-gray-300'" @click="togglePush">
          <span class="absolute top-0.5 h-5 w-5 rounded-full bg-panel shadow transition-all" :class="push.subscribed ? 'left-[22px]' : 'left-0.5'" />
        </button>
      </div>
    </div>

    <div v-if="contractor.me.support_phone" class="card p-5">
      <h2 class="section-label">Need help?</h2>
      <a :href="`tel:${contractor.me.support_phone}`" class="btn btn-secondary btn-sm mt-3"><FeatherIcon name="phone" class="h-4 w-4" />{{ contractor.me.support_phone }}</a>
    </div>

    <button class="btn btn-secondary w-full text-red-600" :disabled="session.logout.loading" @click="session.logout.submit()"><FeatherIcon name="log-out" class="h-4 w-4" />Sign out</button>

    <Modal v-model="inviting" title="Add someone" subtitle="They get an email with a link to set their password, then sign in to this app.">
      <form id="crew-invite" class="space-y-3" @submit.prevent="invite">
        <div><label class="label" for="ci-name">Name</label><input id="ci-name" v-model="form.full_name" class="input" required maxlength="140" autocomplete="name" /></div>
        <div><label class="label" for="ci-email">Email</label><input id="ci-email" v-model="form.email" type="email" class="input" required autocomplete="email" /></div>
        <div><label class="label" for="ci-phone">Phone <span class="font-normal text-gray-400">(optional)</span></label><input id="ci-phone" v-model="form.phone" type="tel" class="input" autocomplete="tel" /></div>
        <div>
          <span class="label">Role</span>
          <div class="segmented w-full" role="group" aria-label="Role">
            <button v-for="r in ['Crew', 'Lead']" :key="r" type="button" class="flex-1" :aria-pressed="form.member_role === r" @click="form.member_role = r">{{ r }}</button>
          </div>
        </div>
        <p v-if="inviteError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ inviteError }}</p>
        <div v-if="link" class="rounded-lg bg-green-50 p-3 text-sm text-green-900">
          <p>{{ emailed ? 'Invite sent.' : 'The email could not be sent.' }} You can also share this link:</p>
          <input :value="link" readonly class="input mt-2 font-mono text-xs" aria-label="Invite link" @focus="$event.target.select()" />
        </div>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="inviting = false">{{ link ? 'Done' : 'Cancel' }}</button>
        <button v-if="!link" type="submit" form="crew-invite" class="btn btn-primary" :disabled="busy">Send invite</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import Modal from '@/components/ops/Modal.vue'
import Dropdown from '@/components/ops/Dropdown.vue'
import { contractor } from '@/data/contractor'
import { session } from '@/data/session'
import { theme, setTheme } from '@/data/theme'
import { push, enablePush, disablePush, checkPush } from '@/data/push'
import { api } from '@/data/ops'

const THEMES = [
  { key: 'light', label: 'Light', title: 'Light' },
  { key: 'dark', label: 'Dark', title: 'Dark navy' },
  { key: 'system', label: 'Auto', title: "Match the phone's setting" },
]
const team = ref(null)
const teamError = ref('')
const busy = ref(false)
const inviting = ref(false)
const inviteError = ref('')
const link = ref('')
const emailed = ref(false)
const form = reactive({ full_name: '', email: '', phone: '', member_role: 'Crew' })

async function loadTeam() {
  if (!contractor.me?.runs_jobs) return
  try {
    team.value = await api('projectit.contractors.crew')
  } catch (e) {
    teamError.value = e.message
  }
}
function openInvite() {
  Object.assign(form, { full_name: '', email: '', phone: '', member_role: 'Crew' })
  inviteError.value = ''
  link.value = ''
  inviting.value = true
}
async function invite() {
  busy.value = true
  inviteError.value = ''
  try {
    const r = await api('projectit.contractors.invite_member', { ...form })
    link.value = r.link
    emailed.value = r.emailed
    loadTeam()
  } catch (e) {
    inviteError.value = e.message
  } finally {
    busy.value = false
  }
}
async function update(m, changes) {
  try {
    await api('projectit.contractors.update_member', { user: m.user, ...changes })
    loadTeam()
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}
async function resend(m) {
  try {
    const r = await api('projectit.contractors.resend_invite', { user: m.user })
    toast({ title: r.emailed ? 'Invite sent again' : 'The email could not be sent', icon: 'send', position: 'top-center' })
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}
async function togglePush() {
  busy.value = true
  try {
    if (push.subscribed) await disablePush()
    else await enablePush()
    await checkPush()
  } finally {
    busy.value = false
  }
}
onMounted(() => {
  loadTeam()
  checkPush()
})
</script>
