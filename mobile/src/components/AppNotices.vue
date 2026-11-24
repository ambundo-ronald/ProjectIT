<template>
  <!-- App-wide notices: the location and camera explanation before Android asks (phone app), the update bar (phone
       app), and "Open in the app" (Android browsers). -->
  <div class="ops contents">
    <!-- Prominent disclosure (data/disclosure.js) -->
    <Teleport to="body">
      <div v-if="disclosure.open && info" class="ops fixed inset-0 z-[80] flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-6">
        <div role="dialog" aria-modal="true" :aria-labelledby="`disc-${disclosure.kind}`" class="w-full max-w-md rounded-t-2xl bg-panel p-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] shadow-pop sm:rounded-2xl">
          <span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700"><FeatherIcon :name="info.icon" class="h-6 w-6" /></span>
          <h2 :id="`disc-${disclosure.kind}`" class="mt-4 text-[19px] font-semibold text-gray-900">{{ info.title }}</h2>
          <p class="mt-2 text-[15px] leading-relaxed text-gray-700">{{ info.text }}</p>
          <p class="mt-2 text-sm text-gray-500">{{ info.next }}</p>
          <p class="mt-3 text-sm"><a :href="privacyUrl" target="_blank" rel="noopener" class="link">Privacy policy</a></p>
          <div class="mt-5 flex gap-2">
            <button class="btn btn-secondary flex-1" @click="decline">Not now</button>
            <button class="btn btn-primary flex-1" @click="answer(true)">Continue</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- A newer app version (data/updates.js) -->
    <div v-if="update.state && !hideUpdate" class="fixed inset-x-3 z-[70] mx-auto flex max-w-md items-center gap-3 rounded-2xl bg-brand-800 px-4 py-3 text-white shadow-pop" :class="barPosition" role="status">
      <FeatherIcon :name="update.state === 'ready' ? 'refresh-cw' : 'download'" class="h-5 w-5 shrink-0 text-accent-400" />
      <span class="min-w-0 flex-1 text-sm">
        <template v-if="update.state === 'ready'">The update is ready. Restart to finish.</template>
        <template v-else-if="update.state === 'downloading'">Downloading the update{{ update.progress ? ` (${update.progress}%)` : '' }}…</template>
        <template v-else-if="update.required">This version is too old for your company's site. Update to carry on.</template>
        <template v-else>A new version of Techy App is available{{ update.version ? ` (${update.version})` : '' }}.</template>
      </span>
      <button v-if="update.state === 'ready'" class="btn btn-sm bg-accent-400 text-brand-900 hover:bg-accent-500" @click="finishUpdate">Restart</button>
      <button v-else-if="update.state === 'available'" class="btn btn-sm bg-accent-400 text-brand-900 hover:bg-accent-500" @click="startUpdate">Update</button>
      <button v-if="!update.required && update.state !== 'downloading'" class="rounded p-1 text-brand-200 hover:text-white" aria-label="Later" @click="hideUpdate = true"><FeatherIcon name="x" class="h-4 w-4" /></button>
    </div>

    <!-- Android browser: open this screen in the installed app (or get it from the Play Store) -->
    <div v-if="showOpenInApp" class="fixed inset-x-3 z-[70] mx-auto flex max-w-md items-center gap-3 rounded-2xl border border-gray-200 bg-panel px-3 py-2.5 shadow-pop" :class="barPosition" role="region" aria-label="Techy App for Android">
      <img :src="APP_ICON" alt="" class="h-9 w-9 shrink-0 rounded-xl" />
      <span class="min-w-0 flex-1 text-sm leading-tight"><span class="block font-semibold text-gray-900">Techy App</span><span class="block text-xs text-gray-500">Faster, and works without signal</span></span>
      <a :href="openLink" class="btn btn-primary btn-sm" @click="opened">Open in the app</a>
      <button class="rounded p-1 text-gray-400 hover:text-gray-700" aria-label="Not now" @click="dismiss"><FeatherIcon name="x" class="h-4 w-4" /></button>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import { disclosure, DISCLOSURES, answer } from '@/data/disclosure'
import { update, startUpdate, finishUpdate } from '@/data/updates'
import { isNative, apiBase } from '@/data/native'
import { intentLink } from '@/data/applinks'

const APP_ICON = `${import.meta.env.BASE_URL}techy-app.svg`
const route = useRoute()
const info = computed(() => DISCLOSURES[disclosure.kind])
const privacyUrl = computed(() => `${apiBase()}/techy-privacy`)
const hideUpdate = ref(false)
// Above the bottom tab bars on phones.
const barPosition = 'bottom-[calc(env(safe-area-inset-bottom)+5rem)] md:bottom-6'
function decline() {
  window.alert(info.value.refused)
  answer(false)
}

// "Open in the app": Android browsers only, when the company has the Android app, until the person says not now.
const DISMISSED = 'techy_open_in_app_dismissed'
const app = ref(null)
const dismissed = ref(false)
try {
  dismissed.value = Number(localStorage.getItem(DISMISSED) || 0) > Date.now()
} catch (e) {
  dismissed.value = false
}
const android = typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent)
const showOpenInApp = computed(() => !isNative && android && !dismissed.value && !!app.value && !['Rate', 'PublicRequest'].includes(route.name))
const openLink = computed(() => (app.value ? intentLink(route.fullPath, app.value.android_package, app.value.play_url) : '#'))
function dismiss() {
  dismissed.value = true
  try {
    localStorage.setItem(DISMISSED, String(Date.now() + 30 * 86400000)) // ask again in a month
  } catch (e) {
    /* hidden until the page reloads */
  }
}
const opened = () => setTimeout(dismiss, 1500)
onMounted(async () => {
  if (isNative || !android || dismissed.value) return
  try {
    const r = await fetch('/api/method/projectit.device_auth.hello', { headers: { Accept: 'application/json' } })
    const hello = (await r.json()).message
    if (hello?.android_app && hello.android_package) app.value = hello
  } catch (e) {
    /* offline: no bar */
  }
})
</script>
