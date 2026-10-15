<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <div class="min-w-0">
        <h2 class="card-title">Service report</h2>
        <p class="mt-0.5 truncate text-xs" :class="r.last_sent ? 'text-green-700' : 'text-gray-500'">
          <template v-if="r.last_sent">Emailed to {{ r.last_sent.recipients }} · {{ fromNow(r.last_sent.creation) }}</template>
          <template v-else-if="r.customer">Not sent to the customer yet</template>
          <template v-else>For your records</template>
        </p>
      </div>
      <a :href="pdfUrl" target="_blank" rel="noopener" class="btn btn-secondary btn-sm shrink-0"><FeatherIcon name="file-text" class="h-4 w-4" />Preview PDF</a>
    </div>
    <div class="space-y-3 p-5">
      <div>
        <label class="label" for="work-summary">Work done <span class="font-normal text-gray-400">(the customer reads this)</span></label>
        <textarea v-if="r.can_edit_summary" id="work-summary" v-model="summary" rows="3" maxlength="4000" class="input" placeholder="e.g. Replaced both pre-filters and flushed the membranes. Permeate TDS back to 17 ppm. Advised the caretaker to report any drop in flow." :disabled="saving" @blur="saveSummary" />
        <p v-else class="text-sm" :class="r.work_summary ? 'whitespace-pre-wrap text-gray-700' : 'italic text-gray-400'">{{ r.work_summary || 'Not written yet' }}</p>
        <p v-if="savedNote" class="mt-1 text-xs text-green-700" role="status">{{ savedNote }}</p>
      </div>
      <div v-if="r.customer" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3">
        <p v-if="!r.emails.length && r.can_email" class="text-xs text-amber-700">The customer has no email address. Add one in ERPNext to email reports.</p>
        <p v-else-if="!summary.trim()" class="text-xs text-amber-700">Write what you did before sending.</p>
        <span v-else />
        <button v-if="r.can_email" class="btn btn-primary btn-sm" :disabled="!r.emails.length && !r.can_add_recipients" @click="openSend"><FeatherIcon name="send" class="h-4 w-4" />Email to customer</button>
      </div>
    </div>

    <Modal v-model="sending" title="Email service report" :subtitle="`The PDF goes to the customer and is logged on ${workOrder}.`">
      <form id="send-report" class="space-y-4" @submit.prevent="send">
        <fieldset>
          <legend class="label">Send to</legend>
          <label v-for="e in r.emails" :key="e" class="flex items-center gap-2 py-1 text-sm"><input v-model="chosen" type="checkbox" :value="e" class="rounded border-gray-300 text-brand-600" />{{ e }}</label>
          <p v-if="!r.emails.length" class="text-sm text-gray-500">No addresses on file for this customer.</p>
        </fieldset>
        <div v-if="r.can_add_recipients">
          <label class="label" for="report-extra">Other addresses <span class="font-normal text-gray-400">(comma separated)</span></label>
          <input id="report-extra" v-model="extra" type="text" inputmode="email" class="input" placeholder="owner@example.com" />
        </div>
        <div>
          <label class="label" for="report-message">Message <span class="font-normal text-gray-400">(optional)</span></label>
          <textarea id="report-message" v-model="message" rows="3" maxlength="2000" class="input" placeholder="A short note; a polite default is used if left empty." />
        </div>
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
      </form>
      <template #footer>
        <button class="btn btn-secondary" @click="sending = false">Cancel</button>
        <button class="btn btn-primary" form="send-report" :disabled="busy || !recipients.length"><FeatherIcon name="send" class="h-4 w-4" />{{ busy ? 'Sending…' : `Send to ${recipients.length}` }}</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, watch } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import { api, fromNow } from '@/data/ops'

const props = defineProps({ report: { type: Object, required: true }, workOrder: { type: String, required: true } })
const emit = defineEmits(['updated', 'error'])
const r = computed(() => props.report)
const summary = ref(props.report.work_summary || '')
watch(() => props.report.work_summary, (v) => !saving.value && (summary.value = v || ''))
const saving = ref(false)
const savedNote = ref('')
const sending = ref(false)
const busy = ref(false)
const error = ref('')
const chosen = ref([])
const extra = ref('')
const message = ref('')
const pdfUrl = computed(() => `/api/method/projectit.service_report.download?name=${encodeURIComponent(props.workOrder)}`)
const recipients = computed(() => [...new Set([...chosen.value, ...extra.value.split(',').map((e) => e.trim().toLowerCase()).filter(Boolean)])])

async function saveSummary() {
  if ((summary.value || '') === (r.value.work_summary || '')) return
  saving.value = true
  savedNote.value = ''
  try {
    emit('updated', await api('projectit.service_report.set_summary', { name: props.workOrder, summary: summary.value }))
    savedNote.value = 'Saved'
    setTimeout(() => (savedNote.value = ''), 2000)
  } catch (e) {
    emit('error', e.message)
  } finally {
    saving.value = false
  }
}
function openSend() {
  chosen.value = r.value.emails.slice(0, 1)
  extra.value = ''
  message.value = ''
  error.value = ''
  sending.value = true
}
async function send() {
  busy.value = true
  error.value = ''
  try {
    await saveSummary()
    emit('updated', await api('projectit.service_report.email_report', { name: props.workOrder, recipients: recipients.value, message: message.value }))
    sending.value = false
    toast({ title: 'Service report sent', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
