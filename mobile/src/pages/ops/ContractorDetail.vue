<template>
  <section class="mx-auto max-w-5xl p-4 md:p-8">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsContractors' }" class="hover:text-gray-800">Contractors</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">{{ c?.contractor_name || route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data && !error" class="space-y-4" aria-busy="true"><div class="h-32 animate-pulse rounded-xl bg-gray-200/70" /><div class="h-56 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <div v-if="data" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div class="min-w-0 space-y-5">
        <!-- Details -->
        <div class="card p-5">
          <div v-if="!editing" class="flex items-start gap-4">
            <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600"><FeatherIcon :name="c.contractor_type === 'Company' ? 'briefcase' : 'user'" class="h-6 w-6" /></span>
            <div class="min-w-0 flex-1">
              <h1 class="text-[20px] font-semibold leading-snug tracking-tight md:text-[24px]">{{ c.contractor_name }}<span v-if="!c.enabled" class="ml-2 align-middle rounded bg-gray-100 px-1.5 text-xs font-semibold text-gray-500">Inactive</span></h1>
              <p class="mt-0.5 text-sm text-gray-500">{{ [c.contractor_type === 'Company' ? 'Company with a crew' : 'Individual', c.trades].filter(Boolean).join(' · ') }}</p>
              <dl class="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
                <div class="flex gap-2"><dt class="text-gray-500">Supplier</dt><dd class="truncate"><a :href="`/desk/supplier/${encodeURIComponent(c.supplier)}`" target="_blank" rel="noopener" class="link">{{ data.supplier_name || c.supplier }}</a></dd></div>
                <div class="flex gap-2"><dt class="text-gray-500">Pay cycle</dt><dd>{{ c.pay_cycle }}</dd></div>
                <div v-if="c.phone" class="flex gap-2"><dt class="text-gray-500">Phone</dt><dd><a :href="`tel:${c.phone}`" class="link">{{ c.phone }}</a></dd></div>
                <div class="flex gap-2"><dt class="text-gray-500">Bought on site</dt><dd>{{ c.purchases === 'Included in price' ? 'Included in price' : 'Paid back' }}</dd></div>
              </dl>
              <p v-if="c.notes" class="mt-3 whitespace-pre-wrap text-sm text-gray-700">{{ c.notes }}</p>
            </div>
            <button class="btn btn-secondary btn-sm" @click="startEdit"><FeatherIcon name="edit-2" class="h-4 w-4" />Edit</button>
          </div>
          <form v-else class="space-y-3" @submit.prevent="saveDetails">
            <div><label class="label" for="cd-name">Name</label><input id="cd-name" v-model="form.contractor_name" class="input" required maxlength="140" /></div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div><label class="label" for="cd-type">Type</label><select id="cd-type" v-model="form.contractor_type" class="input"><option value="Individual">Individual</option><option value="Company">Company with a crew</option></select></div>
              <div><label class="label" for="cd-cycle">Usual pay cycle</label><select id="cd-cycle" v-model="form.pay_cycle" class="input"><option v-for="p in data.pay_cycles" :key="p">{{ p }}</option></select></div>
              <div><label class="label" for="cd-phone">Phone</label><input id="cd-phone" v-model="form.phone" type="tel" class="input" /></div>
              <div><label class="label" for="cd-email">Email</label><input id="cd-email" v-model="form.email" type="email" class="input" /></div>
              <div><label class="label" for="cd-buy">Bought on site</label><select id="cd-buy" v-model="form.purchases" class="input"><option value="Reimbursed">We pay it back</option><option value="Included in price">Included in their price</option></select></div>
              <div><label class="label" for="cd-supplier">Supplier</label><input id="cd-supplier" v-model="form.supplier" class="input" /></div>
            </div>
            <div><label class="label" for="cd-trades">Skills or trades</label><input id="cd-trades" v-model="form.trades" class="input" maxlength="1000" /></div>
            <div><label class="label" for="cd-notes">Notes</label><textarea id="cd-notes" v-model="form.notes" rows="3" class="input" maxlength="4000" /></div>
            <label class="flex items-center gap-2 text-sm"><input v-model="form.enabled" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-brand-600" />Active (inactive contractors can't be given new jobs)</label>
            <div class="flex gap-2"><button class="btn btn-primary" :disabled="busy">Save</button><button type="button" class="btn btn-ghost" @click="editing = false">Cancel</button></div>
          </form>
        </div>

        <!-- People -->
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">People</h2><button class="btn btn-secondary btn-sm -mr-2" @click="openInvite"><FeatherIcon name="user-plus" class="h-4 w-4" />Invite</button></div>
          <ul v-if="data.members.length" class="divide-y divide-gray-100">
            <li v-for="m in data.members" :key="m.user" class="flex items-center gap-3 px-4 py-3">
              <UserAvatar :name="m.full_name" size="md" />
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium" :class="m.enabled ? 'text-gray-900' : 'text-gray-400 line-through'">{{ m.full_name }}</span>
                <span class="block truncate text-xs text-gray-500">{{ m.user }} · {{ m.enabled ? (m.joined ? `last in ${fromNow(m.last_login)}` : 'invited, not signed in yet') : 'switched off' }}</span>
              </span>
              <select :value="m.member_role" class="input !h-8 !w-auto text-xs" :aria-label="`${m.full_name}'s role`" @change="updateMember(m, { member_role: $event.target.value })"><option>Owner</option><option>Lead</option><option>Crew</option></select>
              <Dropdown>
                <template #trigger="{ open, toggle }"><button class="btn btn-ghost btn-icon" :aria-expanded="open" aria-haspopup="menu" :aria-label="`More for ${m.full_name}`" @click="toggle"><FeatherIcon name="more-vertical" class="h-4 w-4" /></button></template>
                <template #default="{ close }">
                  <button v-if="m.enabled" class="menu-item" role="menuitem" @click="close(); resend(m)"><FeatherIcon name="send" class="h-4 w-4" />Send a new sign-in link</button>
                  <button class="menu-item" :class="m.enabled ? 'text-red-600' : ''" role="menuitem" @click="close(); updateMember(m, { enabled: m.enabled ? 0 : 1 })"><FeatherIcon :name="m.enabled ? 'user-x' : 'user-check'" class="h-4 w-4" />{{ m.enabled ? 'Switch off' : 'Switch on' }}</button>
                </template>
              </Dropdown>
            </li>
          </ul>
          <p v-else class="px-4 py-4 text-sm text-gray-500">Invite the {{ c.contractor_type === 'Company' ? 'owner first. They can add their own crew in the app.' : 'technician so they can use the app.' }}</p>
        </div>

        <!-- Rate card -->
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Rate card</h2><button v-if="!editingRates" class="btn btn-secondary btn-sm -mr-2" @click="startRates"><FeatherIcon name="edit-2" class="h-4 w-4" />Edit</button></div>
          <div v-if="editingRates" class="space-y-2 p-4">
            <div v-for="(r, i) in rates" :key="i" class="grid grid-cols-[minmax(0,1fr)_7rem_7rem_auto] items-center gap-2">
              <input v-model="r.activity" class="input text-sm" maxlength="140" placeholder="Activity, e.g. Filter change" :aria-label="`Activity ${i + 1}`" />
              <select v-model="r.unit" class="input text-sm" :aria-label="`Unit ${i + 1}`"><option v-for="u in data.units" :key="u">{{ u }}</option></select>
              <input v-model.number="r.rate" type="number" min="0" step="any" class="input text-sm" placeholder="Rate" :aria-label="`Rate ${i + 1}`" />
              <button class="btn btn-ghost btn-icon" :aria-label="`Remove rate ${i + 1}`" @click="rates.splice(i, 1)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button>
            </div>
            <button class="btn btn-ghost btn-sm" @click="rates.push({ activity: '', unit: 'Job', rate: null })"><FeatherIcon name="plus" class="h-4 w-4" />Add a rate</button>
            <div class="flex gap-2 border-t border-gray-100 pt-3"><button class="btn btn-primary btn-sm" :disabled="busy" @click="saveRates">Save rates</button><button class="btn btn-ghost btn-sm" @click="editingRates = false">Cancel</button></div>
          </div>
          <table v-else-if="data.rates.length" class="w-full text-sm">
            <tbody class="divide-y divide-gray-100">
              <tr v-for="r in data.rates" :key="r.name"><td class="px-4 py-2.5">{{ r.activity }}</td><td class="px-4 py-2.5 text-gray-500">per {{ r.unit.toLowerCase() }}</td><td class="px-4 py-2.5 text-right font-medium tabular-nums">{{ money(r.rate) }}</td></tr>
            </tbody>
          </table>
          <p v-else class="px-4 py-4 text-sm text-gray-500">Their usual prices. Pick from it when you set the pay on a job.</p>
        </div>

        <!-- Pay -->
        <div v-if="statement">
          <h2 class="section-label mb-2 px-1">Pay</h2>
          <ContractorStatement :data="statement">
            <template #actions="{ line }">
              <button v-if="line.queried" class="btn btn-secondary btn-sm" @click="answer(line)"><FeatherIcon name="message-square" class="h-4 w-4" />Answer the query</button>
              <button v-if="line.shown === 'Approved'" class="btn btn-ghost btn-sm text-gray-600" @click="hold(line, 1)">Hold</button>
              <button v-if="line.shown === 'On hold'" class="btn btn-ghost btn-sm text-gray-600" @click="hold(line, 0)">Release</button>
              <router-link v-if="line.work_order" :to="{ name: 'OpsWorkOrder', params: { name: line.work_order } }" class="btn btn-ghost btn-sm text-gray-600">Job</router-link>
            </template>
          </ContractorStatement>
        </div>
      </div>

      <aside class="space-y-4 lg:sticky lg:top-8 lg:self-start">
        <div class="card p-4">
          <p class="section-label">We owe them</p>
          <p class="mt-1 text-[22px] font-semibold tabular-nums">{{ money((data.owed?.approved || 0) + (data.owed?.billed || 0)) }}</p>
          <p class="text-xs text-gray-500">{{ money(data.owed?.approved || 0) }} approved, not yet billed · {{ money(data.owed?.billed || 0) }} billed, not yet paid</p>
          <router-link v-if="me.can_invoice" :to="{ name: 'OpsPayouts' }" class="btn btn-secondary btn-sm mt-3 w-full">Payouts</router-link>
          <a :href="`/api/method/projectit.contractor_pay.download_statement?contractor=${encodeURIComponent(c.name)}`" target="_blank" rel="noopener" class="btn btn-ghost btn-sm mt-1 w-full"><FeatherIcon name="download" class="h-4 w-4" />Statement (PDF)</a>
        </div>
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Jobs</h2><span class="text-xs text-gray-500">latest {{ data.jobs.length }}</span></div>
          <ul v-if="data.jobs.length" class="divide-y divide-gray-100 text-sm">
            <li v-for="j in data.jobs" :key="j.name">
              <router-link :to="{ name: 'OpsWorkOrder', params: { name: j.name } }" class="block px-4 py-2.5 hover:bg-gray-50">
                <span class="block truncate font-medium text-gray-900">{{ j.subject }}</span>
                <span class="text-xs text-gray-500">{{ j.custom_contractor_state === 'Accepted' ? (STATUS_LABEL[j.status] || j.status) : j.custom_contractor_state }}<template v-if="j.exp_end_date"> · due {{ formatDate(j.exp_end_date) }}</template></span>
              </router-link>
            </li>
          </ul>
          <p v-else class="px-4 py-4 text-sm text-gray-500">Give them a job from its page: Give to a contractor.</p>
        </div>
        <div v-if="data.projects.length" class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Projects</h2></div>
          <ul class="divide-y divide-gray-100 text-sm">
            <li v-for="p in data.projects" :key="p.project" class="px-4 py-2.5"><span class="block font-medium">{{ p.project_name || p.project }}</span><span v-if="p.instructions" class="line-clamp-2 text-xs text-gray-500">{{ p.instructions }}</span></li>
          </ul>
        </div>
      </aside>
    </div>

    <Modal v-model="inviting" title="Invite someone" :subtitle="`To ${c?.contractor_name}. They get an email with a link to set their password.`">
      <form id="cd-invite" class="space-y-3" @submit.prevent="invite">
        <div><label class="label" for="ci2-name">Name</label><input id="ci2-name" v-model="person.full_name" class="input" required maxlength="140" /></div>
        <div><label class="label" for="ci2-email">Email</label><input id="ci2-email" v-model="person.email" type="email" class="input" required /></div>
        <div><label class="label" for="ci2-phone">Phone <span class="font-normal text-gray-400">(optional)</span></label><input id="ci2-phone" v-model="person.phone" type="tel" class="input" /></div>
        <div>
          <span class="label">Role</span>
          <div class="segmented w-full" role="group" aria-label="Role">
            <button v-for="r in ['Owner', 'Lead', 'Crew']" :key="r" type="button" class="flex-1" :aria-pressed="person.member_role === r" @click="person.member_role = r">{{ r }}</button>
          </div>
          <p class="hint">Owner: accepts jobs, runs the crew and sees pay. Lead: accepts jobs and assigns crew. Crew: does the jobs.</p>
        </div>
        <p v-if="inviteError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ inviteError }}</p>
        <div v-if="link" class="rounded-lg bg-green-50 p-3 text-sm text-green-900">
          <p>{{ emailed ? 'Invite sent.' : 'The email could not be sent.' }} You can also share this link (WhatsApp, SMS):</p>
          <input :value="link" readonly class="input mt-2 font-mono text-xs" aria-label="Invite link" @focus="$event.target.select()" />
        </div>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="inviting = false">{{ link ? 'Done' : 'Cancel' }}</button>
        <button v-if="!link" type="submit" form="cd-invite" class="btn btn-primary" :disabled="busy">Send invite</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import Dropdown from '@/components/ops/Dropdown.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import ContractorStatement from '@/components/ops/ContractorStatement.vue'
import { api, me, loadMe, formatDate, fromNow, STATUS_LABEL } from '@/data/ops'
import { money as fmt } from '@/data/contractor'

const route = useRoute()
const data = ref(null)
const statement = ref(null)
const error = ref('')
const busy = ref(false)
const editing = ref(false)
const editingRates = ref(false)
const rates = ref([])
const form = reactive({})
const inviting = ref(false)
const inviteError = ref('')
const link = ref('')
const emailed = ref(false)
const person = reactive({ full_name: '', email: '', phone: '', member_role: 'Crew' })
const c = computed(() => data.value?.contractor)
const money = (v) => fmt(v, statement.value?.currency)
const toastError = (e) => toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })

async function load() {
  try {
    data.value = await api('projectit.contractors.get_contractor', { name: route.params.name })
    error.value = ''
    loadStatement()
  } catch (e) {
    error.value = e.message
  }
}
async function loadStatement() {
  try {
    statement.value = await api('projectit.contractor_pay.statement', { contractor: route.params.name })
  } catch (e) {
    statement.value = null
  }
}
function startEdit() {
  Object.assign(form, { ...c.value, enabled: !!c.value.enabled })
  editing.value = true
}
async function save(changes) {
  busy.value = true
  try {
    data.value = await api('projectit.contractors.save_contractor', { name: c.value.name, data: { ...c.value, ...changes, rates: changes.rates ?? data.value.rates } })
    return true
  } catch (e) {
    toastError(e)
    return false
  } finally {
    busy.value = false
  }
}
async function saveDetails() {
  if (await save({ ...form, enabled: form.enabled ? 1 : 0 })) editing.value = false
}
function startRates() {
  rates.value = data.value.rates.map((r) => ({ ...r }))
  if (!rates.value.length) rates.value.push({ activity: '', unit: 'Job', rate: null })
  editingRates.value = true
}
async function saveRates() {
  if (await save({ rates: rates.value.filter((r) => r.activity) })) editingRates.value = false
}
function openInvite() {
  Object.assign(person, { full_name: '', email: '', phone: '', member_role: data.value.members.some((m) => m.member_role === 'Owner') ? 'Crew' : 'Owner' })
  inviteError.value = ''
  link.value = ''
  inviting.value = true
}
async function invite() {
  busy.value = true
  inviteError.value = ''
  try {
    const r = await api('projectit.contractors.invite_member', { contractor: c.value.name, ...person })
    link.value = r.link
    emailed.value = r.emailed
    load()
  } catch (e) {
    inviteError.value = e.message
  } finally {
    busy.value = false
  }
}
async function updateMember(m, changes) {
  try {
    await api('projectit.contractors.update_member', { contractor: c.value.name, user: m.user, ...changes })
    load()
  } catch (e) {
    toastError(e)
    load()
  }
}
async function resend(m) {
  try {
    const r = await api('projectit.contractors.resend_invite', { contractor: c.value.name, user: m.user })
    window.prompt(r.emailed ? 'Sent by email. You can also share this link:' : 'The email could not be sent. Share this link instead:', r.link)
  } catch (e) {
    toastError(e)
  }
}
async function hold(line, on) {
  try {
    await api('projectit.contractor_pay.hold_line', { line: line.name, hold: on })
    loadStatement()
  } catch (e) {
    toastError(e)
  }
}
async function answer(line) {
  const note = window.prompt(`Answer about “${line.description}”:`)
  if (!note) return
  try {
    await api('projectit.contractor_pay.answer_query', { line: line.name, note })
    loadStatement()
  } catch (e) {
    toastError(e)
  }
}
onMounted(() => {
  loadMe().catch(() => {})
  load()
})
</script>
