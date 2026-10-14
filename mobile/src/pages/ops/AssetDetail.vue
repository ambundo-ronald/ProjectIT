<template>
  <section class="mx-auto max-w-6xl p-4 md:p-8">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsAssets' }" class="hover:text-gray-800">Assets</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">{{ data?.asset.asset_name || route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data && !error" class="h-40 animate-pulse rounded-xl bg-gray-200/70" />

    <div v-if="data" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div class="min-w-0 space-y-5">
        <div class="card flex flex-col gap-4 p-5 sm:flex-row">
          <div class="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 ring-1 ring-inset ring-gray-200">
            <img v-if="safeFile(asset.image)" :src="asset.image" alt="" class="h-full w-full object-cover" />
            <FeatherIcon v-else name="box" class="h-9 w-9 text-gray-400" />
          </div>
          <div class="min-w-0 flex-1">
            <h1 class="text-[20px] font-semibold tracking-tight md:text-[24px]">{{ asset.asset_name }}</h1>
            <p class="mt-0.5 font-mono text-xs text-gray-500">{{ asset.name }} · {{ asset.item_code }}</p>
            <div class="mt-3 flex flex-wrap gap-2 text-xs">
              <span v-if="asset.location" class="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-1 font-medium text-gray-700"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />{{ asset.location }}</span>
              <span v-if="asset.asset_category" class="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-1 font-medium text-gray-700"><FeatherIcon name="tag" class="h-3.5 w-3.5" />{{ asset.asset_category }}</span>
              <span class="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium" :class="openCount ? 'bg-amber-50 text-amber-800' : 'bg-green-50 text-green-700'"><FeatherIcon :name="openCount ? 'tool' : 'check-circle'" class="h-3.5 w-3.5" />{{ openCount ? `${openCount} open work order${openCount === 1 ? '' : 's'}` : 'No open work' }}</span>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button v-if="data.can_create" class="btn btn-primary btn-sm" @click="openNew(asset)"><FeatherIcon name="plus" class="h-4 w-4" />New work order</button>
              <router-link :to="{ name: 'OpsRequests', query: { new: 1, asset: asset.name, asset_name: asset.asset_name } }" class="btn btn-secondary btn-sm"><FeatherIcon name="alert-triangle" class="h-4 w-4" />Report a problem</router-link>
            </div>
          </div>
        </div>

        <MetersCard :meters="data.meters" :asset="asset.name" :manager="data.manager" @reload="reload" />

        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Preventive maintenance</h2><router-link :to="{ name: 'OpsPM' }" class="text-xs font-medium text-brand-600 hover:underline">Schedule</router-link></div>
          <ul v-if="data.plans.length" class="divide-y divide-gray-100">
            <li v-for="p in data.plans" :key="p.name" class="flex items-center gap-3 px-5 py-3">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600"><FeatherIcon name="repeat" class="h-4 w-4" /></span>
              <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ p.maintenance_task }}</span><span class="text-xs text-gray-500">{{ p.periodicity }} · {{ p.maintenance_type }}</span></span>
              <DueChip :date="p.next_due_date" />
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">No schedule yet. Create an Asset Maintenance record for this asset in ERPNext to plan recurring work.</p>
        </div>

        <div class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Work order history</h2><span class="text-xs text-gray-500">{{ data.work_orders.length }}</span></div>
          <ul v-if="data.work_orders.length" class="divide-y divide-gray-100">
            <li v-for="w in data.work_orders" :key="w.name">
              <router-link :to="{ name: 'OpsWorkOrder', params: { name: w.name } }" class="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
                <span class="min-w-0 flex-1"><span class="block truncate font-medium">{{ w.subject }}</span><span class="text-xs text-gray-500">{{ w.custom_work_category || 'Work order' }} · {{ fromNow(w.modified) }}</span></span>
                <StatusPill :status="w.status" />
              </router-link>
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">No work orders yet.</p>
        </div>

        <div v-if="data.requests.length" class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Requests</h2></div>
          <ul class="divide-y divide-gray-100">
            <li v-for="r in data.requests" :key="r.name"><router-link :to="{ name: 'OpsRequests', query: { open: r.name } }" class="flex items-center justify-between gap-3 px-5 py-3 hover:bg-gray-50"><span class="truncate font-medium">{{ r.subject }}</span><span class="text-xs text-gray-500">{{ r.status }}</span></router-link></li>
          </ul>
        </div>
      </div>

      <aside class="lg:sticky lg:top-8 lg:self-start">
        <div class="card p-5 text-center print:border-0 print:shadow-none" aria-label="QR label">
          <h2 class="section-label">QR label</h2>
          <div class="mx-auto mt-3 w-fit rounded-xl border border-gray-200 bg-white p-3">
            <img v-if="qr" :src="qr" :alt="`QR code for ${asset.asset_name}`" class="h-44 w-44" />
          </div>
          <p class="mt-3 font-semibold">{{ asset.asset_name }}</p>
          <p class="font-mono text-xs text-gray-500">{{ asset.name }}</p>
          <p class="mx-auto mt-3 max-w-[15rem] text-xs text-gray-500">{{ me.guest_requests ? 'Anyone who scans this can report a problem.' : 'Staff who scan this can report a problem after signing in.' }}</p>
          <div class="mt-4 grid grid-cols-2 gap-2 print:hidden">
            <button class="btn btn-secondary btn-sm" @click="print"><FeatherIcon name="printer" class="h-4 w-4" />Print</button>
            <button class="btn btn-secondary btn-sm" @click="copy"><FeatherIcon :name="copied ? 'check' : 'link'" class="h-4 w-4" />{{ copied ? 'Copied' : 'Copy link' }}</button>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>
<script setup>
import { ref, computed, inject, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import QRCode from 'qrcode'
import StatusPill from '@/components/ops/StatusPill.vue'
import MetersCard from '@/components/ops/MetersCard.vue'
import { api, me, dueIn, formatDate, fromNow, safeFile } from '@/data/ops'

const route = useRoute()
const openNew = inject('openNewWorkOrder')
const data = ref(null)
const error = ref('')
const qr = ref('')
const copied = ref(false)
const asset = computed(() => data.value.asset)
const openCount = computed(() => data.value.work_orders.filter((w) => !['Completed', 'Cancelled'].includes(w.status)).length)
const base = window.location.pathname.startsWith('/projectit') ? '/projectit' : '/techy-app'
const link = computed(() => `${window.location.origin}${base}/request?asset=${encodeURIComponent(route.params.name)}`)

const DueChip = (props) => {
  const d = dueIn(props.date)
  if (d === null) return h('span', { class: 'text-xs text-gray-400' }, 'Not scheduled')
  const [text, tone] = d < 0 ? [`${-d}d overdue`, 'bg-red-50 text-red-700'] : d === 0 ? ['Due today', 'bg-amber-50 text-amber-800'] : d <= 7 ? [`In ${d}d`, 'bg-amber-50 text-amber-800'] : [formatDate(props.date), 'bg-gray-100 text-gray-600']
  return h('span', { class: `whitespace-nowrap rounded-md px-2 py-1 text-xs font-semibold ${tone}` }, text)
}
DueChip.props = ['date']

function print() {
  const w = window.open('', '_blank', 'width=400,height=500')
  if (!w) return window.print()
  const doc = w.document
  doc.title = asset.value.asset_name
  const box = doc.body.appendChild(doc.createElement('div'))
  box.style.cssText = 'font-family:Inter,system-ui,sans-serif;text-align:center;padding:16px'
  const img = box.appendChild(doc.createElement('img'))
  img.src = qr.value
  img.style.cssText = 'width:240px;height:240px'
  const title = box.appendChild(doc.createElement('h2'))
  title.textContent = asset.value.asset_name
  title.style.cssText = 'margin:8px 0 2px'
  const code = box.appendChild(doc.createElement('p'))
  code.textContent = `${asset.value.name} · Scan to report a problem`
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

const reload = async () => {
  data.value = await api('projectit.maintenance.get_asset', { name: route.params.name })
}
onMounted(async () => {
  try {
    await reload()
    qr.value = await QRCode.toDataURL(link.value, { width: 480, margin: 1, color: { dark: '#0F2A4A' } })
  } catch (e) {
    error.value = e.message
  }
})
</script>
