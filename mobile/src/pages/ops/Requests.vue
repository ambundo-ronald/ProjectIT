<template>
  <section class="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
    <PageHeader :title="me.manager ? 'Work requests' : 'My requests'" :subtitle="me.manager ? 'Problems reported by your team and by QR code scans.' : 'Problems you have reported and what happened to them.'">
      <button class="btn btn-primary" @click="openNew()"><FeatherIcon name="alert-triangle" class="h-4 w-4" /><span class="hidden sm:inline">Report a problem</span><span class="sm:hidden">Report</span></button>
    </PageHeader>

    <div class="tabs" role="tablist">
      <button v-for="s in states" :key="s.value" role="tab" :aria-selected="state === s.value" @click="state = s.value; load()">
        {{ s.label }}<span v-if="s.value === 'Pending' && me.counts?.pending_requests" class="ml-1.5 rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-800">{{ me.counts.pending_requests }}</span>
      </button>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="busy && !rows.length" class="space-y-2">
      <div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <ul v-else-if="rows.length" class="card divide-y divide-gray-100 overflow-hidden" :class="busy && 'opacity-60'">
      <li v-for="r in rows" :key="r.name" class="flex flex-col gap-3 p-4 hover:bg-gray-50/70 sm:flex-row sm:items-center">
        <button class="flex min-w-0 flex-1 items-start gap-3 text-left" @click="open(r.name)">
          <UserAvatar :name="r.raised_by_name || r.raised_by" size="lg" />
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2">
              <span class="truncate font-semibold text-gray-900">{{ r.subject }}</span>
              <StatusPill :status="r.state" request class="shrink-0" />
            </span>
            <span class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
              <span>{{ r.raised_by_name || r.raised_by }}</span>
              <span>{{ fromNow(r.creation) }}</span>
              <span v-if="r.equipment" class="inline-flex items-center gap-1"><FeatherIcon name="droplet" class="h-3.5 w-3.5" />{{ r.equipment.customer_name }} · {{ r.equipment.equipment_name }}</span>
              <span v-else-if="r.custom_asset" class="inline-flex items-center gap-1"><FeatherIcon name="box" class="h-3.5 w-3.5" />{{ r.asset_name || r.custom_asset }}</span>
              <span v-else-if="r.custom_location" class="inline-flex items-center gap-1"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />{{ r.custom_location }}</span>
            </span>
          </span>
        </button>
        <div v-if="me.manager && r.state === 'Pending'" class="flex gap-2 pl-12 sm:pl-0">
          <button class="btn btn-secondary btn-sm" @click="startDecline(r)">Decline</button>
          <button class="btn btn-success btn-sm" @click="approving = r"><FeatherIcon name="check" class="h-4 w-4" />Approve</button>
        </div>
        <router-link v-else-if="r.custom_work_order" :to="{ name: 'OpsWorkOrder', params: { name: r.custom_work_order } }" class="btn btn-ghost btn-sm ml-12 self-start text-brand-700 sm:ml-0 sm:self-center">View work order<FeatherIcon name="arrow-right" class="h-4 w-4" /></router-link>
      </li>
    </ul>
    <EmptyState v-else :icon="state === 'Pending' ? 'check-circle' : 'inbox'" :title="state === 'Pending' ? 'All caught up' : 'No requests here'" :text="state === 'Pending' ? 'New problem reports will appear here for review.' : 'Requests move here as they are approved, declined or completed.'" />
    <Pager :total="total" :start="start" :page-length="pageLength" :busy="busy" label="Request pages" @change="load" @update:page-length="(n) => { pageLength = n; load() }" />

    <!-- New request -->
    <Modal v-model="creating" title="Report a problem" subtitle="A manager will review it and turn it into a work order.">
      <form id="request-form" class="space-y-4" @submit.prevent="submit">
        <div>
          <label class="label" for="rq-subject">What's wrong? <span class="text-red-500">*</span></label>
          <input id="rq-subject" v-model="form.subject" required maxlength="140" class="input" placeholder="e.g. Leaking pipe in the plant room" />
        </div>
        <div>
          <label class="label" for="rq-details">Details</label>
          <textarea id="rq-details" v-model="form.description" rows="3" maxlength="4000" class="input" placeholder="When did it start? Is it safe to use?" />
        </div>
        <div>
          <span class="label">Customer equipment <span class="font-normal text-gray-400">(optional)</span></span>
          <EquipmentPicker v-model="form.equipment" :label="form.equipmentLabel" @picked="(e) => (form.equipmentLabel = e ? `${e.customer_name} · ${e.equipment_name}` : '')" />
        </div>
        <div v-if="!form.equipment">
          <span class="label">Our asset <span class="font-normal text-gray-400">(optional)</span></span>
          <AssetPicker v-model="form.asset" :label="form.assetLabel" @picked="(a) => (form.assetLabel = a?.asset_name || '')" />
        </div>
        <div>
          <span class="label">Photo <span class="font-normal text-gray-400">(optional)</span></span>
          <div v-if="form.photo" class="flex items-center gap-3">
            <img :src="form.photo.preview" alt="Photo to send" class="h-16 w-16 rounded-lg border border-gray-200 object-cover" />
            <button type="button" class="btn btn-ghost btn-sm text-gray-500" @click="form.photo = null">Remove</button>
          </div>
          <PhotoButtons v-else @photos="(list) => (form.photo = list[0])" @error="(e) => (formError = e)" />
        </div>
        <p v-if="formError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ formError }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-secondary" @click="creating = false">Cancel</button>
        <button form="request-form" :disabled="busy" class="btn btn-primary">Submit request</button>
      </template>
    </Modal>

    <!-- Request detail -->
    <Modal :model-value="!!detail" :title="detail?.request.subject" :subtitle="detail ? `#${detail.request.name} · ${formatDate(detail.request.creation)}` : ''" size="lg" @update:model-value="detail = null">
      <div v-if="detail" class="space-y-4 text-sm">
        <div class="flex flex-wrap items-center gap-3">
          <StatusPill :status="detail.request.state" request />
          <span class="inline-flex items-center gap-2"><UserAvatar :name="detail.request.raised_by_name || detail.request.raised_by" size="sm" />{{ detail.request.raised_by_name || detail.request.raised_by }}</span>
          <router-link v-if="detail.equipment" :to="{ name: 'OpsEquipmentDetail', params: { name: detail.equipment.name } }" class="inline-flex items-center gap-1 text-gray-600 hover:text-brand-700"><FeatherIcon name="droplet" class="h-4 w-4" />{{ detail.equipment.customer_name }} · {{ detail.equipment.equipment_name }}</router-link>
          <CoverageBadge v-if="detail.equipment" :kind="detail.equipment.coverage.kind" :until="detail.equipment.coverage.until" />
          <router-link v-if="detail.request.custom_asset" :to="{ name: 'OpsAsset', params: { name: detail.request.custom_asset } }" class="inline-flex items-center gap-1 text-gray-600 hover:text-brand-700"><FeatherIcon name="box" class="h-4 w-4" />{{ detail.asset_name || detail.request.custom_asset }}</router-link>
          <span v-if="detail.request.custom_location" class="inline-flex items-center gap-1 text-gray-600"><FeatherIcon name="map-pin" class="h-4 w-4" />{{ detail.request.custom_location }}</span>
        </div>
        <p v-if="detail.description" class="whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-[15px] leading-relaxed text-gray-800">{{ detail.description }}</p>
        <div v-if="detail.files.length" class="grid grid-cols-3 gap-2 sm:grid-cols-4">
          <a v-for="f in detail.files.filter((f) => safeFile(f.file_url))" :key="f.name" :href="f.file_url" target="_blank" rel="noopener" class="block aspect-square overflow-hidden rounded-lg border border-gray-200"><img :src="f.file_url" :alt="f.file_name" class="h-full w-full object-cover" /></a>
        </div>
        <router-link v-if="detail.request.custom_work_order" :to="{ name: 'OpsWorkOrder', params: { name: detail.request.custom_work_order } }" class="flex items-center justify-between rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
          <span class="inline-flex items-center gap-2 font-medium"><FeatherIcon name="tool" class="h-4 w-4 text-gray-500" />Work order #{{ detail.request.custom_work_order }}</span>
          <FeatherIcon name="arrow-right" class="h-4 w-4 text-gray-400" />
        </router-link>
        <div v-if="detail.comments.length">
          <h3 class="section-label">History</h3>
          <ol class="mt-2 space-y-2">
            <li v-for="c in detail.comments" :key="c.name" class="text-[13px]"><span class="font-semibold">{{ c.comment_by || 'System' }}</span> <span class="text-gray-400">· {{ fromNow(c.creation) }}</span><p class="whitespace-pre-wrap text-gray-700">{{ c.content }}</p></li>
          </ol>
        </div>
        <p v-if="detailError" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-red-700">{{ detailError }}</p>
      </div>
      <template v-if="detail && detail.manager && detail.request.state === 'Pending'" #footer>
        <button class="btn btn-secondary" @click="startDecline(detail.request)">Decline</button>
        <button class="btn btn-success" @click="approving = detail.request; detail = null"><FeatherIcon name="check" class="h-4 w-4" />Approve</button>
      </template>
    </Modal>

    <!-- Decline -->
    <Modal :model-value="!!declining" title="Decline request" :subtitle="declining?.subject" @update:model-value="declining = null">
      <label class="label" for="rq-reason">Reason <span class="text-red-500">*</span></label>
      <textarea id="rq-reason" v-model="reason" rows="3" maxlength="1000" class="input" placeholder="Let the requester know why, or who handles this instead." />
      <p v-if="detailError" role="alert" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ detailError }}</p>
      <template #footer>
        <button class="btn btn-secondary" @click="declining = null">Back</button>
        <button class="btn bg-red-600 text-white hover:bg-red-700" :disabled="busy || !reason.trim()" @click="decline">Decline request</button>
      </template>
    </Modal>

    <WorkOrderForm v-model="approvingOpen" :request="approving" @saved="(r) => router.push({ name: 'OpsWorkOrder', params: { name: r.work_order } })" />
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import StatusPill from '@/components/ops/StatusPill.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import AssetPicker from '@/components/ops/AssetPicker.vue'
import EquipmentPicker from '@/components/ops/EquipmentPicker.vue'
import CoverageBadge from '@/components/ops/CoverageBadge.vue'
import WorkOrderForm from '@/components/ops/WorkOrderForm.vue'
import Pager from '@/components/ops/Pager.vue'
import { usePageLength } from '@/data/paging'
import { api, me, loadMe, formatDate, fromNow, safeFile } from '@/data/ops'
import PhotoButtons from '@/components/ops/PhotoButtons.vue'

const route = useRoute()
const router = useRouter()
const states = computed(() =>
  me.manager
    ? [{ value: 'Pending', label: 'Needs review' }, { value: 'Approved', label: 'Approved' }, { value: 'Done', label: 'Done' }, { value: 'Declined', label: 'Declined' }, { value: '', label: 'All' }]
    : [{ value: '', label: 'All' }, { value: 'Pending', label: 'Waiting' }, { value: 'Approved', label: 'In progress' }, { value: 'Done', label: 'Done' }],
)
const state = ref(me.manager ? 'Pending' : '')
const rows = ref([])
const pageLength = usePageLength()
const start = ref(0)
const total = ref(0)
const busy = ref(false)
const error = ref('')
const creating = ref(false)
const formError = ref('')
const form = reactive({ subject: '', description: '', asset: '', assetLabel: '', equipment: '', equipmentLabel: '', photo: null })
const detail = ref(null)
const detailError = ref('')
const declining = ref(null)
const reason = ref('')
const approving = ref(null)
const approvingOpen = computed({ get: () => !!approving.value, set: (v) => !v && (approving.value = null) })

async function load(from = 0) {
  busy.value = true
  error.value = ''
  try {
    let data = await api('projectit.work_requests.list_requests', { state: state.value, start: from, page_length: pageLength.value })
    if (!data.requests.length && from > 0) {
      // The last request on this page was just approved or declined: show the page before.
      data = await api('projectit.work_requests.list_requests', { state: state.value, start: Math.max(0, from - pageLength.value), page_length: pageLength.value })
    }
    rows.value = data.requests
    start.value = data.start
    total.value = data.total
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function openNew(asset = null, equipment = null) {
  Object.assign(form, { subject: '', description: '', asset: asset?.name || '', assetLabel: asset?.asset_name || '', equipment: equipment?.name || '', equipmentLabel: equipment?.label || '', photo: null })
  formError.value = ''
  creating.value = true
}

async function submit() {
  busy.value = true
  formError.value = ''
  try {
    const photo = form.photo?.content || null
    await api('projectit.work_requests.submit_request', { subject: form.subject, description: form.description, asset: form.equipment ? null : form.asset || null, equipment: form.equipment || null, photo })
    creating.value = false
    loadMe(true).catch(() => {})
    await load()
  } catch (e) {
    formError.value = e.message
  } finally {
    busy.value = false
  }
}

async function open(name) {
  detailError.value = ''
  try {
    detail.value = await api('projectit.work_requests.get_request', { name })
  } catch (e) {
    error.value = e.message
  }
}

function startDecline(request) {
  detail.value = null
  detailError.value = ''
  reason.value = ''
  declining.value = request
}

async function decline() {
  busy.value = true
  try {
    await api('projectit.work_requests.decline_request', { name: declining.value.name, reason: reason.value })
    declining.value = null
    loadMe(true).catch(() => {})
    await load(start.value)
  } catch (e) {
    detailError.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  load()
  if (route.query.open) open(String(route.query.open))
  if (route.query.new) openNew(route.query.asset ? { name: String(route.query.asset), asset_name: String(route.query.asset_name || route.query.asset) } : null, route.query.equipment ? { name: String(route.query.equipment), label: String(route.query.equipment_name || route.query.equipment) } : null)
})
</script>
