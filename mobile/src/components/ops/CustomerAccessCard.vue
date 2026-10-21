<template>
  <div v-if="data" class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <div class="min-w-0">
        <h2 class="card-title">{{ equipment ? 'Customer app access' : 'People' }}</h2>
        <p class="text-xs text-gray-500">{{ equipment ? `${data.customer_name} people who can see this machine in the plant app` : 'Who can sign in to the plant app' }}</p>
      </div>
      <span class="flex flex-wrap gap-2">
        <router-link v-if="equipment && data.staff" :to="{ path: '/plant', query: { preview: equipment } }" class="btn btn-ghost btn-sm"><FeatherIcon name="eye" class="h-4 w-4" />See it as the customer</router-link>
        <a v-if="data.staff" :href="`/api/method/projectit.monthly_report.download?customer=${encodeURIComponent(data.customer)}`" target="_blank" rel="noopener" class="btn btn-ghost btn-sm"><FeatherIcon name="file-text" class="h-4 w-4" />Last month's report</a>
        <button v-if="data.staff && data.accounts.some((a) => a.access === 'Customer admin' && a.enabled)" class="btn btn-ghost btn-sm" :disabled="busy === 'report'" @click="emailReport"><FeatherIcon name="mail" class="h-4 w-4" />Email it</button>
        <button class="btn btn-secondary btn-sm" @click="openInvite"><FeatherIcon name="user-plus" class="h-4 w-4" />Invite someone</button>
      </span>
    </div>

    <ul v-if="data.accounts.length" class="divide-y divide-gray-100">
      <li v-for="a in data.accounts" :key="a.user" class="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold" :class="a.enabled ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-400'" aria-hidden="true">{{ initials(a.full_name) }}</span>
        <span class="min-w-0 flex-1">
          <span class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span class="font-medium" :class="a.enabled ? 'text-gray-900' : 'text-gray-500 line-through'">{{ a.full_name }}</span>
            <span class="rounded px-1.5 text-[11px] font-semibold" :class="a.access === 'Customer admin' ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-600'">{{ a.access === 'Customer admin' ? 'Admin' : 'Operator' }}</span>
            <span v-if="a.me" class="text-[11px] text-gray-500">(you)</span>
          </span>
          <span class="block truncate text-xs text-gray-500">{{ a.user }}</span>
          <span class="block text-xs" :class="!a.enabled ? 'text-gray-500' : a.joined ? 'text-gray-500' : 'text-amber-700'">
            {{ !a.enabled ? 'Switched off' : a.joined ? `Last signed in ${fromNow(a.last_login)}` : 'Invited, has not signed in yet' }}
            <template v-if="a.access === 'Operator' && !equipment"> · {{ a.machine_names.length ? a.machine_names.join(', ') : 'no machines yet' }}</template>
          </span>
        </span>
        <span v-if="canChange(a)" class="flex shrink-0 flex-wrap gap-1.5">
          <button v-if="a.access === 'Operator'" class="btn btn-ghost btn-sm" @click="openMachines(a)"><FeatherIcon name="cpu" class="h-4 w-4" />Machines</button>
          <button v-if="a.enabled" class="btn btn-ghost btn-sm" :disabled="busy === a.user" @click="resend(a)"><FeatherIcon name="send" class="h-4 w-4" />New link</button>
          <button class="btn btn-ghost btn-sm" :class="a.enabled ? 'text-red-600' : ''" :disabled="busy === a.user" @click="toggle(a)">
            <FeatherIcon :name="a.enabled ? 'user-x' : 'user-check'" class="h-4 w-4" />{{ a.enabled ? 'Switch off' : 'Switch on' }}
          </button>
        </span>
      </li>
    </ul>
    <p v-else class="px-5 py-4 text-sm text-gray-500">Nobody yet. Invite the customer's admin and operators: they log the plant's readings and follow how it runs.</p>
    <p v-if="error" role="alert" class="px-5 pb-3 text-sm text-red-600">{{ error }}</p>

    <!-- Invite -->
    <Modal v-model="inviting" title="Invite to the plant app" :subtitle="data.customer_name">
      <form v-if="!sent" id="invite-form" class="space-y-4" @submit.prevent="invite">
        <div>
          <label class="label" for="inv-name">Name</label>
          <input id="inv-name" v-model="form.full_name" class="input" maxlength="140" autocomplete="off" required />
        </div>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="inv-email">Email</label>
            <input id="inv-email" v-model="form.email" type="email" class="input" maxlength="140" autocomplete="off" required />
          </div>
          <div>
            <label class="label" for="inv-phone">Phone <span class="font-normal text-gray-500">(optional)</span></label>
            <input id="inv-phone" v-model="form.phone" type="tel" class="input" maxlength="30" autocomplete="off" />
          </div>
        </div>
        <div v-if="data.staff">
          <span class="label">Access</span>
          <div class="segmented" role="group" aria-label="Access">
            <button v-for="o in ACCESS" :key="o.value" type="button" :aria-pressed="form.access === o.value" @click="form.access = o.value">{{ o.label }}</button>
          </div>
          <p class="hint">{{ ACCESS.find((o) => o.value === form.access).help }}</p>
        </div>
        <fieldset v-if="form.access === 'Operator'">
          <legend class="label">Machines they can log</legend>
          <MachineChecks v-model="form.machines" :machines="data.machines" />
        </fieldset>
        <p v-if="formError" role="alert" class="text-sm text-red-600">{{ formError }}</p>
      </form>
      <SentLink v-else :sent="sent" />
      <template #footer>
        <template v-if="!sent">
          <button class="btn btn-secondary" type="button" @click="inviting = false">Cancel</button>
          <button class="btn btn-primary" type="submit" form="invite-form" :disabled="saving"><FeatherIcon name="send" class="h-4 w-4" />{{ saving ? 'Inviting…' : 'Send invitation' }}</button>
        </template>
        <button v-else class="btn btn-primary" type="button" @click="inviting = false">Done</button>
      </template>
    </Modal>

    <!-- A new link -->
    <Modal :model-value="!!resent" title="New sign-in link" :subtitle="resent?.name" @update:model-value="resent = null">
      <SentLink v-if="resent" :sent="resent" />
      <template #footer><button class="btn btn-primary" type="button" @click="resent = null">Done</button></template>
    </Modal>

    <!-- Machines for an operator -->
    <Modal :model-value="!!editing" title="Machines they can log" :subtitle="editing?.full_name" @update:model-value="editing = null">
      <MachineChecks v-if="editing" v-model="editing.machines" :machines="data.machines" />
      <template #footer>
        <button class="btn btn-secondary" type="button" @click="editing = null">Cancel</button>
        <button class="btn btn-primary" type="button" :disabled="saving" @click="saveMachines">{{ saving ? 'Saving…' : 'Save' }}</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted, h } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import { api, fromNow } from '@/data/ops'

const props = defineProps({ equipment: { type: String, default: null } })
const ACCESS = [
  { value: 'Operator', label: 'Operator', help: 'Logs readings and asks for service on the machines you choose.' },
  { value: 'Customer admin', label: 'Customer admin', help: 'Sees every machine of this customer and can invite their own operators.' },
]
const data = ref(null)
const error = ref('')
const busy = ref('')
const inviting = ref(false)
const saving = ref(false)
const formError = ref('')
const sent = ref(null)
const resent = ref(null)
const editing = ref(null)
const form = reactive({ full_name: '', email: '', phone: '', access: 'Operator', machines: [] })

const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
// Staff change anyone; a customer admin changes their operators, not other admins or themselves.
const canChange = (a) => data.value.staff || (a.access === 'Operator' && !a.me)
const scope = () => (props.equipment ? { equipment: props.equipment } : {})

async function load() {
  try {
    data.value = await api('projectit.customer_accounts.list_accounts', scope())
  } catch (e) {
    data.value = null // no customer on the machine yet, or no access: leave the card out
  }
}
onMounted(load)

async function emailReport() {
  if (!window.confirm(`Email last month's plant report to ${data.value.customer_name}'s admins?`)) return
  busy.value = 'report'
  error.value = ''
  try {
    const r = await api('projectit.monthly_report.send_now', { customer: data.value.customer })
    toast({ title: `Sent to ${r.sent_to.join(', ')}`, icon: 'mail', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}
function openInvite() {
  Object.assign(form, { full_name: '', email: '', phone: '', access: 'Operator', machines: props.equipment ? [props.equipment] : data.value.machines.length === 1 ? [data.value.machines[0].name] : [] })
  formError.value = ''
  sent.value = null
  inviting.value = true
}
async function invite() {
  saving.value = true
  formError.value = ''
  try {
    const r = await api('projectit.customer_accounts.invite', { ...scope(), full_name: form.full_name, email: form.email, phone: form.phone || null, access: form.access, machines: JSON.stringify(form.machines) })
    sent.value = { name: form.full_name, email: form.email, link: r.link, emailed: r.emailed }
    load()
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}
async function resend(a) {
  busy.value = a.user
  error.value = ''
  try {
    const r = await api('projectit.customer_accounts.resend_invite', { ...scope(), user: a.user })
    resent.value = { name: a.full_name, email: a.user, link: r.link, emailed: r.emailed }
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}
async function toggle(a) {
  if (a.enabled && !window.confirm(`Switch off ${a.full_name}'s account? They will not be able to sign in. Their logs are kept.`)) return
  busy.value = a.user
  error.value = ''
  try {
    await api('projectit.customer_accounts.update_account', { ...scope(), user: a.user, enabled: a.enabled ? 0 : 1 })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}
function openMachines(a) {
  editing.value = { user: a.user, full_name: a.full_name, machines: [...a.machines] }
}
async function saveMachines() {
  saving.value = true
  try {
    await api('projectit.customer_accounts.update_account', { ...scope(), user: editing.value.user, machines: JSON.stringify(editing.value.machines) })
    editing.value = null
    await load()
  } catch (e) {
    error.value = e.message
    editing.value = null
  } finally {
    saving.value = false
  }
}

// Checkboxes for the customer's machines.
const MachineChecks = (p, { emit }) =>
  h('div', { class: 'space-y-1.5' }, p.machines.length
    ? p.machines.map((m) => h('label', { class: 'flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 text-sm' }, [
      h('input', { type: 'checkbox', class: 'h-4 w-4 rounded border-gray-300 text-brand-600', checked: p.modelValue.includes(m.name),
        onChange: (e) => emit('update:modelValue', e.target.checked ? [...p.modelValue, m.name] : p.modelValue.filter((x) => x !== m.name)) }),
      h('span', { class: 'min-w-0 flex-1' }, [h('span', { class: 'block font-medium text-gray-900' }, m.equipment_name), h('span', { class: 'block text-xs text-gray-500' }, [m.site, m.name].filter(Boolean).join(' · '))]),
    ]))
    : [h('p', { class: 'text-sm text-gray-500' }, 'This customer has no machines registered yet.')])
MachineChecks.props = ['modelValue', 'machines']
MachineChecks.emits = ['update:modelValue']

// After inviting: whether the email went, and the link to share another way (WhatsApp, SMS).
const SentLink = (p) =>
  h('div', { class: 'space-y-3 text-sm' }, [
    h('p', { class: 'flex items-start gap-2 ' + (p.sent.emailed ? 'text-green-700' : 'text-amber-800') }, [
      h(FeatherIcon, { name: p.sent.emailed ? 'check-circle' : 'alert-triangle', class: 'mt-0.5 h-4 w-4 shrink-0' }),
      p.sent.emailed ? `We emailed ${p.sent.email} a link to set their password.` : `The email could not be sent from this site. Share this link with ${p.sent.name} another way.`,
    ]),
    h('div', { class: 'flex gap-2' }, [
      h('input', { class: 'input font-mono text-xs', readonly: true, value: p.sent.link, 'aria-label': 'Sign-in link', onFocus: (e) => e.target.select() }),
      h('button', { type: 'button', class: 'btn btn-secondary shrink-0', onClick: () => navigator.clipboard?.writeText(p.sent.link).then(() => toast({ title: 'Link copied', icon: 'check', iconClasses: 'text-green-600', position: 'top-center' })) }, [
        h(FeatherIcon, { name: 'copy', class: 'h-4 w-4' }), 'Copy']),
    ]),
    h('p', { class: 'text-xs text-gray-500' }, 'The link works once. They choose a password, then the plant app opens. Use New link if it expires.'),
  ])
SentLink.props = ['sent']
</script>
