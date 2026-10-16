<template>
  <div v-if="ready" class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <h2 class="card-title">Root cause investigations</h2>
      <button class="btn btn-secondary btn-sm" :disabled="starting" @click="start"><FeatherIcon name="crosshair" class="h-4 w-4" />{{ starting ? 'Starting…' : 'Investigate root cause' }}</button>
    </div>
    <ul v-if="rows.length" class="divide-y divide-gray-100">
      <li v-for="r in rows" :key="r.name">
        <router-link :to="{ name: 'OpsInvestigation', params: { name: r.name } }" class="flex items-center gap-3 px-5 py-2.5 text-sm hover:bg-gray-50">
          <span class="min-w-0 flex-1 truncate font-medium">{{ r.title }}</span>
          <span v-if="r.actions" class="shrink-0 text-xs tabular-nums text-gray-500">{{ r.actions_done }}/{{ r.actions }} actions</span>
          <span class="shrink-0 rounded px-1.5 text-[11px] font-semibold" :class="r.status === 'Closed' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-800'">{{ r.status }}</span>
        </router-link>
      </li>
    </ul>
    <p v-else class="px-5 py-3 text-sm text-gray-500">{{ workOrder ? 'When a problem keeps coming back, find out why: causes under the 6Ms, the evidence, the 5 Whys and a PDF report.' : 'None yet for this machine.' }}</p>
    <p v-if="error" role="alert" class="px-5 pb-3 text-sm text-red-600">{{ error }}</p>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import { api } from '@/data/ops'

const props = defineProps({ workOrder: String, equipment: String, asset: String })
const router = useRouter()
const rows = ref([])
const ready = ref(false)
const starting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const r = await api('projectit.investigations.list_investigations', { work_order: props.workOrder || null, equipment: props.workOrder ? null : props.equipment || null, asset: props.workOrder ? null : props.asset || null })
    rows.value = r.investigations
    ready.value = true
  } catch (e) {
    /* offline, or no Techy Ops access: leave the card out */
  }
})
async function start() {
  starting.value = true
  error.value = ''
  try {
    const r = await api('projectit.investigations.start', { work_order: props.workOrder || null, equipment: props.equipment || null, asset: props.asset || null })
    router.push({ name: 'OpsInvestigation', params: { name: r.investigation.name } })
  } catch (e) {
    error.value = e.message
  } finally {
    starting.value = false
  }
}
</script>
