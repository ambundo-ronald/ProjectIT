<template>
  <div class="space-y-4">
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!data && !error" class="space-y-3" aria-busy="true">
      <div class="h-28 animate-pulse rounded-2xl bg-gray-200/70" />
      <div class="h-56 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <template v-if="data">
      <ContractorStatement :data="data" :can-query="!data.manager" @query="openQuery" />
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2 text-sm">
          <label for="pay-period" class="text-gray-600">Paid in the last</label>
          <select id="pay-period" v-model.number="days" class="input !w-auto" @change="load">
            <option :value="30">30 days</option>
            <option :value="90">90 days</option>
            <option :value="365">year</option>
          </select>
        </div>
        <a :href="pdfPath" target="_blank" rel="noopener" class="btn btn-secondary btn-sm"><FeatherIcon name="download" class="h-4 w-4" />Statement (PDF)</a>
      </div>
      <p class="text-xs text-gray-500">Approved lines are paid in the next payout on your usual pay cycle ({{ data.contractor.pay_cycle?.toLowerCase() }}). Something not right? Press Query on the line and tell us.</p>
    </template>

    <Modal v-model="querying" title="Query this line" :subtitle="line?.description">
      <label class="label" for="query-note">What is not right?</label>
      <textarea id="query-note" v-model="note" rows="4" maxlength="1000" class="input" placeholder="e.g. We were on site 4 hours, not 3" />
      <template #footer>
        <button class="btn btn-secondary" @click="querying = false">Cancel</button>
        <button class="btn btn-primary" :disabled="!note.trim() || busy" @click="sendQuery">Send</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import ContractorStatement from '@/components/ops/ContractorStatement.vue'
import { api } from '@/data/ops'

const data = ref(null)
const error = ref('')
const days = ref(90)
const querying = ref(false)
const line = ref(null)
const note = ref('')
const busy = ref(false)
const range = () => {
  const end = new Date()
  const start = new Date(Date.now() - (days.value - 1) * 86400000)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

async function load() {
  try {
    data.value = await api('projectit.contractor_pay.statement', range())
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}
function openQuery(l) {
  line.value = l
  note.value = ''
  querying.value = true
}
async function sendQuery() {
  busy.value = true
  try {
    await api('projectit.contractor_pay.query_line', { line: line.value.name, note: note.value })
    querying.value = false
    toast({ title: 'Sent. We will look at it and answer.', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    load()
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  } finally {
    busy.value = false
  }
}
// A plain link: the phone app opens it in the browser, signed (data/native.js).
const pdfPath = computed(() => {
  const { start, end } = range()
  return `/api/method/projectit.contractor_pay.download_statement?start=${start}&end=${end}`
})
onMounted(load)
</script>
