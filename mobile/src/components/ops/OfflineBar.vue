<template>
  <div v-if="!offline.online || offline.pending || offline.failed.length" class="border-b px-4 py-2 text-sm md:px-8" :class="tone" role="status">
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
      <FeatherIcon :name="!offline.online ? 'wifi-off' : offline.failed.length ? 'alert-triangle' : 'refresh-cw'" class="h-4 w-4 shrink-0" :class="offline.syncing ? 'animate-spin' : ''" />
      <span class="min-w-0 flex-1">
        <template v-if="!offline.online">
          <span class="font-semibold">You're offline.</span> Showing what's saved on this phone.
          <template v-if="offline.pending"> {{ offline.pending }} change{{ offline.pending === 1 ? '' : 's' }} will be sent when you're back online.</template>
        </template>
        <template v-else-if="offline.syncing">Sending {{ offline.pending }} change{{ offline.pending === 1 ? '' : 's' }} made offline…</template>
        <template v-else-if="offline.pending">{{ offline.pending }} change{{ offline.pending === 1 ? '' : 's' }} waiting to be sent.</template>
        <template v-if="offline.failed.length">
          <span :class="!offline.online || offline.pending ? 'ml-1' : ''">{{ offline.failed.length }} change{{ offline.failed.length === 1 ? '' : 's' }} could not be saved.</span>
        </template>
      </span>
      <button v-if="offline.online && offline.pending && !offline.syncing" class="font-semibold underline" @click="sync">Send now</button>
      <button v-if="offline.pending || offline.failed.length" class="font-semibold underline" @click="show">{{ offline.failed.length ? 'Review' : 'See what' }}</button>
    </div>

    <Modal v-model="open" title="Waiting to send" subtitle="Changes made on this phone without signal. They are sent in order as soon as you are online.">
      <p v-if="!items.length" class="py-3 text-sm text-gray-500">Everything has been sent.</p>
      <ul class="divide-y divide-gray-100">
        <li v-for="item in items" :key="item.id" class="py-3">
          <p class="flex items-center gap-2 text-sm font-medium text-gray-900">
            <FeatherIcon :name="item.failed ? 'alert-triangle' : 'clock'" class="h-4 w-4 shrink-0" :class="item.failed ? 'text-red-600' : 'text-amber-600'" />
            <span>{{ item.label }}<template v-if="item.job"> · <router-link :to="{ name: 'OpsWorkOrder', params: { name: item.job } }" class="text-brand-600 hover:underline" @click="open = false">{{ item.job }}</router-link></template></span>
          </p>
          <p v-if="item.failed" class="mt-0.5 text-sm text-red-700">{{ item.error }}</p>
          <p class="text-xs text-gray-500">Made {{ fromNow(new Date(item.created).toISOString()) }}{{ item.failed ? '' : ' · waiting' }}</p>
          <div v-if="item.failed" class="mt-2 flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="act(retry, item)">Try again</button>
            <button class="btn btn-ghost btn-sm text-gray-600" @click="act(discard, item)">Discard</button>
          </div>
        </li>
      </ul>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, watch } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import { fromNow } from '@/data/ops'
import { offline, sync, retry, discard, outbox } from '@/data/offline'

const open = ref(false)
const items = ref([])
const refresh = async () => (items.value = await outbox())
async function show() {
  await refresh()
  open.value = true
}
async function act(fn, item) {
  await fn(item)
  await refresh()
}
// Keep the open list current while things are being sent.
watch(() => [offline.pending, offline.failed.length], () => open.value && refresh())
const tone = computed(() => (!offline.online ? 'border-amber-200 bg-amber-50 text-amber-900' : offline.failed.length ? 'border-red-200 bg-red-50 text-red-800' : 'border-brand-100 bg-brand-50 text-brand-900'))
</script>
