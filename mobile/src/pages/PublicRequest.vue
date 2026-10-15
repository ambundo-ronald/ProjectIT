<template>
  <div class="ops min-h-[100dvh] bg-gradient-to-b from-brand-50 to-gray-50 px-4 py-8">
    <div class="mx-auto w-full max-w-md">
      <div class="mb-5 flex items-center gap-3">
        <img src="/techy-app.svg" alt="" class="h-10 w-10 rounded-xl shadow-card" />
        <div>
          <h1 class="text-[20px] font-semibold tracking-tight">Report a problem</h1>
          <p class="text-sm text-gray-500">The maintenance team will take a look.</p>
        </div>
      </div>

      <div v-if="loading" class="card h-64 animate-pulse" aria-label="Loading" />

      <div v-else-if="done" class="card p-6 text-center" role="status">
        <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-50 text-green-600"><FeatherIcon name="check" class="h-7 w-7" /></span>
        <p class="mt-4 text-[18px] font-semibold">Thanks, your request was sent</p>
        <p class="mt-1 text-sm text-gray-500">Reference <span class="font-mono font-medium text-gray-800">{{ done }}</span>. {{ guest ? "We'll email you about it." : 'You can follow it under Requests.' }}</p>
        <button class="btn btn-secondary mt-5" @click="reset">Report another problem</button>
      </div>

      <div v-else-if="!context.allowed" class="card p-6 text-center">
        <span class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600"><FeatherIcon name="lock" class="h-5 w-5" /></span>
        <p class="mt-3 font-semibold">Sign in to report a problem</p>
        <p class="mt-1 text-sm text-gray-500">Public reporting isn't enabled for this site.</p>
        <router-link :to="{ name: 'Login' }" class="btn btn-primary mt-5">Sign in</router-link>
      </div>

      <form v-else class="card space-y-4 p-5" @submit.prevent="submit">
        <div v-if="context.equipment" class="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600"><FeatherIcon name="droplet" class="h-5 w-5" /></span>
          <span class="min-w-0"><span class="block truncate font-semibold">{{ context.equipment.equipment_name }}</span><span class="block truncate text-xs text-gray-500">{{ context.equipment.site || context.equipment.name }}</span></span>
        </div>
        <div v-else-if="context.asset" class="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
          <span class="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-gray-500 ring-1 ring-gray-200"><FeatherIcon name="box" class="h-5 w-5" /></span>
          <span class="min-w-0"><span class="block truncate font-semibold">{{ context.asset.asset_name }}</span><span class="block font-mono text-xs text-gray-500">{{ context.asset.name }}</span></span>
        </div>
        <div>
          <label class="label" for="pr-subject">What's wrong? <span class="text-red-500">*</span></label>
          <input id="pr-subject" v-model="form.subject" required maxlength="140" class="input" placeholder="e.g. Making a loud grinding noise" />
        </div>
        <div>
          <label class="label" for="pr-details">Details</label>
          <textarea id="pr-details" v-model="form.description" rows="4" maxlength="3800" class="input" placeholder="When did you notice it? Is it safe to use?" />
        </div>
        <template v-if="guest">
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="label" for="pr-name">Your name</label>
              <input id="pr-name" v-model="form.full_name" maxlength="140" autocomplete="name" class="input" />
            </div>
            <div>
              <label class="label" for="pr-email">Email <span class="text-red-500">*</span></label>
              <input id="pr-email" v-model="form.email" type="email" required maxlength="140" autocomplete="email" class="input" />
            </div>
          </div>
          <p class="hint -mt-2">We only use your email to update you about this request.</p>
        </template>
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
        <button :disabled="busy" class="btn btn-primary btn-lg w-full">{{ busy ? 'Sending…' : 'Send request' }}</button>
      </form>
    </div>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import { api } from '@/data/ops'
import { session } from '@/data/session'

const route = useRoute()
const guest = !session.isLoggedIn
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const done = ref('')
const context = ref({ allowed: false, asset: null, equipment: null })
const form = reactive({ subject: '', description: '', full_name: '', email: '' })

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const asset = context.value.asset?.name || null
    const equipment = context.value.equipment?.name || null
    const result = guest
      ? await api('projectit.work_requests.submit_guest_request', { ...form, asset, equipment })
      : await api('projectit.work_requests.submit_request', { subject: form.subject, description: form.description, asset, equipment })
    done.value = result.name
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function reset() {
  Object.assign(form, { subject: '', description: '' })
  done.value = ''
}

onMounted(async () => {
  try {
    context.value = await api('projectit.work_requests.request_context', { asset: route.query.asset || null, equipment: route.query.equipment || null })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>
