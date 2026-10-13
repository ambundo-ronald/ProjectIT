<template>
  <section class="ops space-y-5">
    <!-- List -->
    <template v-if="!detail">
      <PageHeader mobile :title="manager ? 'Project tasks' : 'My tasks'" :subtitle="manager ? 'Tasks across your projects.' : 'Project tasks assigned to you.'">
        <button class="btn btn-ghost btn-icon" aria-label="Refresh" :disabled="busy" @click="reload"><FeatherIcon name="refresh-cw" class="h-4 w-4" :class="busy ? 'animate-spin' : ''" /></button>
        <button v-if="manager && canManage" class="btn btn-primary" @click="openCreate"><FeatherIcon name="plus" class="h-4 w-4" />New task</button>
      </PageHeader>
      <div class="segmented" role="group" aria-label="Filter">
        <button v-for="f in filters" :key="f.key" :aria-pressed="filter === f.key" @click="filter = f.key">{{ f.label }}<span class="text-xs text-gray-400">{{ f.count }}</span></button>
      </div>
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

      <div v-if="busy && !rows.length" class="space-y-2"><div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" /></div>
      <ul v-else-if="visible.length" class="space-y-2">
        <li v-for="task in visible" :key="task.name">
          <button class="card group flex w-full items-start gap-3 p-4 text-left transition hover:border-gray-300 hover:shadow-pop" :disabled="busy" @click="open(task.name)">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2" :class="task.status === 'Completed' ? 'border-green-500 bg-green-500 text-white' : 'border-gray-300'">
              <FeatherIcon v-if="task.status === 'Completed'" name="check" class="h-3 w-3" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-semibold leading-snug group-hover:text-brand-700" :class="task.status === 'Completed' ? 'text-gray-500' : 'text-gray-900'">{{ task.subject }}</span>
              <span class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                <StatusPill :status="task.status" />
                <PriorityFlag :priority="task.priority" />
                <span class="inline-flex items-center gap-1"><FeatherIcon name="briefcase" class="h-3.5 w-3.5" />{{ task.project_name || task.project }}</span>
                <span v-if="task.is_group" class="inline-flex items-center gap-1"><FeatherIcon name="list" class="h-3.5 w-3.5" />Checklist</span>
              </span>
            </span>
            <span v-if="task.exp_end_date && !closedStatus(task.status)" class="shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold" :class="dueTone(task)">{{ dueLabel(task) }}</span>
          </button>
        </li>
      </ul>
      <EmptyState v-else :icon="filter === 'open' ? 'check-circle' : 'inbox'" :title="filter === 'open' ? 'Nothing to do right now' : 'No tasks here'" :text="manager ? 'Create a task or checklist for someone on a project.' : 'Tasks your manager assigns to you will show up here.'" />
      <button v-if="hasMore" class="btn btn-secondary w-full" :disabled="busy" @click="loadMore">Load more</button>
    </template>

    <!-- Detail -->
    <template v-else>
      <button class="btn btn-ghost btn-sm -ml-2" :disabled="busy" @click="back"><FeatherIcon name="arrow-left" class="h-4 w-4" />{{ manager ? 'Project tasks' : 'My tasks' }}</button>
      <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

      <div class="card p-5">
        <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <span class="inline-flex items-center gap-1"><FeatherIcon name="briefcase" class="h-3.5 w-3.5" />{{ detail.task.project_name || detail.task.project }}</span>
          <span v-if="detail.task.exp_end_date">· Due {{ formatDate(detail.task.exp_end_date) }}</span>
        </div>
        <h1 class="mt-2 text-[20px] font-semibold leading-snug tracking-tight">{{ detail.task.subject }}</h1>
        <div class="mt-2 flex items-center gap-3"><StatusPill :status="detail.task.status" /><PriorityFlag :priority="detail.task.priority" /></div>
        <p v-if="detail.description" class="mt-4 whitespace-pre-wrap text-[15px] leading-relaxed text-gray-700">{{ detail.description }}</p>

        <div v-if="detail.workflow" class="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">This task uses an approval workflow. <a :href="deskLink(detail.task.name)" target="_blank" rel="noopener" class="font-medium underline">Open in ERPNext</a> to change its status.</div>
        <div v-else-if="detail.can_write" class="mt-5">
          <span class="label">Status</span>
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <button v-for="s in statuses" :key="s" class="flex h-10 items-center justify-center rounded-lg border text-sm font-medium transition-colors disabled:opacity-50" :class="detail.task.status === s ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'" :disabled="busy || detail.task.status === s" @click="saveStatus(s)">
              {{ STATUS_LABEL[s] || s }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="detail.children.length" class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Checklist</h2><span class="text-sm text-gray-500">{{ detail.children.filter((c) => c.status === 'Completed').length }} of {{ detail.children.length }} done</span></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="child in detail.children" :key="child.name">
            <button class="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-gray-50" :disabled="busy" @click="open(child.name)">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2" :class="child.status === 'Completed' ? 'border-green-500 bg-green-500 text-white' : 'border-gray-300'"><FeatherIcon v-if="child.status === 'Completed'" name="check" class="h-3 w-3" /></span>
              <span class="flex-1 text-[15px]" :class="child.status === 'Completed' ? 'text-gray-400' : 'text-gray-800'">{{ child.subject }}</span>
              <FeatherIcon name="chevron-right" class="h-4 w-4 text-gray-300" />
            </button>
          </li>
        </ul>
        <p v-if="detail.task.is_group && !manager" class="border-t border-gray-100 px-5 py-2 text-xs text-gray-500">Only steps assigned to you are shown.</p>
      </div>

      <div class="card p-5">
        <div class="flex items-center justify-between"><h2 class="card-title">Photos & files</h2><span class="text-xs text-gray-500">{{ files.length }}</span></div>
        <div class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
          <a v-for="file in files" :key="file.name" :href="file.file_url" target="_blank" rel="noopener" class="block aspect-square overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
            <img v-if="/\.(jpe?g|png|gif|webp)$/i.test(file.file_url)" :src="file.file_url" :alt="file.file_name" class="h-full w-full object-cover" loading="lazy" />
            <span v-else class="flex h-full items-center justify-center p-1 text-center text-[11px]">{{ file.file_name }}</span>
          </a>
          <label v-if="detail.can_write" class="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700">
            <FeatherIcon name="camera" class="h-5 w-5" /><span class="text-xs font-medium">Add photo</span>
            <input type="file" accept="image/jpeg,image/png" capture="environment" class="sr-only" :disabled="busy" @change="upload" />
          </label>
        </div>
      </div>

      <div class="card p-5">
        <h2 class="card-title">Updates</h2>
        <ol v-if="detail.comments.length" class="mt-4 space-y-4">
          <li v-for="c in detail.comments" :key="c.name" class="flex gap-3">
            <UserAvatar :name="c.comment_by" size="md" />
            <div class="min-w-0 flex-1">
              <p class="text-xs text-gray-500"><span class="text-[13px] font-semibold text-gray-900">{{ c.comment_by }}</span> · {{ fromNow(c.creation) }}</p>
              <p class="mt-0.5 whitespace-pre-wrap text-[14px] leading-relaxed text-gray-800">{{ c.content }}</p>
            </div>
          </li>
        </ol>
        <p v-else class="mt-2 text-sm text-gray-500">No updates yet.</p>
        <Composer v-if="detail.can_write" class="mt-5" placeholder="Post a work update…" :submit="comment" />
      </div>
      <a :href="deskLink(detail.task.name)" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-brand-700"><FeatherIcon name="external-link" class="h-3.5 w-3.5" />Open in ERPNext</a>
    </template>

    <!-- Create -->
    <Modal v-model="creating" title="New task" subtitle="Add steps to make it a checklist. Each step becomes its own task." size="lg">
      <form id="task-form" class="space-y-4" @submit.prevent="create">
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="task-project">Project <span class="text-red-500">*</span></label>
            <select id="task-project" v-model="form.project" required class="input" @change="loadPeople">
              <option value="">Choose project</option>
              <option v-for="p in options.projects" :key="p.name" :value="p.name">{{ p.project_name }}</option>
            </select>
          </div>
          <div>
            <label class="label" for="task-assignee">Assign to <span class="text-red-500">*</span></label>
            <select id="task-assignee" v-model="form.assignee" required class="input" :disabled="!form.project">
              <option value="">{{ form.project ? 'Choose employee' : 'Choose a project first' }}</option>
              <option v-for="p in options.people" :key="p.user_id" :value="p.user_id">{{ p.employee_name }}</option>
            </select>
            <p v-if="form.project && !options.people.length" class="hint">Allocate someone with a user account to this project first.</p>
          </div>
        </div>
        <div>
          <label class="label" for="task-title">Title <span class="text-red-500">*</span></label>
          <input id="task-title" v-model="form.subject" required maxlength="140" class="input" placeholder="e.g. Install cable tray in plant room" />
        </div>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="label" for="task-due">Due</label>
            <input id="task-due" v-model="form.due_date" type="datetime-local" class="input" />
          </div>
          <div>
            <label class="label" for="task-priority">Priority</label>
            <select id="task-priority" v-model="form.priority" class="input"><option>Low</option><option>Medium</option><option>High</option><option>Urgent</option></select>
          </div>
        </div>
        <div>
          <label class="label" for="task-steps">Checklist steps <span class="font-normal text-gray-400">(one per line, optional)</span></label>
          <textarea id="task-steps" v-model="steps" rows="4" class="input" placeholder="Isolate power&#10;Fit tray&#10;Test and tag" />
        </div>
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
      </form>
      <template #footer>
        <button type="button" class="btn btn-secondary" @click="creating = false">Cancel</button>
        <button form="task-form" :disabled="busy" class="btn btn-primary">Create task</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import StatusPill from '@/components/ops/StatusPill.vue'
import PriorityFlag from '@/components/ops/PriorityFlag.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import Composer from '@/components/ops/Composer.vue'
import Modal from '@/components/ops/Modal.vue'
import { api, STATUS_LABEL, formatDate, fromNow, dueIn, readFile, safeFile } from '@/data/ops'

const route = useRoute()
const props = defineProps({ manager: Boolean })
const rows = ref([])
const detail = ref(null)
const error = ref('')
const busy = ref(false)
const hasMore = ref(false)
const canManage = ref(false)
const creating = ref(false)
const steps = ref('')
const filter = ref('open')
const options = reactive({ projects: [], people: [] })
const form = reactive({ project: '', subject: '', assignee: '', due_date: '', priority: 'Medium' })

const closedStatus = (s) => ['Completed', 'Cancelled'].includes(s)
const statuses = computed(() => ['Open', 'Working', 'Pending Review', 'Completed', ...(detail.value?.manager ? ['Cancelled'] : [])])
const filters = computed(() => [
  { key: 'open', label: 'To do', count: rows.value.filter((t) => !closedStatus(t.status)).length },
  { key: 'done', label: 'Done', count: rows.value.filter((t) => t.status === 'Completed').length },
  { key: 'all', label: 'All', count: rows.value.length },
])
const visible = computed(() => rows.value.filter((t) => (filter.value === 'open' ? !closedStatus(t.status) : filter.value === 'done' ? t.status === 'Completed' : true)))
const files = computed(() => (detail.value?.files || []).filter((f) => safeFile(f.file_url)))
const dueLabel = (t) => {
  const d = dueIn(String(t.exp_end_date).slice(0, 10))
  return d < 0 ? `${-d}d overdue` : d === 0 ? 'Due today' : d === 1 ? 'Tomorrow' : `In ${d}d`
}
const dueTone = (t) => {
  const d = dueIn(String(t.exp_end_date).slice(0, 10))
  return d < 0 ? 'bg-red-50 text-red-700' : d <= 1 ? 'bg-amber-50 text-amber-800' : 'bg-gray-100 text-gray-600'
}

async function run(work) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function list(append = false) {
  const data = await api('projectit.tasks.list_tasks', { mine: props.manager ? 0 : 1, start: append ? rows.value.length : 0 })
  rows.value = append ? [...rows.value, ...data.tasks] : data.tasks
  hasMore.value = data.has_more
  canManage.value = data.manager
}
const setDetail = (data) => (detail.value = data)
const reload = () => run(async () => (detail.value ? setDetail(await api('projectit.tasks.get_task', { name: detail.value.task.name })) : list()))
const back = () =>
  run(async () => {
    detail.value = null
    await list()
  })
const open = (name) => run(async () => setDetail(await api('projectit.tasks.get_task', { name })))
const loadMore = () => run(() => list(true))
const saveStatus = (status) => run(async () => setDetail(await api('projectit.tasks.update_status', { name: detail.value.task.name, status, modified: detail.value.task.modified })))
async function comment(content) {
  busy.value = true
  error.value = ''
  try {
    setDetail(await api('projectit.tasks.add_comment', { name: detail.value.task.name, content }))
  } catch (e) {
    error.value = e.message
    throw e
  } finally {
    busy.value = false
  }
}
const openCreate = () =>
  run(async () => {
    Object.assign(options, await api('projectit.tasks.task_options'))
    creating.value = true
  })
const loadPeople = () =>
  run(async () => {
    form.assignee = ''
    options.people = []
    Object.assign(options, await api('projectit.tasks.task_options', { project: form.project }))
  })
const create = () =>
  run(async () => {
    const data = await api('projectit.tasks.create_task', {
      ...form,
      due_date: form.due_date ? form.due_date.replace('T', ' ') : null,
      steps: steps.value.split('\n').map((s) => s.trim()).filter(Boolean),
    })
    creating.value = false
    form.subject = ''
    steps.value = ''
    setDetail(await api('projectit.tasks.get_task', { name: data.name }))
  })
const deskLink = (name) => `/desk/task/${encodeURIComponent(name)}`
async function upload(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  await run(async () => setDetail(await api('projectit.tasks.attach_photo', { name: detail.value.task.name, content: await readFile(file) })))
}
onMounted(() => (route.query.task ? open(String(route.query.task)) : reload()))
</script>
