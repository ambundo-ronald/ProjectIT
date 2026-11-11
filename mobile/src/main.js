import './index.css'
import './data/theme'

import { createApp, reactive } from 'vue'
import router from './router'
import App from './App.vue'

import {
  Button,
  Card,
  Input,
  setConfig,
  frappeRequest,
  resourcesPlugin,
} from 'frappe-ui'

let employeeId = localStorage.getItem("employee_id")
if(!employeeId){
  const employeeIdJSON = JSON.stringify({
    name : ''
  })
  localStorage.setItem("employee_id",employeeIdJSON)
  employeeId = {
    name : ''
  }
} else {
  employeeId = JSON.parse(employeeId)
}
const employee = reactive(employeeId)

import { isNative, signIn, signOut, startNative } from './data/native'
import { request } from './data/request'

let app = createApp(App)

// In the phone app, frappe-ui resources go to the company's site with this phone's token (data/native.js).
async function nativeFetcher({ url, params }) {
  if (url === 'login') {
    await signIn(params.usr, params.pwd)
    return { default_route: '/home' }
  }
  if (url === 'frappe.handler.logout') {
    await signOut()
    return {}
  }
  return request(url, params || {})
}
setConfig('resourceFetcher', isNative ? nativeFetcher : frappeRequest)
startNative()

app.use(router)
app.use(resourcesPlugin)

app.component('Button', Button)
app.component('Card', Card)
app.component('Input', Input)

app.provide("employee_id",employee)

app.mount('#app')

// const registerServiceWorker = async () => {

// 	if ("serviceWorker" in navigator) {
// 		// let serviceWorkerURL = "/public/sw.js"
// 		let serviceWorkerURL = "/assets/projectit/projectit/sw.js"
// 		let config = ""

// 		navigator.serviceWorker
// 			.register(serviceWorkerURL, {
// 				type: "classic",
// 			})
// 			.then((registration) => {
// 				if (config) {
//           console.log("Service Worker Initialised")
// 				}
// 			})
// 			.catch((err) => {
// 				console.error("Failed to register service worker", err)
// 			})
// 	} else {
// 		console.error("Service worker not enabled/supported by the browser")
// 	}
// }

// router.isReady().then(async () => {
//   registerServiceWorker()
//   app.mount('#app')
// })
