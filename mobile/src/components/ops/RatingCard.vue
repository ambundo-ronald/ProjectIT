<template>
  <div class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <h2 class="card-title">Customer rating</h2>
      <button v-if="rating.can_share" class="btn btn-secondary btn-sm" :disabled="busy" @click="copy"><FeatherIcon :name="copied ? 'check' : 'link'" class="h-4 w-4" />{{ copied ? 'Link copied' : 'Copy rating link' }}</button>
    </div>
    <div class="px-5 py-4 text-sm">
      <template v-if="rating.rating">
        <p class="flex items-center gap-2">
          <span class="text-lg tracking-wider text-amber-400" :aria-label="`${rating.rating} out of 5 stars`">{{ '★'.repeat(rating.rating) }}<span class="text-gray-300">{{ '★'.repeat(5 - rating.rating) }}</span></span>
          <span class="font-semibold">{{ rating.rating }}/5</span>
          <span class="text-xs text-gray-500">{{ formatDate(rating.rated_on) }}</span>
        </p>
        <p v-if="rating.comment" class="mt-1.5 whitespace-pre-wrap text-gray-700">“{{ rating.comment }}”</p>
      </template>
      <p v-else-if="!rating.completed" class="text-gray-500">Once the job is completed, the customer can rate the visit from a link in the service report email.</p>
      <p v-else-if="rating.can_share" class="text-gray-500">Not rated yet. The link goes out with the service report email. You can also copy it and send it by WhatsApp or SMS.</p>
      <p v-else class="text-gray-500">Not rated. Ratings close 30 days after completion.</p>
      <p v-if="error" role="alert" class="mt-2 text-red-600">{{ error }}</p>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { api, formatDate } from '@/data/ops'

const props = defineProps({ rating: Object, workOrder: String })
const busy = ref(false)
const copied = ref(false)
const error = ref('')
async function copy() {
  busy.value = true
  error.value = ''
  try {
    const { link } = await api('projectit.ratings.share_link', { name: props.workOrder })
    try {
      await navigator.clipboard.writeText(link)
    } catch (e) {
      window.prompt('Copy the rating link', link)
    }
    copied.value = true
    setTimeout(() => (copied.value = false), 2500)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
