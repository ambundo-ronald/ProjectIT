<template>
  <div v-if="plant.me" class="space-y-4">
    <div class="card flex items-center gap-4 p-5">
      <UserAvatar :name="plant.me.full_name" size="lg" />
      <div class="min-w-0 flex-1">
        <p class="truncate text-[17px] font-semibold text-gray-900">{{ plant.me.full_name }}</p>
        <p class="truncate text-sm text-gray-500">{{ plant.me.user }}</p>
        <p class="mt-1 text-xs text-gray-600">{{ plant.me.admin ? 'Admin' : 'Operator' }} · {{ plant.me.customer_name }}</p>
      </div>
    </div>

    <div class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Your machines</h2><span class="text-xs text-gray-500">{{ plant.me.machines.length }}</span></div>
      <ul v-if="plant.me.machines.length" class="divide-y divide-gray-100">
        <li v-for="m in plant.me.machines" :key="m.name" class="flex items-center gap-3 px-5 py-3 text-sm">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="droplet" class="h-4 w-4" /></span>
          <span class="min-w-0 flex-1"><span class="block truncate font-medium text-gray-900">{{ m.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ [m.site, m.tag].filter(Boolean).join(' · ') || m.name }}</span></span>
          <span v-if="m.status !== 'Active'" class="shrink-0 rounded bg-gray-100 px-1.5 text-[11px] font-semibold text-gray-600">{{ m.status }}</span>
        </li>
      </ul>
      <p v-else class="px-5 py-4 text-sm text-gray-500">None yet.</p>
    </div>

    <!-- A customer admin manages their own operators -->
    <CustomerAccessCard v-if="plant.me.admin" />

    <!-- Notifications -->
    <div class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Notifications</h2></div>
      <div class="divide-y divide-gray-100">
        <div class="flex items-center gap-3 px-5 py-3">
          <FeatherIcon :name="push.subscribed ? 'bell' : 'bell-off'" class="h-4 w-4 shrink-0 text-gray-500" />
          <span class="min-w-0 flex-1 text-sm">
            <span class="block font-medium text-gray-900">On this phone</span>
            <span class="block text-xs text-gray-500">{{ phoneHint }}</span>
          </span>
          <Toggle :on="push.subscribed" label="Notifications on this phone" :disabled="!push.supported || push.permission === 'denied' || busy" @change="togglePhone" />
        </div>
        <div v-for="c in CHOICES.filter((x) => !x.admin || plant.me.admin)" :key="c.key" class="flex items-center gap-3 px-5 py-3">
          <FeatherIcon :name="c.icon" class="h-4 w-4 shrink-0 text-gray-500" />
          <span class="min-w-0 flex-1 text-sm"><span class="block font-medium text-gray-900">{{ c.label }}</span><span class="block text-xs text-gray-500">{{ c.help }}</span></span>
          <Toggle :on="!!plant.me.notify?.[c.key]" :label="c.label" :disabled="busy" @change="(v) => setChoice(c.key, v)" />
        </div>
        <div v-if="push.subscribed" class="px-5 py-3">
          <button class="btn btn-ghost btn-sm" :disabled="busy" @click="sendTest"><FeatherIcon :name="tested ? 'check' : 'send'" class="h-4 w-4" />{{ tested ? 'Sent: check your notifications' : 'Send a test notification' }}</button>
        </div>
      </div>
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
      <h2 class="section-label">Need help?</h2>
      <p class="mt-1 text-sm text-gray-600">Ask for service from the Service tab, or contact {{ plant.me.company || 'us' }}:</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <a v-if="plant.me.support_phone" :href="`tel:${plant.me.support_phone}`" class="btn btn-secondary btn-sm"><FeatherIcon name="phone" class="h-4 w-4" />{{ plant.me.support_phone }}</a>
        <a v-if="plant.me.support_email" :href="`mailto:${plant.me.support_email}`" class="btn btn-secondary btn-sm"><FeatherIcon name="mail" class="h-4 w-4" />{{ plant.me.support_email }}</a>
        <router-link :to="{ name: 'PlantService' }" class="btn btn-secondary btn-sm"><FeatherIcon name="tool" class="h-4 w-4" />Ask for service</router-link>
      </div>
    </div>

    <button class="btn btn-secondary w-full text-red-600" :disabled="session.logout.loading" @click="session.logout.submit()"><FeatherIcon name="log-out" class="h-4 w-4" />Sign out</button>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import CustomerAccessCard from '@/components/ops/CustomerAccessCard.vue'
import { plant } from '@/data/plant'
import { session } from '@/data/session'
import { theme, setTheme } from '@/data/theme'
import { push, enablePush, disablePush, checkPush, testPush } from '@/data/push'
import { request } from '@/data/ops'

const CHOICES = [
  { key: 'visits', label: 'Visits and reports', icon: 'truck', help: 'Visit planned or moved, work started, visit done and the report ready, membranes need cleaning.' },
  { key: 'reminders', label: 'Log reminders', icon: 'edit-3', help: "Once a day when a machine's log is due." },
  { key: 'reports', label: 'Monthly report by email', icon: 'mail', help: "Last month's plant report on the 1st: water produced, logs, visits and what we recommend.", admin: true },
]
const busy = ref(false)
const tested = ref(false)
const phoneHint = computed(() => {
  if (!push.supported) return /iPhone|iPad/.test(navigator.userAgent) ? 'On an iPhone, add this app to the home screen first (Share, then Add to Home Screen).' : 'This browser cannot show notifications.'
  if (push.permission === 'denied') return "Blocked in this phone's settings for this site."
  return push.subscribed ? 'Alerts arrive even when the app is closed.' : 'Turn on to get alerts when the app is closed. Replies to your requests always arrive.'
})
onMounted(() => checkPush())

async function togglePhone(on) {
  busy.value = true
  try {
    if (on) {
      const ok = await enablePush()
      await checkPush()
      if (!ok) toast({ title: push.permission === 'denied' ? 'Notifications are blocked for this site in the phone settings.' : 'Notifications could not be turned on.', icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
    } else {
      await disablePush()
    }
  } finally {
    busy.value = false
  }
}
async function setChoice(key, on) {
  busy.value = true
  try {
    plant.me.notify = await request('projectit.plant.set_notifications', { [key]: on ? 1 : 0 })
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  } finally {
    busy.value = false
  }
}
async function sendTest() {
  busy.value = true
  try {
    await testPush()
    tested.value = true
    setTimeout(() => (tested.value = false), 4000)
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  } finally {
    busy.value = false
  }
}

// An on/off switch with a proper role and name.
const Toggle = (p, { emit }) =>
  h('button', { type: 'button', role: 'switch', 'aria-checked': String(!!p.on), 'aria-label': p.label, disabled: p.disabled,
    class: 'relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ' + (p.on ? 'bg-brand-600' : 'bg-gray-300'),
    onClick: () => emit('change', !p.on) },
  [h('span', { class: 'absolute top-0.5 h-5 w-5 rounded-full bg-panel shadow transition-all ' + (p.on ? 'left-[22px]' : 'left-0.5') })])
Toggle.props = ['on', 'label', 'disabled']
Toggle.emits = ['change']

const THEMES = [
  { key: 'light', label: 'Light', title: 'Light' },
  { key: 'dark', label: 'Dark', title: 'Dark navy' },
  { key: 'system', label: 'Auto', title: "Match the phone's setting" },
]
</script>
