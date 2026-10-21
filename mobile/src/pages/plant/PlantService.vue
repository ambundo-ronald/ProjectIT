<template>
  <div class="space-y-4">
    <!-- Ask for service -->
    <div class="card flex flex-wrap items-center gap-4 p-5">
      <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><FeatherIcon name="tool" class="h-6 w-6" /></span>
      <div class="min-w-0 flex-1 basis-48">
        <h1 class="text-[17px] font-semibold text-gray-900">Need us?</h1>
        <p class="text-sm text-gray-600">Tell us what is wrong with {{ machine?.equipment_name || 'the machine' }}. We reply here and by notification.</p>
      </div>
      <button class="btn btn-primary w-full sm:w-auto" @click="openAsk"><FeatherIcon name="plus" class="h-4 w-4" />Ask for service</button>
      <p v-if="plant.me?.support_phone" class="w-full text-xs text-gray-500">Plant stopped or water unsafe? Also call us: <a :href="`tel:${plant.me.support_phone}`" class="link">{{ plant.me.support_phone }}</a></p>
    </div>

    <div v-if="!s && !error" class="space-y-3" aria-busy="true"><div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-2xl bg-gray-200/70" /></div>
    <EmptyState v-else-if="error" icon="alert-circle" title="Service could not be loaded" :text="error" />

    <template v-else>
      <!-- Planned visits -->
      <div v-if="s.planned.length" class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Planned visits</h2></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="p in s.planned" :key="`${p.on}${p.kind}`" class="flex items-center gap-3 px-5 py-3 text-sm">
            <FeatherIcon name="calendar" class="h-4 w-4 shrink-0 text-brand-600" />
            <span class="flex-1 font-medium text-gray-900">{{ p.kind }}</span>
            <span class="tabular-nums text-gray-700">{{ formatDate(p.on) }}</span>
          </li>
        </ul>
      </div>

      <!-- Requests -->
      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Your requests</h2><span class="text-xs text-gray-500">{{ s.requests.length }}</span></div>
        <ul v-if="s.requests.length" class="divide-y divide-gray-100">
          <li v-for="r in s.requests" :key="r.name" class="px-5 py-3 text-sm">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <p class="min-w-0 flex-1 font-medium text-gray-900">{{ r.subject }}<span v-if="r.urgent" class="ml-2 rounded bg-red-50 px-1.5 text-[11px] font-semibold text-red-700">Urgent</span></p>
              <span class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold" :class="STATE[r.state.key].chip">
                <FeatherIcon :name="STATE[r.state.key].icon" class="h-3.5 w-3.5" />{{ r.state.label }}<template v-if="r.state.on"> for {{ formatDate(r.state.on) }}</template>
              </span>
            </div>
            <p v-if="r.description" class="mt-1 line-clamp-2 whitespace-pre-wrap text-xs text-gray-600">{{ r.description }}</p>
            <p v-if="r.state.note" class="mt-1 text-xs text-gray-700">{{ r.state.note }}</p>
            <p v-if="r.reason" class="mt-1 text-xs text-gray-700"><span class="font-medium">Our reply:</span> {{ r.reason }}</p>
            <p class="mt-1 text-xs text-gray-500">{{ formatDate(r.on) }} · {{ r.mine ? 'You' : r.by }}<template v-if="r.visit"> · <a href="#visits" class="link" @click.prevent="showVisit(r.visit)">See the visit</a></template></p>
          </li>
        </ul>
        <p v-else class="px-5 py-4 text-sm text-gray-500">No requests yet.</p>
      </div>

      <!-- Visits -->
      <div id="visits" class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Past visits</h2><span class="text-xs text-gray-500">{{ s.visits.length }}</span></div>
        <ul v-if="s.visits.length" class="divide-y divide-gray-100">
          <li v-for="v in s.visits" :id="`visit-${v.name}`" :key="v.name" class="px-5 py-4 text-sm" :class="highlight === v.name ? 'bg-brand-50' : ''">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <p class="font-medium text-gray-900">{{ v.kind }}<span class="font-normal text-gray-500"> · {{ v.title }}</span></p>
              <span class="text-xs tabular-nums text-gray-500">{{ formatDate(v.on) }}</span>
            </div>
            <p v-if="v.summary" class="mt-1 whitespace-pre-wrap text-gray-700">{{ v.summary }}</p>
            <p v-if="v.technicians.length" class="mt-1 text-xs text-gray-500">By {{ v.technicians.join(', ') }}</p>
            <div class="mt-2 flex flex-wrap items-center gap-3">
              <a :href="`/api/method/projectit.plant.report?job=${encodeURIComponent(v.name)}`" target="_blank" rel="noopener" class="btn btn-secondary btn-sm"><FeatherIcon name="file-text" class="h-4 w-4" />Service report</a>
              <!-- Rating -->
              <span v-if="v.rating && rating?.name !== v.name" class="flex items-center gap-1 text-xs text-gray-600" :aria-label="`You rated this visit ${v.rating} out of 5`">
                <FeatherIcon v-for="n in 5" :key="n" name="star" class="h-4 w-4" :class="n <= v.rating ? 'fill-amber-400 text-amber-500' : 'text-gray-300'" />
                <button v-if="v.can_rate" class="ml-1 link" @click="startRating(v)">Change</button>
              </span>
              <button v-else-if="v.can_rate && rating?.name !== v.name" class="btn btn-ghost btn-sm" @click="startRating(v)"><FeatherIcon name="star" class="h-4 w-4" />Rate this visit</button>
            </div>
            <form v-if="rating?.name === v.name" class="mt-3 space-y-2 rounded-xl border border-gray-200 p-3" @submit.prevent="saveRating">
              <div class="flex items-center gap-1" role="radiogroup" aria-label="Stars">
                <button v-for="n in 5" :key="n" type="button" role="radio" :aria-checked="rating.stars === n" :aria-label="`${n} star${n === 1 ? '' : 's'}`" class="rounded p-1 hover:bg-gray-100" @click="rating.stars = n">
                  <FeatherIcon name="star" class="h-6 w-6" :class="n <= rating.stars ? 'fill-amber-400 text-amber-500' : 'text-gray-300'" />
                </button>
                <span class="ml-2 text-xs text-gray-600">{{ STARS[rating.stars] || 'Choose 1 to 5 stars' }}</span>
              </div>
              <textarea v-model="rating.comment" rows="2" maxlength="1000" class="input" aria-label="Comment (optional)" placeholder="Anything to tell us? (optional)" />
              <p v-if="rating.error" role="alert" class="text-sm text-red-600">{{ rating.error }}</p>
              <div class="flex justify-end gap-2">
                <button type="button" class="btn btn-secondary btn-sm" @click="rating = null">Cancel</button>
                <button type="submit" class="btn btn-primary btn-sm" :disabled="!rating.stars || rating.saving">{{ rating.saving ? 'Saving…' : 'Send rating' }}</button>
              </div>
            </form>
          </li>
        </ul>
        <p v-else class="px-5 py-4 text-sm text-gray-500">No visits yet.</p>
      </div>

      <!-- Cover -->
      <div class="card p-5">
        <h2 class="card-title">Warranty and service contract</h2>
        <dl class="mt-3 space-y-2 text-sm">
          <div class="flex justify-between gap-3"><dt class="text-gray-500">Warranty</dt><dd class="text-right" :class="s.cover.warranty_active ? 'text-gray-900' : 'text-gray-500'">{{ s.cover.warranty_until ? `${s.cover.warranty_active ? 'Until' : 'Ended'} ${formatDate(s.cover.warranty_until)}` : 'None recorded' }}</dd></div>
          <div v-if="s.cover.installed_on" class="flex justify-between gap-3"><dt class="text-gray-500">Installed</dt><dd>{{ formatDate(s.cover.installed_on) }}</dd></div>
        </dl>
        <template v-if="s.cover.contract">
          <div class="mt-4 border-t border-gray-100 pt-4">
            <p class="flex flex-wrap items-center justify-between gap-2"><span class="font-medium text-gray-900">{{ s.cover.contract.title }}</span><span class="rounded px-1.5 text-[11px] font-semibold" :class="s.cover.contract.state === 'Active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'">{{ s.cover.contract.state }}</span></p>
            <dl class="mt-2 space-y-2 text-sm">
              <div class="flex justify-between gap-3"><dt class="text-gray-500">Period</dt><dd class="text-right">{{ formatDate(s.cover.contract.start) }} – {{ formatDate(s.cover.contract.end) }}</dd></div>
              <div v-if="s.cover.contract.visit_frequency" class="flex justify-between gap-3"><dt class="text-gray-500">Service visits</dt><dd class="text-right">{{ s.cover.contract.visit_frequency }}<template v-if="s.cover.contract.visits_done !== null"> · {{ s.cover.contract.visits_done }} done</template></dd></div>
              <div class="flex justify-between gap-3"><dt class="text-gray-500">Labour</dt><dd class="text-right">{{ s.cover.contract.labour_included ? 'Included' : 'Charged' }}</dd></div>
              <div v-if="s.cover.contract.callouts_included" class="flex justify-between gap-3"><dt class="text-gray-500">Call-outs included</dt><dd class="text-right">{{ s.cover.contract.callouts_included }}</dd></div>
              <div v-if="s.cover.contract.response_hours" class="flex justify-between gap-3"><dt class="text-gray-500">We respond within</dt><dd class="text-right">{{ s.cover.contract.response_hours }} hours</dd></div>
              <div v-if="s.cover.contract.fix_hours" class="flex justify-between gap-3"><dt class="text-gray-500">We fix within</dt><dd class="text-right">{{ s.cover.contract.fix_hours }} hours</dd></div>
            </dl>
            <p v-if="s.cover.contract.items.length" class="mt-2 text-xs text-gray-600"><span class="font-medium">Parts covered:</span> {{ s.cover.contract.items.join(', ') }}</p>
          </div>
        </template>
        <p v-else class="mt-3 text-xs text-gray-500">No service contract for this machine. Ask us about one: regular visits keep the plant running and cost less than breakdowns.</p>
      </div>
    </template>

    <!-- The request form -->
    <Modal v-model="asking" title="Ask for service" :subtitle="machine?.equipment_name">
      <form id="ask-form" class="space-y-4" @submit.prevent="send">
        <div>
          <label class="label" for="ask-subject">What is wrong?</label>
          <input id="ask-subject" v-model="ask.subject" class="input" maxlength="140" required placeholder="e.g. Less water than usual, alarm on the panel, leak" />
        </div>
        <div>
          <label class="label" for="ask-details">Details <span class="font-normal text-gray-500">(optional)</span></label>
          <textarea id="ask-details" v-model="ask.description" rows="3" maxlength="4000" class="input" placeholder="When it started, what you see or hear, anything you already tried" />
        </div>
        <label class="flex items-start gap-3 rounded-lg border border-gray-200 px-3 py-2.5 text-sm">
          <input v-model="ask.urgent" type="checkbox" class="mt-0.5 h-4 w-4 rounded border-gray-300 text-red-600" />
          <span><span class="block font-medium text-gray-900">Urgent</span><span class="block text-xs text-gray-500">The plant has stopped, or the water is not safe to use.</span></span>
        </label>
        <div class="flex flex-wrap items-center gap-3">
          <PhotoButtons camera-label="Add a photo" :disabled="sending" @photos="(p) => (ask.photo = p[0])" @error="(m) => (askError = m)" />
          <span v-if="ask.photo" class="flex items-center gap-2">
            <img :src="ask.photo.preview" alt="Photo to send" class="h-12 w-12 rounded-lg object-cover" />
            <button type="button" class="btn btn-ghost btn-icon text-gray-500" aria-label="Remove the photo" @click="ask.photo = null"><FeatherIcon name="x" class="h-4 w-4" /></button>
          </span>
        </div>
        <p v-if="askError" role="alert" class="text-sm text-red-600">{{ askError }}</p>
      </form>
      <template #footer>
        <button class="btn btn-secondary" type="button" @click="asking = false">Cancel</button>
        <button class="btn btn-primary" type="submit" form="ask-form" :disabled="sending || !ask.subject.trim()"><FeatherIcon name="send" class="h-4 w-4" />{{ sending ? 'Sending…' : 'Send request' }}</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, reactive, watch, onMounted, nextTick } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import Modal from '@/components/ops/Modal.vue'
import PhotoButtons from '@/components/ops/PhotoButtons.vue'
import { api, request, formatDate } from '@/data/ops'
import { plant, machine } from '@/data/plant'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// Request states: an icon and a word, never colour alone.
const STATE = {
  received: { icon: 'inbox', chip: 'bg-gray-100 text-gray-700' },
  accepted: { icon: 'check', chip: 'bg-brand-50 text-brand-700' },
  scheduled: { icon: 'calendar', chip: 'bg-brand-50 text-brand-700' },
  onway: { icon: 'navigation', chip: 'bg-brand-50 text-brand-700' },
  working: { icon: 'tool', chip: 'bg-amber-50 text-amber-800' },
  done: { icon: 'check-circle', chip: 'bg-green-50 text-green-700' },
  closed: { icon: 'x-circle', chip: 'bg-gray-100 text-gray-600' },
}
const STARS = { 1: 'Very poor', 2: 'Poor', 3: 'OK', 4: 'Good', 5: 'Excellent' }
const s = ref(null)
const error = ref('')
const asking = ref(false)
const sending = ref(false)
const askError = ref('')
const ask = reactive({ subject: '', description: '', urgent: false, photo: null })
const rating = ref(null)
const highlight = ref('')

async function load() {
  if (!plant.machine) return
  error.value = ''
  try {
    s.value = await api('projectit.plant.service', { equipment: plant.machine })
  } catch (e) {
    if (!s.value) error.value = e.message
  }
}
watch(() => plant.machine, () => {
  s.value = null
  load()
})
onMounted(() => {
  load()
  // From "Ask for service" on an out-of-range reading: open the form with the readings filled in.
  if (route.query.ask) {
    openAsk()
    ask.subject = String(route.query.ask).slice(0, 140)
    router.replace({ query: {} })
  }
})

function openAsk() {
  Object.assign(ask, { subject: '', description: '', urgent: false, photo: null })
  askError.value = ''
  asking.value = true
}
async function send() {
  sending.value = true
  askError.value = ''
  try {
    const r = await request('projectit.plant.request_service', { equipment: plant.machine, subject: ask.subject, description: ask.description || null, urgent: ask.urgent ? 1 : 0, photo: ask.photo?.content || null })
    asking.value = false
    if (r.request && s.value) s.value.requests.unshift(r.request)
    toast({ title: 'Request sent. We will get back to you.', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    askError.value = e.offline ? 'No signal: the request could not be sent. Try again when you are online, or call us.' : e.message
  } finally {
    sending.value = false
  }
}

function startRating(v) {
  rating.value = { name: v.name, stars: v.rating || 0, comment: v.comment || '', saving: false, error: '' }
}
async function saveRating() {
  rating.value.saving = true
  rating.value.error = ''
  try {
    const r = await request('projectit.plant.rate_visit', { job: rating.value.name, rating: rating.value.stars, comment: rating.value.comment || null })
    const i = s.value.visits.findIndex((v) => v.name === r.visit.name)
    if (i >= 0) s.value.visits[i] = r.visit
    rating.value = null
    toast({ title: 'Thank you for your rating', icon: 'star', iconClasses: 'text-amber-500', position: 'top-center' })
  } catch (e) {
    rating.value.error = e.message
    rating.value.saving = false
  }
}
async function showVisit(name) {
  highlight.value = name
  await nextTick()
  document.getElementById(`visit-${name}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  setTimeout(() => (highlight.value = ''), 2500)
}
</script>
