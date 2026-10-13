<template>
  <div ref="root" class="relative" @keydown.esc="open = false">
    <slot name="trigger" :open="open" :toggle="toggle" />
    <Transition enter-from-class="opacity-0 -translate-y-1" leave-to-class="opacity-0 -translate-y-1" enter-active-class="transition duration-100" leave-active-class="transition duration-75">
      <div v-if="open" class="ops absolute z-50 w-72 rounded-xl border border-gray-200 bg-white p-1.5 text-gray-900 shadow-pop" :class="[align === 'right' ? 'right-0' : 'left-0', placement === 'top' ? 'bottom-full mb-2' : 'mt-2']" role="menu" @click="closeOnClick && (open = false)">
        <slot :close="() => (open = false)" />
      </div>
    </Transition>
  </div>
</template>
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
defineProps({ align: { type: String, default: 'left' }, placement: { type: String, default: 'bottom' }, closeOnClick: { type: Boolean, default: true } })
const open = ref(false)
const root = ref(null)
const toggle = () => (open.value = !open.value)
const outside = (e) => root.value && !root.value.contains(e.target) && (open.value = false)
watch(open, (v) => (v ? document.addEventListener('pointerdown', outside) : document.removeEventListener('pointerdown', outside)))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))
</script>
