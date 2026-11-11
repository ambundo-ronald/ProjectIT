<template>
  <div v-if="people.length" class="flex items-center">
    <div class="flex -space-x-1.5">
      <UserAvatar v-for="p in people.slice(0, max)" :key="p.user" :name="p.full_name" :image="p.image" :size="size" class="ring-2 ring-panel" />
    </div>
    <span v-if="people.length > max" class="ml-1 text-xs font-medium text-gray-500">+{{ people.length - max }}</span>
  </div>
  <span v-else class="text-xs text-gray-400">Unassigned</span>
</template>
<script setup>
import UserAvatar from './UserAvatar.vue'
defineProps({ people: { type: Array, default: () => [] }, max: { type: Number, default: 3 }, size: { type: String, default: 'sm' } })
</script>
