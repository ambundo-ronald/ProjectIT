import router from '@/router'
import { computed, reactive, ref } from 'vue'
import { createResource } from 'frappe-ui'

import { userResource } from './user'
import { isNative, server } from './native'

export function sessionUser() {
  // The phone app has no session cookie: it is signed in while it holds a token (data/native.js).
  if (isNative) return server.token ? server.user : null
  const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  let _sessionUser = cookies.get('user_id')
  if (_sessionUser === 'Guest') {
    _sessionUser = null
  }
  return _sessionUser
}

/** The signed-in person's full name and user id, for greetings and the menu. */
export function whoAmI() {
  if (isNative) return { fullName: server.full_name || '', userId: server.user || '' }
  const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  const fullName = cookies.get('full_name') || ''
  return { fullName: fullName === 'Guest' ? '' : fullName, userId: cookies.get('user_id') || '' }
}

export const session = reactive({
  login: createResource({
    url: 'login',
    method: 'POST',
    makeParams({ email, password }) {
      return {
        usr: email,
        pwd: password,
      }
    },
    onSuccess(data) {
      try {
        sessionStorage.setItem('techy_signed_in', '1')
      } catch (e) {
        /* storage blocked: Home simply shows the apps */
      }
      userResource.reload()
      session.user = sessionUser()
      session.login.reset()
      router.replace(data.default_route || '/home')
    },
    onError(error){
      if(error.exc_type  == "AuthenticationError"){
        showAuthenticationError.value = true
      } 
    }
  }),
  logout: createResource({
    url: 'frappe.handler.logout',
    method: 'POST',
    onSuccess() {
      userResource.reset()
      session.user = sessionUser()
      router.replace({ name: 'Login' })
    },
  }),
  user: sessionUser(),
  isLoggedIn: computed(() => !!session.user),
})

export const showAuthenticationError = ref(false);