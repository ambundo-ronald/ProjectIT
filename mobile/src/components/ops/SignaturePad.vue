<template>
  <Modal :model-value="modelValue" title="Sign off" :subtitle="label" size="md" @update:model-value="emit('update:modelValue', $event)">
    <div class="palette-light relative overflow-hidden rounded-xl border-2 border-dashed border-gray-300 bg-panel">
      <canvas
        ref="canvas"
        class="block h-48 w-full touch-none"
        aria-label="Signature area. Draw your signature with a finger, pen or mouse."
        role="img"
        @pointerdown="down"
        @pointermove="move"
        @pointerup="up"
        @pointerleave="up"
        @pointercancel="up"
      />
      <span class="pointer-events-none absolute inset-x-6 bottom-10 border-b border-gray-300" />
      <span v-if="empty" class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-gray-400">Sign here</span>
    </div>
    <p class="mt-2 text-xs text-gray-500">Signing as <strong class="font-medium text-gray-700">{{ me.full_name }}</strong>. The signature and time are saved with this step.</p>
    <template #footer>
      <button type="button" class="btn btn-ghost mr-auto" :disabled="empty" @click="clear"><FeatherIcon name="rotate-ccw" class="h-4 w-4" />Clear</button>
      <button type="button" class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button type="button" class="btn btn-primary" :disabled="empty" @click="save"><FeatherIcon name="check" class="h-4 w-4" />Save signature</button>
    </template>
  </Modal>
</template>
<script setup>
import { ref, watch, nextTick } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import { me } from '@/data/ops'

const props = defineProps({ modelValue: Boolean, label: String })
const emit = defineEmits(['update:modelValue', 'signed'])
const canvas = ref(null)
const empty = ref(true)
let ctx = null
let drawing = false

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    await nextTick()
    const el = canvas.value
    const ratio = window.devicePixelRatio || 1
    el.width = el.clientWidth * ratio
    el.height = el.clientHeight * ratio
    ctx = el.getContext('2d')
    ctx.scale(ratio, ratio)
    ctx.lineWidth = 2.2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#111827'
    empty.value = true
  },
)

const point = (e) => {
  const r = canvas.value.getBoundingClientRect()
  return [e.clientX - r.left, e.clientY - r.top]
}
function down(e) {
  drawing = true
  canvas.value.setPointerCapture?.(e.pointerId)
  ctx.beginPath()
  ctx.moveTo(...point(e))
}
function move(e) {
  if (!drawing) return
  ctx.lineTo(...point(e))
  ctx.stroke()
  empty.value = false
}
const up = () => (drawing = false)
function clear() {
  ctx.clearRect(0, 0, canvas.value.width, canvas.value.height)
  empty.value = true
}
function save() {
  // White background so the PNG reads well in Desk and print.
  const out = document.createElement('canvas')
  out.width = canvas.value.width
  out.height = canvas.value.height
  const o = out.getContext('2d')
  o.fillStyle = '#fff'
  o.fillRect(0, 0, out.width, out.height)
  o.drawImage(canvas.value, 0, 0)
  emit('signed', out.toDataURL('image/png').split(',')[1])
  emit('update:modelValue', false)
}
</script>
