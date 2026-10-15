<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">Time on job</h2>
      <span class="text-sm tabular-nums text-gray-600">{{ t.total ? `${duration(t.total)} logged` : 'No time logged' }}</span>
    </div>
    <div class="space-y-4 p-5">
      <!-- My clock -->
      <div v-if="t.mine" class="flex items-center justify-between gap-3 rounded-xl bg-amber-50 px-4 py-3">
        <div>
          <p class="flex items-center gap-2 text-xs font-medium text-amber-800"><span class="h-2 w-2 animate-pulse rounded-full bg-amber-500" />Your timer is running</p>
          <p class="mt-0.5 text-[26px] font-semibold tabular-nums tracking-tight text-gray-900" role="timer" aria-label="Time on this job">{{ clock(running(t.mine)) }}</p>
        </div>
        <button class="btn btn-danger btn-lg" :disabled="busy" @click="call('projectit.timer.stop', { work_order: workOrder })"><FeatherIcon name="square" class="h-4 w-4" />Stop</button>
      </div>
      <div v-else-if="t.can_start" class="flex flex-wrap items-center justify-between gap-3">
        <p class="text-sm text-gray-500">{{ status === 'Working' ? 'Track the time you spend on this job.' : 'Starting the timer moves the job to in progress.' }}</p>
        <button class="btn btn-primary btn-lg" :disabled="busy" @click="start"><FeatherIcon name="play" class="h-4 w-4" />Start timer</button>
      </div>

      <!-- Others working now -->
      <ul v-if="others.length" class="space-y-2">
        <li v-for="r in others" :key="r.name" class="flex items-center gap-2.5 text-sm">
          <UserAvatar :name="r.full_name" :image="r.image" size="sm" />
          <span class="min-w-0 flex-1 truncate"><span class="font-medium">{{ r.full_name }}</span> <span class="text-gray-500">is on this job</span></span>
          <span class="tabular-nums text-gray-700">{{ clock(running(r)) }}</span>
          <button v-if="t.manager && r.can_edit" class="btn btn-ghost btn-sm text-gray-500" :disabled="busy" @click="call('projectit.timer.stop', { work_order: workOrder, entry: r.name })">Stop</button>
        </li>
      </ul>

      <!-- Entries -->
      <ul v-if="finished.length" class="divide-y divide-gray-100 border-t border-gray-100" aria-label="Time entries">
        <li v-for="r in shown" :key="r.name" class="flex items-center gap-2.5 py-2.5 text-sm">
          <UserAvatar :name="r.full_name" :image="r.image" size="sm" />
          <div class="min-w-0 flex-1">
            <p class="truncate"><span class="font-medium">{{ r.full_name }}</span><span v-if="r.source === 'Manual'" class="ml-1.5 rounded bg-gray-100 px-1 text-[11px] text-gray-500">added</span></p>
            <p class="truncate text-xs text-gray-500">{{ formatDate(r.started_at) }} · {{ formatTime(r.started_at) }}–{{ formatTime(r.ended_at) }}</p>
          </div>
          <template v-if="editing === r.name">
            <label class="sr-only" :for="`entry-${r.name}`">Minutes</label>
            <input :id="`entry-${r.name}`" v-model.number="minutes" type="number" min="1" max="1440" inputmode="numeric" class="input h-8 w-20 py-0 text-sm" @keydown.enter="saveEntry(r)" />
            <span class="text-xs text-gray-500">min</span>
            <button class="btn btn-primary btn-sm" :disabled="busy" @click="saveEntry(r)">Save</button>
            <button class="btn btn-ghost btn-sm" @click="editing = ''">Cancel</button>
          </template>
          <template v-else>
            <span class="tabular-nums text-gray-800">{{ duration(r.hours) }}</span>
            <template v-if="r.can_edit">
              <button class="btn btn-ghost btn-icon h-8 w-8 text-gray-400" :aria-label="`Change ${r.full_name}'s time`" :disabled="busy" @click="edit(r)"><FeatherIcon name="edit-2" class="h-3.5 w-3.5" /></button>
              <button class="btn btn-ghost btn-icon -ml-2 h-8 w-8 text-gray-400 hover:text-red-600" :aria-label="`Delete ${r.full_name}'s time`" :disabled="busy" @click="remove(r)"><FeatherIcon name="trash-2" class="h-3.5 w-3.5" /></button>
            </template>
          </template>
        </li>
      </ul>
      <button v-if="finished.length > 5" class="text-xs font-medium text-brand-600 hover:underline" @click="all = !all">{{ all ? 'Show fewer' : `Show all ${finished.length} entries` }}</button>

      <!-- Add time by hand -->
      <form v-if="adding" class="flex flex-wrap items-end gap-3 rounded-lg bg-gray-50 p-3" @submit.prevent="add">
        <div>
          <label class="label" for="add-hours">Hours</label>
          <input id="add-hours" v-model.number="addHours" type="number" min="0" max="24" inputmode="numeric" class="input w-20" />
        </div>
        <div>
          <label class="label" for="add-minutes">Minutes</label>
          <input id="add-minutes" v-model.number="addMinutes" type="number" min="0" max="59" step="5" inputmode="numeric" class="input w-20" />
        </div>
        <div v-if="t.manager && people.length">
          <label class="label" for="add-user">Who</label>
          <select id="add-user" v-model="addUser" class="input w-auto">
            <option v-for="p in people" :key="p.user" :value="p.user">{{ p.full_name || p.user }}</option>
          </select>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-primary" :disabled="busy || !addTotal">Add {{ addTotal ? duration(addTotal / 60) : '' }}</button>
          <button type="button" class="btn btn-ghost" @click="adding = false">Cancel</button>
        </div>
      </form>
      <button v-else-if="t.can_add" class="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline" @click="openAdd"><FeatherIcon name="plus" class="h-4 w-4" />Add time you forgot to clock</button>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import { api, me, now, useTick, clock, duration, formatDate, formatTime } from '@/data/ops'

const props = defineProps({
  timer: { type: Object, required: true },
  workOrder: { type: String, required: true },
  status: String,
  assignees: { type: Array, default: () => [] },
})
const emit = defineEmits(['updated', 'error'])
const t = computed(() => props.timer)
const busy = ref(false)
const all = ref(false)
const editing = ref('')
const minutes = ref(0)
const adding = ref(false)
const addHours = ref(0)
const addMinutes = ref(0)
const addUser = ref('')

// Running clocks count on from the server's elapsed seconds at load time, whatever the phone's clock says.
const loadedAt = ref(Date.now())
watch(() => props.timer, () => (loadedAt.value = Date.now()))
const untick = useTick()
onBeforeUnmount(untick)
const running = (r) => r.elapsed + (now.value - loadedAt.value) / 1000

const others = computed(() => t.value.running.filter((r) => r.name !== t.value.mine?.name))
const finished = computed(() => t.value.entries.filter((r) => r.ended_at))
const shown = computed(() => (all.value ? finished.value : finished.value.slice(0, 5)))
const people = computed(() => {
  const list = [...props.assignees]
  if (!list.some((p) => p.user === me.user)) list.unshift({ user: me.user, full_name: me.full_name })
  return list
})
const addTotal = computed(() => Math.max(0, (Number(addHours.value) || 0) * 60 + (Number(addMinutes.value) || 0)))

async function call(method, args, done) {
  busy.value = true
  try {
    emit('updated', await api(method, args))
    done?.()
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
function start() {
  const switching = me.timer && me.timer.work_order !== props.workOrder
  call('projectit.timer.start', { work_order: props.workOrder }, () => {
    if (switching) toast({ title: `Stopped your timer on ${me.timer.subject}`, icon: 'clock', position: 'top-center' })
  })
}
function edit(r) {
  editing.value = r.name
  minutes.value = Math.round(r.hours * 60)
}
const saveEntry = (r) => call('projectit.timer.update_entry', { name: r.name, minutes: minutes.value }, () => (editing.value = ''))
const remove = (r) => window.confirm(`Delete ${duration(r.hours)} logged by ${r.full_name}?`) && call('projectit.timer.delete_entry', { name: r.name })
function openAdd() {
  addHours.value = 0
  addMinutes.value = 30
  addUser.value = me.user
  adding.value = true
}
const add = () => call('projectit.timer.add_time', { work_order: props.workOrder, minutes: addTotal.value, user: addUser.value || undefined }, () => (adding.value = false))
</script>
