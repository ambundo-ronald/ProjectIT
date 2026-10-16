<template>
  <div class="ops min-h-[100dvh] bg-gradient-to-b from-brand-50 to-gray-50 px-4 py-8">
    <div class="mx-auto w-full max-w-md">
      <div class="mb-5 flex items-center gap-3">
        <img src="/techy-app.svg" alt="" class="h-10 w-10 rounded-xl shadow-card" />
        <div>
          <h1 class="text-[20px] font-semibold tracking-tight">How did we do?</h1>
          <p class="text-sm text-gray-500">{{ info?.company ? `Rate your visit from ${info.company}.` : 'Rate your service visit.' }}</p>
        </div>
      </div>

      <div v-if="loading" class="card h-64 animate-pulse" aria-label="Loading" />

      <div v-else-if="error && !info" class="card p-6 text-center" role="alert">
        <span class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600"><FeatherIcon name="link" class="h-5 w-5" /></span>
        <p class="mt-3 font-semibold">This link doesn't work</p>
        <p class="mt-1 text-sm text-gray-500">{{ error }}</p>
      </div>

      <div v-else-if="thanks" class="card p-6 text-center" role="status">
        <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-50 text-green-600"><FeatherIcon name="check" class="h-7 w-7" /></span>
        <p class="mt-4 text-[18px] font-semibold">Thank you for your feedback</p>
        <p class="mt-1 text-sm text-gray-500">{{ stars >= 4 ? "We're glad the visit went well." : "We're sorry it wasn't better. We'll look into it." }}</p>
        <button v-if="info.open" class="btn btn-secondary mt-5" @click="thanks = false">Change my rating</button>
      </div>

      <form v-else class="card space-y-5 p-5" @submit.prevent="submit">
        <div class="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
          <p class="font-semibold">{{ info.subject }}</p>
          <p class="mt-0.5 text-gray-500">
            <template v-if="info.machine">{{ info.machine.equipment_name }}<template v-if="info.machine.site"> · {{ info.machine.site }}</template> · </template>{{ formatDate(info.completed) }}
          </p>
          <p v-if="info.technicians.length" class="mt-0.5 text-gray-500">By {{ info.technicians.join(' and ') }}</p>
        </div>
        <p v-if="!info.open" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">Ratings for this visit have closed.<template v-if="info.rating"> You rated it {{ info.rating }} out of 5. Thank you.</template></p>
        <template v-else>
          <fieldset>
            <legend class="label">Your rating <span class="text-red-500">*</span></legend>
            <div class="mt-1 flex justify-between gap-1" role="radiogroup" aria-label="Rating">
              <button v-for="n in 5" :key="n" type="button" role="radio" :aria-checked="stars === n" :aria-label="`${n} star${n === 1 ? '' : 's'}: ${LABELS[n]}`" class="flex flex-1 flex-col items-center gap-1 rounded-lg py-2 hover:bg-amber-50" @click="stars = n">
                <svg viewBox="0 0 24 24" class="h-10 w-10" :class="n <= stars ? 'fill-amber-400 stroke-amber-500' : 'fill-none stroke-gray-300'" stroke-width="1.5" aria-hidden="true"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z" stroke-linejoin="round" /></svg>
                <span class="text-[11px] text-gray-500">{{ LABELS[n] }}</span>
              </button>
            </div>
          </fieldset>
          <div>
            <label class="label" for="rate-comment">Anything you'd like to tell us? <span class="font-normal text-gray-400">(optional)</span></label>
            <textarea id="rate-comment" v-model="comment" rows="3" maxlength="1000" class="input" placeholder="What went well, or what we could do better" />
          </div>
          <p v-if="error" role="alert" class="text-sm text-red-600">{{ error }}</p>
          <button class="btn btn-primary btn-lg w-full" :disabled="!stars || sending">{{ sending ? 'Sending…' : info.rating ? 'Update my rating' : 'Send my rating' }}</button>
        </template>
      </form>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import { api, formatDate } from '@/data/ops'

const LABELS = { 1: 'Poor', 2: 'Fair', 3: 'Good', 4: 'Very good', 5: 'Excellent' }
const route = useRoute()
const info = ref(null)
const loading = ref(true)
const error = ref('')
const stars = ref(0)
const comment = ref('')
const sending = ref(false)
const thanks = ref(false)

onMounted(async () => {
  try {
    info.value = await api('projectit.ratings.info', { job: route.query.job || '', key: route.query.key || '' })
    stars.value = info.value.rating || 0
    comment.value = info.value.comment || ''
    thanks.value = !!info.value.rating && info.value.open
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
async function submit() {
  sending.value = true
  error.value = ''
  try {
    await api('projectit.ratings.submit', { job: route.query.job, key: route.query.key, rating: stars.value, comment: comment.value })
    info.value.rating = stars.value
    thanks.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}
</script>
