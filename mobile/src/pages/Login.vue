<template>
  <div class="ops flex min-h-[100dvh] items-center justify-center bg-gradient-to-b from-brand-50 to-gray-50 p-4">
    <InstallationPrompt />
    <div class="w-full max-w-sm">
      <div class="mb-6 flex flex-col items-center text-center">
        <img src="/techy-app.svg" alt="" class="h-14 w-14 rounded-2xl shadow-card" />
        <h1 class="mt-4 text-[24px] font-semibold tracking-tight">Sign in to Techy App</h1>
        <p class="mt-1 text-sm text-gray-500">Work orders, field work and your team, in one place.</p>
      </div>
      <form class="card space-y-4 p-6" @submit.prevent="submit">
        <div>
          <label class="label" for="login-email">Email or user ID</label>
          <input id="login-email" required name="email" type="text" autocomplete="username" class="input" placeholder="you@company.com" @input="clearError" />
        </div>
        <div>
          <label class="label" for="login-password">Password</label>
          <input id="login-password" required name="password" type="password" autocomplete="current-password" class="input" placeholder="••••••••" @input="clearError" />
        </div>
        <p v-if="showAuthenticationError" role="alert" class="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"><FeatherIcon name="alert-circle" class="h-4 w-4" />Incorrect email or password.</p>
        <button class="btn btn-primary w-full" :disabled="session.login.loading">{{ session.login.loading ? 'Signing in…' : 'Sign in' }}</button>
      </form>
    </div>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
import { session, showAuthenticationError } from '../data/session'
import InstallationPrompt from './InstallationPrompt.vue'

const clearError = () => (showAuthenticationError.value = false)

function submit(e) {
  const formData = new FormData(e.target)
  session.login.submit({ email: formData.get('email'), password: formData.get('password') })
}
</script>
