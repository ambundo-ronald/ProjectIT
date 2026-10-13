<template>
  <Toasts />
  <router-view />
  <ChatDock />
  <Camera v-if="showCamera" :mode="cameraMode" @close-event="showCamera = false" @capture-event="imageFile = $event" />
</template>
<script setup>
import { watch, inject } from 'vue'
import { Toasts } from 'frappe-ui'
import Camera from './components/Camera.vue'
import ChatDock from './components/ChatDock.vue'
import { showCamera, cameraMode, imageFile } from './data/camera_context'

const employeeId = inject('employee_id')

watch(employeeId, () => {
  localStorage.setItem('employee_id', JSON.stringify(employeeId))
})
</script>
