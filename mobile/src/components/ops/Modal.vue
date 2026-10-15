<template>
  <Teleport to="body">
    <Transition enter-from-class="opacity-0" leave-to-class="opacity-0" enter-active-class="transition duration-150" leave-active-class="transition duration-100">
      <div
        v-if="modelValue"
        class="ops fixed inset-0 z-50 flex items-end justify-center bg-gray-900/50 backdrop-blur-[2px] sm:items-center sm:p-6"
        @mousedown.self="close"
      >
        <div
          ref="panel"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
          class="flex max-h-[94dvh] w-full flex-col rounded-t-2xl bg-white shadow-pop outline-none sm:rounded-2xl"
          :class="{ md: 'sm:max-w-lg', lg: 'sm:max-w-2xl', xl: 'sm:max-w-4xl' }[wide ? 'lg' : size]"
        >
          <div class="mx-auto mt-2 h-1 w-10 rounded-full bg-gray-300 sm:hidden" aria-hidden="true" />
          <header class="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
            <div class="min-w-0">
              <h2 class="text-[18px] font-semibold text-gray-900">{{ title }}</h2>
              <p v-if="subtitle" class="mt-0.5 text-sm text-gray-500">{{ subtitle }}</p>
            </div>
            <button class="btn btn-ghost btn-icon -mr-2 -mt-1" aria-label="Close" @click="close">
              <FeatherIcon name="x" class="h-5 w-5" />
            </button>
          </header>
          <div class="overflow-y-auto px-5 pb-5">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex flex-wrap justify-end gap-2 border-t border-gray-100 bg-gray-50/60 px-5 py-3 sm:rounded-b-2xl">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { FeatherIcon } from 'frappe-ui'
const props = defineProps({ modelValue: Boolean, title: String, subtitle: String, size: { type: String, default: 'md' }, wide: Boolean })
const emit = defineEmits(['update:modelValue'])
const panel = ref(null)
const close = () => emit('update:modelValue', false)
// Escape closes the top-most dialog even when focus has left it (e.g. the button pressed was removed).
const onKey = (e) => {
  if (e.key !== 'Escape' || e.defaultPrevented) return
  const dialogs = document.querySelectorAll('[role="dialog"][aria-modal="true"]')
  if (dialogs[dialogs.length - 1] === panel.value) {
    e.preventDefault()
    close()
  }
}
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKey)
      nextTick(() => panel.value?.querySelector('input:not([type=hidden]),textarea,select')?.focus() || panel.value?.focus())
    } else document.removeEventListener('keydown', onKey)
  },
  { immediate: true },
)
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>
