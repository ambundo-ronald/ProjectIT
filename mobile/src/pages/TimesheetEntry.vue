<template>
    <AttendanceStatus ref="attendanceStatus" />
    <div v-if="uploading" class="flex h-80 items-center justify-center">
        <Spinner class=" h-12"></Spinner>
    </div>
    <div v-else>
        <div class=" pt-7 text-right pr-7" v-if="!showCamera">
            <PrimaryButton @click="cameraMode = actionName; showCamera = true" :disabled="!projectId" :name="actionName"></PrimaryButton>
        </div>
        <div v-if="!showCamera">
            <div v-if="actionName == 'Check-In'">
                <div class=" pt-7 pl-6 pr-6 font-[Inter] font-[600]">
                    <SelectionList :dataList="projectAllocationResource" @select-event="handleProjectSelection($event)"
                        :noData="isProjectAllocated">
                    </SelectionList>
                    <label v-if="projectId" class="mt-3 block text-sm">Task (optional)
                        <select v-model="taskId" class="block w-full" :disabled="taskOptions.loading">
                            <option value="">Project time only</option>
                            <option v-for="task in taskOptions.data || []" :key="task.name" :value="task.name">{{ task.subject }}</option>
                        </select>
                    </label>
                </div>
            </div>
            <div v-else class=" pl-6 pr-6 pt-7 pb-4">
                <div class="bg-[#B9C8EA] pt-3 pb-3 pl-4 pr-3 rounded-t-md flex gap-3">
                    <ProjectOutline class=" h-6 w-6"></ProjectOutline>
                    <p class="text-[#4A6BB6] font-[600] font-[Inter]"> {{ projectName }}</p>
                </div>
                <div
                    class="bg-[#F5F8FF] pl-4 pr-3 pt-5 pb-3 rounded-b-md border-[#B9C8EA] border-x-2 border-b-2 flex flex-col gap-3">
                    <p> Check-In Time : {{ dayjs(timesheetDetails.from_time).format("hh:mm:ss a") }}</p>
                    <div @click="showCaption = true"
                        class="bg-white shadow-[0_4px_4px_rgba(0,0,0,0.25)] rounded-sm pt-3 pb-3 pl-2 pr-2 flex gap-2">
                        <FeatherIcon name="download" class="h-6 w-6" />
                        <p>Project Status Update</p>
                    </div>
                    <div v-if="showCaption" class="text-center flex flex-col gap-3">
                        <textarea v-model="caption"></textarea>
                        <div>
                            <PrimaryButton @click="showCamera = true; cameraMode = 'Upload'" name="Upload">
                            </PrimaryButton>
                        </div>
                    </div>
                </div>
            </div>
            <div class=" pl-6 pr-6 pt-7 pb-4" v-if="projectName != ''">
                <Instructions :instructions="instructions"></Instructions>
                <div class="pt-5">
                    <TeamMembers :members="members"></TeamMembers>
                </div>
            </div>
        </div>
    </div>

    <div v-if="showError">
        <ErrorMessage @dialog-event="showError = $event" :error-message="errorMessage"></ErrorMessage>
    </div>
</template>
<script setup>
import { inject, ref, onMounted, watch } from 'vue'
import { createResource, createListResource, toast, FeatherIcon, Spinner } from 'frappe-ui'
import dayjs from 'dayjs'
import ErrorMessage from '../components/ErrorMessage.vue'
import SelectionList from '../components/SelectionList.vue'
import PrimaryButton from '../components/PrimaryButton.vue'
import AttendanceStatus from '../components/AttendanceStatus.vue'
import ProjectOutline from './icons/ProjectOutline.vue'
import Instructions from './Instructions.vue'
import { get_instructions } from '../data/work_instructions'
import TeamMembers from './TeamMembers.vue'
import { showCamera, cameraMode, imageFile } from '../data/camera_context'

const employee = inject('employee_id')
const projectName = ref('')
const projectId = ref('')
const taskId = ref('')
const timesheetDetails = ref({})
const actionName = ref('Check-In')
const isProjectAllocated = ref(true)
const errorMessage = ref('')
const showError = ref(false)
const showCaption = ref(false)
const caption = ref('')
const instructions = ref({})
const members = ref([])
const uploading = ref(false)
const attendanceStatus = ref(null)
cameraMode.value = 'Check-In'

function reportError(error) {
    errorMessage.value = error.messages?.join(' ') || error.message || String(error)
    showError.value = true
}

const taskOptions = createResource({ url: 'projectit.tasks.work_tasks' })
watch(projectId, async (project) => {
    if (!project) { taskOptions.data = []; return }
    try { await taskOptions.fetch({ project }) } catch (error) { reportError(error) }
})

const activeSession = createResource({ url: 'projectit.attendance.get_active_session' })
const checkInRequest = createResource({ url: 'projectit.attendance.check_in', method: 'POST' })
const checkOutRequest = createResource({ url: 'projectit.attendance.check_out', method: 'POST' })
const photoRequest = createResource({ url: 'projectit.attendance.add_photo', method: 'POST' })
const projectAllocationResource = createResource({
    url: 'projectit.api.get_project_allocation',
    makeParams: () => ({ employee_id: employee.name }),
})
const teamMembers = createResource({
    url: 'projectit.api.get_team_members',
    makeParams: () => ({ project_name: projectName.value }),
    onSuccess(data) { members.value = JSON.parse(data?.[0]?.members || '[]') },
})
const projectResource = createListResource({
    doctype: 'Project', fields: ['name'],
    onSuccess(data) { projectId.value = data?.[0]?.name || '' },
    onError: reportError,
})

async function displayInstructions() {
    instructions.value = await get_instructions(dayjs().format('YYYY-MM-DD'), projectName.value, employee.name)
}

function setSession(data) {
    timesheetDetails.value = data || {}
    taskId.value = data?.task || ''
    projectName.value = data?.project_name || ''
    projectId.value = data?.project || ''
    actionName.value = data ? 'Check-Out' : 'Check-In'
    cameraMode.value = actionName.value
    if (!data) {
        instructions.value = {}
        members.value = []
    }
}

onMounted(async () => {
    try {
        setSession(await activeSession.fetch())
        await projectAllocationResource.fetch()
        isProjectAllocated.value = !!projectAllocationResource.data?.length
        if (projectName.value) await Promise.all([displayInstructions(), teamMembers.fetch()])
    } catch (error) { reportError(error) }
})

async function handleProjectSelection(project_name) {
    projectName.value = project_name
    projectId.value = ''
    taskId.value = ''
    projectResource.update({ filters: { project_name } })
    try {
        await Promise.all([projectResource.fetch(), displayInstructions(), teamMembers.fetch()])
    } catch (error) { reportError(error) }
}

function getLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error('Geolocation is not supported by your device.'))
        navigator.geolocation.getCurrentPosition(
            ({ coords }) => resolve({ latitude: coords.latitude, longitude: coords.longitude }),
            reject,
            { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
        )
    })
}

function readPhoto(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(',')[1])
        reader.onerror = () => reject(new Error('The captured photo could not be read. Please try again.'))
        reader.readAsDataURL(file)
    })
}

watch(imageFile, (file) => {
    if (file instanceof Blob && !uploading.value) handleImageCapture(file)
})

async function handleImageCapture(file) {
    uploading.value = true
    const mode = cameraMode.value
    try {
        const photo = await readPhoto(file)
        if (mode === 'Upload') {
            timesheetDetails.value = await photoRequest.submit({ timesheet: timesheetDetails.value.name, photo, caption: caption.value })
            cameraMode.value = 'Check-Out'
            caption.value = ''
            showCaption.value = false
        } else {
            // No server-side writes take place until GPS has succeeded.
            const location = await getLocation()
            if (mode === 'Check-In') {
                setSession(await checkInRequest.submit({ project: projectId.value, task: taskId.value || null, ...location, photo }))
            } else {
                await checkOutRequest.submit({ timesheet: timesheetDetails.value.name, ...location, photo })
                setSession(null)
            }
            await attendanceStatus.value?.refresh()
        }
        toast({
            title: 'Success', text: mode === 'Upload' ? 'Photo update saved' : mode === 'Check-In' ? 'Checked in' : 'Checked out. Attendance will follow HRMS shift rules.',
            icon: 'check-circle', position: 'bottom-center', iconClasses: 'text-blue-500',
        })
    } catch (error) {
        reportError(error)
    } finally {
        uploading.value = false
    }
}
</script>
