<template>
  <header class="flex items-end justify-between gap-3" :class="mobile ? 'flex-nowrap' : 'flex-wrap'">
    <!-- On phones the app bar already shows the page title. -->
    <div class="min-w-0" :class="mobile ? 'flex-1' : 'hidden md:block'">
      <h1 class="truncate text-[20px] font-semibold tracking-tight text-gray-900 md:text-[26px] md:leading-8">{{ title }}</h1>
      <p v-if="subtitle || $slots.subtitle" class="mt-0.5 text-sm text-gray-500"><slot name="subtitle">{{ subtitle }}</slot></p>
    </div>
    <div v-if="$slots.default" class="ml-auto flex shrink-0 items-center gap-2"><slot /></div>
  </header>
</template>
<script setup>
defineProps({ title: String, subtitle: String, mobile: Boolean })
</script>
