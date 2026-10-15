<template>
  <div class="fixed inset-0 z-[60] flex flex-col bg-black text-white" role="dialog" aria-modal="true" :aria-label="title">
    <header class="flex items-center justify-between px-4 pb-2 pt-[max(env(safe-area-inset-top),1rem)]">
      <button class="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 hover:bg-white/20" aria-label="Close camera" @click="close">
        <FeatherIcon name="x" class="h-5 w-5" />
      </button>
      <p class="text-[15px] font-semibold">{{ title }}</p>
      <span class="w-10" />
    </header>

    <div class="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden">
      <video v-show="!preview && !failed" ref="video" autoplay muted playsinline class="h-full w-full object-cover" />
      <img v-if="preview" :src="preview" alt="Captured photo" class="max-h-full max-w-full object-contain" />
      <div v-if="failed && !preview" class="max-w-xs px-6 text-center">
        <FeatherIcon name="camera-off" class="mx-auto h-10 w-10 text-white/60" />
        <p class="mt-3 font-semibold">Camera unavailable</p>
        <p class="mt-1 text-sm text-white/70">{{ failed }}</p>
      </div>
      <p v-if="!preview && !failed" class="absolute bottom-4 rounded-full bg-black/50 px-3 py-1 text-xs text-white/80">{{ hint }}</p>
    </div>

    <footer class="px-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] pt-5">
      <div v-if="preview" class="mx-auto flex max-w-sm gap-3">
        <button class="flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-white/10 font-semibold hover:bg-white/20" @click="retake"><FeatherIcon name="rotate-ccw" class="h-5 w-5" />Retake</button>
        <button class="flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-accent-400 font-semibold text-brand-900 hover:bg-accent-500" @click="use"><FeatherIcon name="check" class="h-5 w-5" />{{ confirmLabel }}</button>
      </div>
      <div v-else class="mx-auto flex max-w-sm items-center justify-between">
        <label class="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-white/10 hover:bg-white/20" aria-label="Choose a photo from the device">
          <FeatherIcon name="image" class="h-5 w-5" />
          <input type="file" accept="image/jpeg,image/png" class="sr-only" @change="pickFile" />
        </label>
        <button class="flex h-[72px] w-[72px] items-center justify-center rounded-full border-4 border-white disabled:opacity-40" :disabled="!!failed || !ready" aria-label="Take photo" @click="capture">
          <span class="h-14 w-14 rounded-full bg-white transition active:scale-90" />
        </button>
        <button class="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 hover:bg-white/20 disabled:opacity-40" :disabled="!!failed" aria-label="Switch camera" @click="swap">
          <FeatherIcon name="refresh-cw" class="h-5 w-5" />
        </button>
      </div>
    </footer>
    <canvas ref="canvas" class="hidden" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({ mode: String })
const emit = defineEmits(['close-event', 'capture-event'])
const video = ref(null)
const canvas = ref(null)
const preview = ref('')
const failed = ref('')
const ready = ref(false)
// Selfies for attendance; the back camera for everything else.
const facing = ref(['Check-In', 'Check-Out'].includes(props.mode) ? 'user' : 'environment')
let stream = null
let file = null

const title = computed(() => ({ 'Check-In': 'Check-in photo', 'Check-Out': 'Check-out photo', Upload: 'Photo update', Photo: 'Take a photo' })[props.mode] || 'Take a photo')
const hint = computed(() => ({ Upload: 'Show the progress on site', Photo: 'Point the camera at what you want to show' })[props.mode] || 'Take a clear photo of yourself on site')
const confirmLabel = computed(() => ({ 'Check-In': 'Check in', 'Check-Out': 'Check out', Upload: 'Upload', Photo: 'Use photo' })[props.mode] || 'Use photo')

async function start() {
  stop()
  ready.value = false
  failed.value = ''
  if (!navigator.mediaDevices?.getUserMedia) {
    failed.value = 'This browser cannot open the camera. Choose a photo from your device instead.'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing.value, width: { ideal: 1280 } }, audio: false })
    video.value.srcObject = stream
    await video.value.play()
    ready.value = true
  } catch (e) {
    failed.value = e?.name === 'NotAllowedError' ? 'Allow camera access in your browser settings, or choose a photo from your device.' : 'No camera was found. Choose a photo from your device instead.'
  }
}

function stop() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
}

function capture() {
  const v = video.value
  const scale = Math.min(1, 1280 / Math.max(v.videoWidth, v.videoHeight))
  canvas.value.width = Math.round(v.videoWidth * scale)
  canvas.value.height = Math.round(v.videoHeight * scale)
  canvas.value.getContext('2d').drawImage(v, 0, 0, canvas.value.width, canvas.value.height)
  canvas.value.toBlob(
    (blob) => {
      file = new File([blob], `${props.mode || 'photo'}-${Date.now()}.jpg`, { type: 'image/jpeg' })
      preview.value = URL.createObjectURL(blob)
      stop()
    },
    'image/jpeg',
    0.85,
  )
}

function pickFile(event) {
  const picked = event.target.files?.[0]
  if (!picked) return
  file = picked
  preview.value = URL.createObjectURL(picked)
  stop()
}

function retake() {
  URL.revokeObjectURL(preview.value)
  preview.value = ''
  file = null
  start()
}

function swap() {
  facing.value = facing.value === 'user' ? 'environment' : 'user'
  start()
}

function use() {
  emit('capture-event', file)
  emit('close-event', true)
}

function close() {
  emit('close-event', true)
}

onMounted(start)
onBeforeUnmount(() => {
  stop()
  if (preview.value) URL.revokeObjectURL(preview.value)
})
</script>
