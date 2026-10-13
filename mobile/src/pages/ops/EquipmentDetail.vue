<template>
  <section class="mx-auto max-w-6xl p-4 md:p-8">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsEquipment' }" class="hover:text-gray-800">Customer equipment</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">{{ eq ? `${eq.customer_name} · ${eq.equipment_name}` : route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data && !error" class="h-40 animate-pulse rounded-xl bg-gray-200/70" />

    <div v-if="data" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div class="min-w-0 space-y-5">
        <!-- Header -->
        <div class="card p-5">
          <div class="flex items-start gap-4">
            <span class="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600"><FeatherIcon name="droplet" class="h-7 w-7" /></span>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium uppercase tracking-wide text-gray-500">{{ eq.customer_name }}</p>
              <h1 class="text-[20px] font-semibold leading-snug tracking-tight md:text-[24px]">{{ eq.equipment_name }}</h1>
              <p class="mt-0.5 font-mono text-xs text-gray-500">{{ eq.name }}<template v-if="eq.tag"> · Tag {{ eq.tag }}</template><template v-if="eq.serial_no"> · S/N {{ eq.serial_no }}</template></p>
            </div>
          </div>
          <div class="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span class="rounded-md px-2 py-1 font-semibold" :class="EQUIPMENT_STATUS[eq.status]">{{ eq.status }}</span>
            <CoverageBadge :kind="data.coverage.kind" :until="data.coverage.until" />
            <CoverageBadge v-if="data.coverage.contract" kind="Contract" :until="data.coverage.contract" />
            <span v-if="openCount" class="rounded-md bg-amber-50 px-2 py-1 font-semibold text-amber-800">{{ openCount }} open job{{ openCount === 1 ? '' : 's' }}</span>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <button v-if="data.can_create && !retired" class="btn btn-primary btn-sm" @click="openNew({ equipment: eq })"><FeatherIcon name="plus" class="h-4 w-4" />New job</button>
            <router-link v-if="!retired" :to="{ name: 'OpsRequests', query: { new: 1, equipment: eq.name, equipment_name: `${eq.customer_name} · ${eq.equipment_name}` } }" class="btn btn-secondary btn-sm"><FeatherIcon name="alert-triangle" class="h-4 w-4" />Report a problem</router-link>
            <button v-if="data.manager" class="btn btn-ghost btn-sm" @click="editing = true"><FeatherIcon name="edit-2" class="h-4 w-4" />Edit</button>
          </div>
        </div>

        <!-- Site and contact -->
        <div class="card grid gap-5 p-5 sm:grid-cols-2">
          <div>
            <h2 class="section-label">Site</h2>
            <template v-if="data.address">
              <p class="mt-2 font-medium">{{ data.address.address_title || eq.site }}</p>
              <p v-for="l in data.address.lines" :key="l" class="text-sm text-gray-600">{{ l }}</p>
              <a v-if="mapLink(data.address)" :href="mapLink(data.address)" target="_blank" rel="noopener" class="link mt-2 inline-flex items-center gap-1 text-sm"><FeatherIcon name="navigation" class="h-3.5 w-3.5" />Directions</a>
            </template>
            <p v-else class="mt-2 text-sm text-gray-500">No site address recorded.</p>
          </div>
          <div>
            <h2 class="section-label">Customer contact</h2>
            <p class="mt-2 font-medium">{{ data.contact.name || eq.customer_name }}</p>
            <a v-if="data.contact.phone || data.address?.phone" :href="`tel:${data.contact.phone || data.address.phone}`" class="mt-1 flex items-center gap-2 text-sm text-brand-700 hover:underline"><FeatherIcon name="phone" class="h-3.5 w-3.5" />{{ data.contact.phone || data.address.phone }}</a>
            <a v-if="data.contact.email" :href="`mailto:${data.contact.email}`" class="mt-1 flex items-center gap-2 text-sm text-brand-700 hover:underline"><FeatherIcon name="mail" class="h-3.5 w-3.5" />{{ data.contact.email }}</a>
            <p v-if="!data.contact.phone && !data.contact.email && !data.address?.phone" class="mt-1 text-sm text-gray-500">No phone or email on the customer.</p>
          </div>
        </div>

        <!-- Jobs -->
        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Job history</h2><span class="text-xs text-gray-500">{{ data.work_orders.length }}</span></div>
          <ul v-if="data.work_orders.length" class="divide-y divide-gray-100">
            <li v-for="w in data.work_orders" :key="w.name">
              <router-link :to="{ name: 'OpsWorkOrder', params: { name: w.name } }" class="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
                <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" :class="w.custom_work_category === 'Installation' ? 'bg-violet-50 text-violet-700' : 'bg-gray-100 text-gray-500'"><FeatherIcon :name="w.custom_work_category === 'Installation' ? 'truck' : 'tool'" class="h-4 w-4" /></span>
                <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ w.subject }}</span><span class="text-xs text-gray-500">{{ w.custom_work_category || 'Job' }} · {{ fromNow(w.modified) }}</span></span>
                <StatusPill :status="w.status" />
              </router-link>
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">No jobs yet.</p>
        </div>

        <div v-if="data.requests.length" class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Requests</h2></div>
          <ul class="divide-y divide-gray-100">
            <li v-for="r in data.requests" :key="r.name"><router-link :to="{ name: 'OpsRequests', query: { open: r.name } }" class="flex items-center justify-between gap-3 px-5 py-3 hover:bg-gray-50"><span class="truncate font-medium">{{ r.subject }}</span><span class="text-xs text-gray-500">{{ r.status }}</span></router-link></li>
          </ul>
        </div>

        <div v-if="eq.notes" class="card p-5">
          <h2 class="section-label">Notes</h2>
          <p class="mt-2 whitespace-pre-wrap text-sm text-gray-800">{{ eq.notes }}</p>
        </div>
      </div>

      <aside class="space-y-4 lg:sticky lg:top-8 lg:self-start">
        <div class="card text-sm">
          <dl class="space-y-3 p-4">
            <div v-for="row in details" :key="row.label" class="flex justify-between gap-3">
              <dt class="text-gray-500">{{ row.label }}</dt>
              <dd class="min-w-0 truncate text-right">
                <LinkChip v-if="row.kind" :kind="row.kind" :name="row.value" />
                <a v-else-if="row.desk" :href="row.desk" target="_blank" rel="noopener" class="link">{{ row.value }}</a>
                <template v-else>{{ row.value }}</template>
              </dd>
            </div>
          </dl>
        </div>

        <div class="card p-5 text-center" aria-label="QR label">
          <h2 class="section-label">QR sticker</h2>
          <div class="mx-auto mt-3 w-fit rounded-xl border border-gray-200 bg-white p-3">
            <img v-if="qr" :src="qr" :alt="`QR code for ${eq.equipment_name}`" class="h-40 w-40" />
          </div>
          <p class="mt-3 font-semibold">{{ eq.equipment_name }}</p>
          <p class="font-mono text-xs text-gray-500">{{ eq.tag || eq.name }}</p>
          <p class="mx-auto mt-3 max-w-[15rem] text-xs text-gray-500">{{ me.guest_requests ? 'The customer can scan this to report a problem with this machine.' : 'Staff who scan this can report a problem after signing in. Turn on public requests to let customers use it.' }}</p>
          <div class="mt-4 grid grid-cols-2 gap-2">
            <button class="btn btn-secondary btn-sm" @click="print"><FeatherIcon name="printer" class="h-4 w-4" />Print</button>
            <button class="btn btn-secondary btn-sm" @click="copy"><FeatherIcon :name="copied ? 'check' : 'link'" class="h-4 w-4" />{{ copied ? 'Copied' : 'Copy link' }}</button>
          </div>
        </div>
      </aside>
    </div>
    <EquipmentForm v-model="editing" :equipment="eq" @saved="(r) => (data = r)" />
  </section>
</template>
<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import QRCode from 'qrcode'
import StatusPill from '@/components/ops/StatusPill.vue'
import CoverageBadge from '@/components/ops/CoverageBadge.vue'
import LinkChip from '@/components/ops/LinkChip.vue'
import EquipmentForm from '@/components/ops/EquipmentForm.vue'
import { api, me, formatDate, fromNow } from '@/data/ops'
import { EQUIPMENT_STATUS, mapLink } from '@/data/equipment'

const route = useRoute()
const openNew = inject('openNewWorkOrder')
const data = ref(null)
const error = ref('')
const editing = ref(false)
const qr = ref('')
const copied = ref(false)
const eq = computed(() => data.value?.equipment)
const retired = computed(() => ['Decommissioned', 'Cancelled'].includes(eq.value?.status))
const openCount = computed(() => data.value.work_orders.filter((w) => !['Completed', 'Cancelled'].includes(w.status)).length)
const base = window.location.pathname.startsWith('/projectit') ? '/projectit' : '/techy-app'
const link = computed(() => `${window.location.origin}${base}/request?equipment=${encodeURIComponent(route.params.name)}`)
const details = computed(() => {
  const e = eq.value
  const rows = [
    { label: 'Delivered', value: e.delivered_on && formatDate(e.delivered_on) },
    { label: 'Delivery note', value: e.delivery_note, desk: e.delivery_note && `/desk/delivery-note/${encodeURIComponent(e.delivery_note)}` },
    { label: 'Installed', value: e.installed_on ? formatDate(e.installed_on) : e.status === 'Awaiting installation' ? 'Not yet' : null },
    { label: 'Installation note', value: e.installation_note, desk: e.installation_note && `/desk/installation-note/${encodeURIComponent(e.installation_note)}` },
    { label: 'Warranty until', value: e.warranty_until ? formatDate(e.warranty_until) : '—' },
    { label: 'Contract until', value: e.contract_until ? formatDate(e.contract_until) : '—' },
    { label: 'Project', value: e.project, kind: e.project && 'project' },
    { label: 'Item', value: e.item_code },
  ]
  return rows.filter((r) => r.value)
})

function print() {
  const w = window.open('', '_blank', 'width=400,height=520')
  if (!w) return window.print()
  const doc = w.document
  doc.title = eq.value.equipment_name
  const box = doc.body.appendChild(doc.createElement('div'))
  box.style.cssText = 'font-family:Inter,system-ui,sans-serif;text-align:center;padding:16px'
  const img = box.appendChild(doc.createElement('img'))
  img.src = qr.value
  img.style.cssText = 'width:240px;height:240px'
  const title = box.appendChild(doc.createElement('h2'))
  title.textContent = eq.value.equipment_name
  title.style.cssText = 'margin:8px 0 2px'
  const code = box.appendChild(doc.createElement('p'))
  code.textContent = `${eq.value.tag || eq.value.name} · Scan to request service`
  code.style.cssText = 'margin:0;color:#555;font-size:13px'
  img.onload = () => w.print()
}

async function copy() {
  try {
    await navigator.clipboard.writeText(link.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch (e) {
    window.prompt('Copy this link', link.value)
  }
}

onMounted(async () => {
  try {
    data.value = await api('projectit.equipment.get_equipment', { name: route.params.name })
    qr.value = await QRCode.toDataURL(link.value, { width: 480, margin: 1, color: { dark: '#0F2A4A' } })
  } catch (e) {
    error.value = e.message
  }
})
</script>
