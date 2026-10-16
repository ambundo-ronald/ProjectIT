<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Root cause investigations" subtitle="Why a problem happened: causes under the 6Ms with their evidence, the 5 Whys, and the actions that close it.">
      <button class="btn btn-primary" :disabled="starting" @click="showNew = true"><FeatherIcon name="plus" class="h-4 w-4" /><span class="hidden sm:inline">New investigation</span><span class="sm:hidden">New</span></button>
    </PageHeader>

    <div class="relative">
      <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <input v-model="search" type="search" placeholder="Search problem, customer or site" aria-label="Search investigations" class="input pl-9" @input="debounced" />
    </div>
    <div class="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0" role="group" aria-label="Show">
      <button v-for="v in ['Open', 'Closed', 'All']" :key="v" class="chip" :aria-pressed="view === v" @click="view = v; load()">{{ v }}</button>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="busy && !rows.length" class="space-y-3"><div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" /></div>
    <ul v-else-if="rows.length" class="card divide-y divide-gray-100 overflow-hidden">
      <li v-for="r in paged" :key="r.name">
        <router-link :to="{ name: 'OpsInvestigation', params: { name: r.name } }" class="flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg" :class="r.status === 'Closed' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"><FeatherIcon name="crosshair" class="h-5 w-5" /></span>
          <span class="min-w-0 flex-1">
            <span class="block truncate font-semibold">{{ r.title }}</span>
            <span class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
              <span v-if="r.customer_name">{{ r.customer_name }}<template v-if="r.site"> · {{ r.site }}</template></span>
              <span v-if="r.machine" class="inline-flex items-center gap-1"><FeatherIcon name="droplet" class="h-3.5 w-3.5" />{{ r.machine }}</span>
              <span>{{ r.causes }} cause{{ r.causes === 1 ? '' : 's' }}</span>
              <span v-if="r.investigated_on">Investigated {{ formatDate(r.investigated_on) }}</span>
            </span>
          </span>
          <span class="flex shrink-0 flex-col items-end gap-1">
            <span class="rounded-md px-2 py-0.5 text-xs font-semibold" :class="r.status === 'Closed' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-800'">{{ r.status === 'Closed' ? 'Closed' : 'Open' }}</span>
            <span v-if="r.actions" class="text-[11px] tabular-nums text-gray-500">{{ r.actions_done }} of {{ r.actions }} actions done</span>
          </span>
        </router-link>
      </li>
    </ul>
    <EmptyState v-else-if="!busy && !error" icon="crosshair" :title="search ? 'No investigations match' : view === 'Open' ? 'No open investigations' : 'No investigations here'" text="Start one when a problem keeps coming back or needs a proper explanation for the customer. You can also start one from a job or a machine.">
      <button v-if="view === 'Open' && !search" class="btn btn-primary" @click="showNew = true"><FeatherIcon name="plus" class="h-4 w-4" />New investigation</button>
    </EmptyState>
    <Pager :total="total" :start="start" :page-length="pageLength" label="Investigation pages" @change="(s) => (start = s)" @update:page-length="(n) => (pageLength = n)" />

    <Modal v-model="showNew" title="New investigation" subtitle="What went wrong? You can add the causes and evidence next.">
      <form class="space-y-4" @submit.prevent="create">
        <div>
          <label class="label" for="inv-title">Problem <span class="text-red-500">*</span></label>
          <input id="inv-title" v-model="newTitle" required maxlength="140" class="input" placeholder="e.g. Excessive chlorine residual" />
        </div>
        <div>
          <label class="label">Machine <span class="font-normal text-gray-400">(optional)</span></label>
          <EquipmentPicker v-model="newEquipment" :label="newEquipmentLabel" @picked="(eq) => (newEquipmentLabel = eq ? `${eq.customer_name} · ${eq.equipment_name}` : '')" />
        </div>
        <p v-if="newError" role="alert" class="text-sm text-red-600">{{ newError }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn btn-secondary" @click="showNew = false">Cancel</button>
          <button class="btn btn-primary" :disabled="starting || !newTitle.trim()">{{ starting ? 'Starting…' : 'Start investigation' }}</button>
        </div>
      </form>
    </Modal>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import EquipmentPicker from '@/components/ops/EquipmentPicker.vue'
import Modal from '@/components/ops/Modal.vue'
import Pager from '@/components/ops/Pager.vue'
import { usePaged } from '@/data/paging'
import { api, formatDate } from '@/data/ops'

const router = useRouter()
const rows = ref([])
const view = ref('Open')
const search = ref('')
const busy = ref(false)
const error = ref('')
const { start, pageLength, total, paged } = usePaged(rows, [search, view])

async function load() {
  busy.value = true
  error.value = ''
  try {
    const r = await api('projectit.investigations.list_investigations', { status: view.value === 'All' ? null : view.value, search: search.value || null })
    rows.value = r.investigations
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
let timer = null
const debounced = () => {
  clearTimeout(timer)
  timer = setTimeout(load, 250)
}

const showNew = ref(false)
const newTitle = ref('')
const newEquipment = ref('')
const newEquipmentLabel = ref('')
const newError = ref('')
const starting = ref(false)
async function create() {
  starting.value = true
  newError.value = ''
  try {
    const r = await api('projectit.investigations.start', { title: newTitle.value, equipment: newEquipment.value || null })
    showNew.value = false
    router.push({ name: 'OpsInvestigation', params: { name: r.investigation.name } })
  } catch (e) {
    newError.value = e.message
  } finally {
    starting.value = false
  }
}
onMounted(load)
</script>
