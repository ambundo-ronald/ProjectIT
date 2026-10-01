<template>
  <section class="mx-6 mt-5 rounded-lg border border-[#B9C8EA] bg-[#F5F8FF] p-4" aria-label="My attendance">
    <div class="flex items-center justify-between gap-3">
      <h2 class="font-semibold text-[#163B65]">My attendance</h2>
      <button type="button" class="text-sm text-[#4A6BB6] underline" :disabled="attendance.loading" @click="refresh">Refresh</button>
    </div>
    <p v-if="error" role="alert" class="mt-2 text-sm text-red-700">{{ error }}</p>
    <p v-else class="mt-2 text-sm" aria-live="polite">{{ attendance.data?.message || 'Loading attendance...' }}</p>
    <details v-if="attendance.data?.records?.length" class="mt-3">
      <summary class="cursor-pointer text-sm font-medium">Recent attendance</summary>
      <ul class="mt-2 space-y-2 text-sm">
        <li v-for="record in attendance.data.records" :key="record.name" class="border-t border-[#B9C8EA] pt-2">
          <span>{{ record.attendance_date }} ? {{ record.status }}</span>
          <span v-if="record.docstatus === 0"> (Draft ? awaiting HR review)</span>
          <div v-if="record.shift" class="text-xs text-gray-600">{{ record.shift }}</div>
        </li>
      </ul>
    </details>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { createResource } from 'frappe-ui'
const error = ref('')
const attendance = createResource({ url: 'projectit.attendance.get_attendance_status' })
async function refresh() {
  error.value = ''
  try { await attendance.fetch() }
  catch (e) { error.value = e.messages?.join(' ') || e.message || 'Attendance could not be loaded. Try Refresh.' }
}
onMounted(refresh)
defineExpose({ refresh })
</script>
