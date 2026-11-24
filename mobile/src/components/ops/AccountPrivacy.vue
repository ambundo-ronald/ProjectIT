<template>
  <!-- The privacy policy, and asking for one's account to be deleted (Google Play requires both in the app). -->
  <div :class="compact ? 'contents' : 'card p-5'">
    <h2 v-if="!compact" class="section-label">Privacy</h2>
    <div :class="compact ? 'contents' : 'mt-2 flex flex-wrap gap-2'">
      <a :href="`${base}/techy-privacy`" target="_blank" rel="noopener" :class="compact ? 'menu-item' : 'btn btn-secondary btn-sm'" role="menuitem"><FeatherIcon name="shield" class="h-4 w-4" :class="compact ? 'text-gray-500' : ''" />Privacy policy</a>
      <button :class="compact ? 'menu-item text-red-600' : 'btn btn-ghost btn-sm text-red-600'" role="menuitem" @click="open = true"><FeatherIcon name="user-x" class="h-4 w-4" />Delete my account</button>
    </div>
    <Modal v-model="open" title="Delete my account" subtitle="Your account belongs to your company. We send them your request.">
      <div v-if="!sent" class="space-y-3 text-sm text-gray-700">
        <p>Your company switches your account off and deletes your personal details (name, contact details, photos of you, your locations) within 30 days. Records it must keep by law, such as invoices, attendance and work done on a customer's machine, are kept without your contact details where possible.</p>
        <label class="label" for="del-reason">Anything you want them to know <span class="font-normal text-gray-400">(optional)</span></label>
        <textarea id="del-reason" v-model="reason" rows="3" maxlength="1000" class="input" />
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-red-700">{{ error }}</p>
      </div>
      <p v-else class="rounded-lg bg-green-50 p-3 text-sm text-green-900" role="status">Your request was sent. Your company will confirm it with you and delete your account within 30 days.</p>
      <template #footer>
        <button class="btn btn-secondary" @click="open = false">{{ sent ? 'Close' : 'Cancel' }}</button>
        <button v-if="!sent" class="btn bg-red-600 text-white hover:bg-red-700" :disabled="busy" @click="send">Ask to delete my account</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import { api } from '@/data/ops'
import { apiBase } from '@/data/native'

defineProps({ compact: Boolean }) // compact: rows for a dropdown menu
const base = apiBase()
const open = ref(false)
const reason = ref('')
const busy = ref(false)
const sent = ref(false)
const error = ref('')
async function send() {
  busy.value = true
  error.value = ''
  try {
    await api('projectit.app_links.request_deletion', { reason: reason.value })
    sent.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
