<template>
  <!-- Two ways to add a photo: Camera (the phone's camera app, or the webcam window on a computer) and Photos
       (the gallery or files). `variant`: icons (composer), buttons (forms) or tiles (photo grids). -->
  <div :class="variant === 'tiles' ? 'contents' : 'flex shrink-0 items-center gap-1.5'">
    <template v-if="variant === 'icons'">
      <button type="button" :class="iconClass" :disabled="disabled || spinning" aria-label="Take a photo" title="Camera" @click="openCamera"><FeatherIcon :name="spinning ? 'loader' : 'camera'" class="h-4 w-4" :class="spinning ? 'animate-spin' : ''" /></button>
      <button type="button" :class="iconClass" :disabled="disabled || spinning" aria-label="Add photos" title="Photos" @click="gallery.click()"><FeatherIcon name="image" class="h-4 w-4" /></button>
    </template>
    <template v-else-if="variant === 'tiles'">
      <button type="button" :class="tileClass" :disabled="disabled || spinning" @click="openCamera"><FeatherIcon :name="spinning ? 'loader' : 'camera'" class="h-5 w-5" :class="spinning ? 'animate-spin' : ''" /><span class="text-xs font-medium">{{ spinning ? 'Uploading…' : 'Camera' }}</span></button>
      <button type="button" :class="tileClass" :disabled="disabled || spinning" @click="gallery.click()"><FeatherIcon name="image" class="h-5 w-5" /><span class="text-xs font-medium">{{ multiple ? 'Photos' : 'Upload' }}</span></button>
    </template>
    <template v-else>
      <button type="button" class="btn btn-secondary" :disabled="disabled || spinning" @click="openCamera"><FeatherIcon :name="spinning ? 'loader' : 'camera'" class="h-4 w-4" :class="spinning ? 'animate-spin' : ''" />{{ cameraLabel }}</button>
      <button type="button" class="btn btn-secondary" :disabled="disabled || spinning" @click="gallery.click()"><FeatherIcon name="image" class="h-4 w-4" />{{ multiple ? 'Photos' : 'Upload' }}</button>
    </template>
    <input ref="camera" type="file" accept="image/*" capture="environment" class="hidden" tabindex="-1" aria-hidden="true" @change="picked" />
    <input ref="gallery" type="file" accept="image/*" :multiple="multiple" class="hidden" tabindex="-1" aria-hidden="true" @change="picked" />
    <Teleport to="body">
      <Camera v-if="webcam" mode="Photo" @close-event="webcam = false" @capture-event="(file) => add([file])" />
    </Teleport>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Camera from '@/components/Camera.vue'
import { shrink, touchDevice } from '@/data/photos'

const props = defineProps({
  variant: { type: String, default: 'buttons' },
  multiple: Boolean,
  max: { type: Number, default: 6 },
  disabled: Boolean,
  busy: Boolean, // the caller is uploading
  cameraLabel: { type: String, default: 'Camera' },
})
// photos: [{ content: base64 JPEG, preview: object URL }]
const emit = defineEmits(['photos', 'error'])
const camera = ref(null)
const gallery = ref(null)
const webcam = ref(false)
const working = ref(false)
const spinning = computed(() => working.value || props.busy)
const iconClass = 'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-gray-800 disabled:opacity-40'
const tileClass = 'flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50'

function openCamera() {
  if (touchDevice()) camera.value.click()
  else webcam.value = true
}

function picked(event) {
  const files = [...(event.target.files || [])]
  event.target.value = '' // the same photo can be picked again
  add(files)
}

async function add(files) {
  if (!files.length) return
  if (files.length > props.max) {
    emit('error', `Choose at most ${props.max} photos at a time.`)
    files = files.slice(0, props.max)
  }
  working.value = true
  try {
    emit('photos', await Promise.all(files.map((f) => shrink(f))))
  } catch (e) {
    emit('error', e.message)
  } finally {
    working.value = false
  }
}
</script>
