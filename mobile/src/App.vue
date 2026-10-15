<template>
  <Toasts />
  <router-view />
  <ChatDock />
  <StatusModal v-model="statusDialog.open" />
  <Camera v-if="showCamera" :mode="cameraMode" @close-event="showCamera = false" @capture-event="imageFile = $event" />
</template>
<script setup>
import { watch, inject } from 'vue'
import { Toasts } from 'frappe-ui'
import Camera from './components/Camera.vue'
import ChatDock from './components/ChatDock.vue'
import StatusModal from './components/ops/StatusModal.vue'
import { statusDialog } from './data/presence'
import { startOffline } from './data/offline'

startOffline()
import { showCamera, cameraMode, imageFile } from './data/camera_context'

const employeeId = inject('employee_id')

watch(employeeId, () => {
  localStorage.setItem('employee_id', JSON.stringify(employeeId))
})
</script>
