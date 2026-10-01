<template>
  <section class="p-4 space-y-4">
    <div class="flex items-center justify-between gap-2">
      <h2 class="text-lg font-semibold">
        {{ manager ? 'Project tasks' : 'My tasks' }}
      </h2>
      <button class="text-blue-700 underline" :disabled="busy" @click="reload">
        Refresh
      </button>
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <p v-if="busy" aria-live="polite">Loading?</p>
    <template v-if="!detail">
      <button
        v-if="manager && canManage"
        class="rounded bg-blue-700 p-2 text-white"
        @click="openCreate"
      >
        New task / checklist
      </button>
      <fieldset v-if="creating" :disabled="busy">
        <form class="space-y-3 rounded border p-3" @submit.prevent="create">
          <label class="block"
            >Project<select
              v-model="form.project"
              required
              class="block w-full"
              @change="loadPeople"
            >
              <option value="">Choose project</option>
              <option
                v-for="p in options.projects"
                :key="p.name"
                :value="p.name"
              >
                {{ p.project_name }}
              </option>
            </select></label
          >
          <label class="block"
            >Task title<input
              v-model="form.subject"
              required
              maxlength="140"
              class="block w-full"
          /></label>
          <label class="block"
            >Assign to<select
              v-model="form.assignee"
              required
              class="block w-full"
            >
              <option value="">Choose employee</option>
              <option
                v-for="p in options.people"
                :key="p.user_id"
                :value="p.user_id"
              >
                {{ p.employee_name }}
              </option>
            </select></label
          >
          <p v-if="form.project && !options.people.length" class="text-sm">
            Allocate an employee with an enabled User account to this project
            first.
          </p>
          <label class="block"
            >Due date<input
              v-model="form.due_date"
              type="datetime-local"
              class="block w-full"
          /></label>
          <label class="block"
            >Priority<select v-model="form.priority" class="block w-full">
              <option>Low</option>
              <option>Medium</option>
              <option>High</option>
              <option>Urgent</option>
            </select></label
          >
          <label class="block"
            >Checklist steps (one per line, optional)<textarea
              v-model="steps"
              rows="4"
              class="block w-full"
            />
          </label>
          <p class="text-xs">
            Each step becomes an ERPNext child Task assigned to the selected
            employee.
          </p>
          <button :disabled="busy" class="rounded bg-blue-700 p-2 text-white">
            Create
          </button>
          <button
            type="button"
            class="ml-3 underline"
            @click="creating = false"
          >
            Cancel
          </button>
        </form>
      </fieldset>
      <p v-if="!busy && !rows.length">No accessible tasks found.</p>
      <button
        v-for="task in rows"
        :key="task.name"
        class="block w-full rounded border p-3 text-left"
        :disabled="busy"
        @click="open(task.name)"
      >
        <span class="block font-semibold">{{ task.subject }}</span>
        <span class="block text-sm"
          >{{ task.status }} ? {{ task.priority }} ? {{ task.project }}</span
        >
        <span v-if="task.is_group" class="block text-xs">Checklist group</span>
        <span v-if="task.exp_end_date" class="block text-xs"
          >Due {{ task.exp_end_date }}</span
        >
      </button>
      <button
        v-if="hasMore"
        :disabled="busy"
        class="underline"
        @click="loadMore"
      >
        Load more
      </button>
    </template>
    <template v-else>
      <button class="underline" :disabled="busy" @click="back">
        Back to tasks
      </button>
      <h3 class="font-semibold">{{ detail.task.subject }}</h3>
      <p>{{ detail.task.status }} ? {{ detail.task.project }}</p>
      <p class="whitespace-pre-wrap text-sm">{{ detail.description }}</p>
      <a
        :href="deskLink(detail.task.name)"
        target="_blank"
        rel="noopener"
        class="block text-blue-700 underline"
        >Open in ERPNext</a
      >
      <p v-if="detail.workflow" class="text-sm">
        This task uses a workflow. Use Open in ERPNext for its workflow actions.
      </p>
      <form
        v-else-if="detail.can_write"
        class="flex gap-2"
        @submit.prevent="saveStatus"
      >
        <select
          v-model="status"
          aria-label="Task status"
          class="min-w-0 flex-1"
        >
          <option v-if="!statuses.includes(status)" :value="status" disabled>
            {{ status }}
          </option>
          <option v-for="s in statuses" :key="s">{{ s }}</option>
        </select>
        <button :disabled="busy" class="rounded bg-blue-700 p-2 text-white">
          Save
        </button>
      </form>
      <div v-if="detail.children.length" class="space-y-2">
        <h4 class="font-semibold">Checklist steps</h4>
        <button
          v-for="child in detail.children"
          :key="child.name"
          class="block w-full rounded border p-2 text-left"
          :disabled="busy"
          @click="open(child.name)"
        >
          {{ child.status === 'Completed' ? '?' : '?' }} {{ child.subject }}
          <span class="block text-xs">{{ child.status }}</span>
        </button>
      </div>
      <p v-if="detail.task.is_group" class="text-xs">
        Only steps assigned to you and permitted by ERPNext are shown. Managers
        can view all permitted steps.
      </p>
      <div v-if="detail.can_write" class="space-y-2">
        <form @submit.prevent="comment">
          <label class="block"
            >Work update<textarea
              v-model="note"
              required
              maxlength="4000"
              class="block w-full"
            /></label
          ><button :disabled="busy || !note.trim()" class="underline">
            Add comment
          </button>
        </form>
        <label class="block"
          >Attach photo<input
            type="file"
            accept="image/jpeg,image/png"
            :disabled="busy"
            class="block w-full text-sm"
            @change="upload"
        /></label>
      </div>
      <ul class="space-y-2">
        <li v-for="file in detail.files" :key="file.name">
          <a
            v-if="safeFile(file.file_url)"
            :href="file.file_url"
            target="_blank"
            rel="noopener"
            class="text-blue-700 underline"
            >{{ file.file_name }}</a
          >
        </li>
      </ul>
      <div
        v-for="c in detail.comments"
        :key="c.name"
        class="border-t pt-2 text-sm"
      >
        <p class="text-xs text-gray-600">
          {{ c.comment_by }} ? {{ c.creation }}
        </p>
        <p class="whitespace-pre-wrap">{{ c.content }}</p>
      </div>
    </template>
  </section>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { createResource } from 'frappe-ui'
import { useRoute } from 'vue-router'
const route = useRoute()
const props = defineProps({ manager: Boolean })
const rows = ref([]),
  detail = ref(null),
  error = ref(''),
  busy = ref(false),
  hasMore = ref(false),
  canManage = ref(false)
const creating = ref(false),
  status = ref('Open'),
  note = ref(''),
  steps = ref('')
const options = reactive({ projects: [], people: [] })
const form = reactive({
  project: '',
  subject: '',
  assignee: '',
  due_date: '',
  priority: 'Medium',
})
const statuses = computed(() => [
  'Open',
  'Working',
  'Pending Review',
  'Completed',
  ...(detail.value?.manager ? ['Cancelled'] : []),
])
const resources = Object.fromEntries(
  [
    'list_tasks',
    'get_task',
    'update_status',
    'task_options',
    'create_task',
    'add_comment',
    'attach_photo',
  ].map((name) => [
    name,
    createResource({ url: `projectit.tasks.${name}`, method: 'POST' }),
  ]),
)
const call = (name, args = {}) => resources[name].submit(args)
async function run(work) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.messages?.join(' ') || e.message || String(e)
  } finally {
    busy.value = false
  }
}
function setDetail(data) {
  detail.value = data
  status.value = data.task.status
  note.value = ''
}
async function list(append = false) {
  const data = await call('list_tasks', {
    mine: props.manager ? 0 : 1,
    start: append ? rows.value.length : 0,
  })
  rows.value = append ? [...rows.value, ...data.tasks] : data.tasks
  hasMore.value = data.has_more
  canManage.value = data.manager
}
const reload = () =>
  run(async () => {
    if (detail.value)
      setDetail(await call('get_task', { name: detail.value.task.name }))
    else await list()
  })
const back = () =>
  run(async () => {
    detail.value = null
    await list()
  })
const open = (name) =>
  run(async () => setDetail(await call('get_task', { name })))
const loadMore = () => run(() => list(true))
const saveStatus = () =>
  run(async () =>
    setDetail(
      await call('update_status', {
        name: detail.value.task.name,
        status: status.value,
        modified: detail.value.task.modified,
      }),
    ),
  )
const comment = () =>
  run(async () =>
    setDetail(
      await call('add_comment', {
        name: detail.value.task.name,
        content: note.value,
      }),
    ),
  )
const openCreate = () =>
  run(async () => {
    Object.assign(options, await call('task_options'))
    creating.value = true
  })
const loadPeople = () =>
  run(async () => {
    form.assignee = ''
    options.people = []
    Object.assign(
      options,
      await call('task_options', { project: form.project }),
    )
  })
const create = () =>
  run(async () => {
    const data = await call('create_task', {
      ...form,
      due_date: form.due_date.replace('T', ' '),
      steps: steps.value
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
    })
    creating.value = false
    form.subject = ''
    steps.value = ''
    setDetail(await call('get_task', { name: data.name }))
  })
const deskLink = (name) => `/desk/task/${encodeURIComponent(name)}`
const safeFile = (url) =>
  typeof url === 'string' && /^\/(private\/)?files\//.test(url)
async function upload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await run(async () => {
    if (file.size > 10 * 1024 * 1024)
      throw new Error('Choose a photo smaller than 10 MB.')
    const content = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result).split(',')[1])
      reader.onerror = () => reject(new Error('Could not read photo.'))
      reader.readAsDataURL(file)
    })
    setDetail(
      await call('attach_photo', { name: detail.value.task.name, content }),
    )
  })
  event.target.value = ''
}
onMounted(() => (route.query.task ? open(String(route.query.task)) : reload()))
</script>
