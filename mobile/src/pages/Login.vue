<template>
  <div class="ops flex min-h-[100dvh] items-center justify-center bg-gradient-to-b from-brand-50 to-gray-50 p-4">
    <InstallationPrompt v-if="!isNative" />
    <div class="w-full max-w-sm">
      <div class="mb-6 flex flex-col items-center text-center">
        <img :src="isNative && server.logo ? server.logo : '/techy-app.svg'" alt="" class="h-14 w-14 rounded-2xl bg-panel object-contain shadow-card" @error="(e) => (e.target.src = '/techy-app.svg')" />
        <h1 class="mt-4 text-[24px] font-semibold tracking-tight">{{ isNative && server.url ? `Sign in to ${server.company}` : 'Sign in to Techy App' }}</h1>
        <p class="mt-1 text-sm text-gray-500">Work orders, field work and your team, in one place.</p>
      </div>

      <!-- Phone app, first time: which company's Techy site -->
      <form v-if="isNative && !server.url" class="card space-y-4 p-6" @submit.prevent="pickServer">
        <div>
          <label class="label" for="login-server">Your company's Techy address</label>
          <input id="login-server" v-model="address" required type="url" inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false" autocomplete="url" class="input" placeholder="ops.yourcompany.com" @input="error = ''" />
          <p class="hint">Your manager can give you this. You only enter it once.</p>
        </div>
        <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"><FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" />{{ error }}</p>
        <button class="btn btn-primary w-full" :disabled="busy">{{ busy ? 'Checking…' : 'Continue' }}</button>
      </form>

      <form v-else class="card space-y-4 p-6" @submit.prevent="submit">
        <div>
          <label class="label" for="login-email">Email or user ID</label>
          <input id="login-email" required name="email" type="text" autocomplete="username" autocapitalize="off" class="input" placeholder="you@company.com" @input="clearError" />
        </div>
        <div>
          <label class="label" for="login-password">Password</label>
          <input id="login-password" required name="password" type="password" autocomplete="current-password" class="input" placeholder="••••••••" @input="clearError" />
        </div>
        <p v-if="message" role="alert" class="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"><FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" />{{ message }}</p>
        <button class="btn btn-primary w-full" :disabled="session.login.loading">{{ session.login.loading ? 'Signing in…' : 'Sign in' }}</button>
        <p v-if="isNative" class="text-center text-xs text-gray-500">
          {{ server.url.replace(/^https?:\/\//, '') }} ·
          <button type="button" class="font-medium text-brand-600 hover:underline" @click="changeServer">Change company</button>
        </p>
      </form>
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { session, showAuthenticationError } from '../data/session'
import { isNative, server, chooseServer, forgetServer } from '../data/native'
import InstallationPrompt from './InstallationPrompt.vue'

const address = ref('')
const error = ref('')
const busy = ref(false)

const clearError = () => {
  showAuthenticationError.value = false
  session.login.reset?.()
}
// In the phone app the site's own words (locked out, two-factor, unreachable); in a browser the usual message.
const message = computed(() => {
  if (isNative && session.login.error) return session.login.error.message || 'Could not sign in.'
  return showAuthenticationError.value ? 'Incorrect email or password.' : ''
})

async function pickServer() {
  busy.value = true
  error.value = ''
  try {
    await chooseServer(address.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function changeServer() {
  address.value = server.url.replace(/^https?:\/\//, '')
  forgetServer()
  clearError()
}

function submit(e) {
  const formData = new FormData(e.target)
  session.login.submit({ email: formData.get('email'), password: formData.get('password') })
}
</script>
