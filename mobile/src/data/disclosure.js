/**
 * Telling people what the app does with their location and camera before Android asks for the permission (Google
 * Play's "prominent disclosure" rule). Shown once per phone for each kind, in the phone app only.
 */
import { reactive } from 'vue'
import { isNative } from './native'

export const DISCLOSURES = {
  location: {
    title: 'Your location at check-in',
    icon: 'map-pin',
    text: 'Techy App records your precise location when you check in and check out at a site, so your company knows you were there. It is taken only at that moment, never in the background, and is sent only to your company’s Techy site.',
    next: 'Next, your phone asks to allow location. Choose “While using the app”.',
    refused: 'Your location is needed to check in and out. You can still use the rest of the app.',
  },
  camera: {
    title: 'Using the camera',
    icon: 'camera',
    text: 'Techy App uses the camera for the photos you choose to take: check-in photos, photos of the work, readings and receipts. Photos are sent only to your company’s Techy site.',
    next: 'Next, your phone asks to allow the camera.',
    refused: 'The camera is needed to take photos. You can still choose a photo from the phone instead.',
  },
}

export const disclosure = reactive({ kind: '', open: false })
let resolve = null
const key = (kind) => `techy_disclosed_${kind}`

/** Resolves true to carry on, false if the person chose Not now. */
export function askOnce(kind) {
  if (!isNative) return Promise.resolve(true)
  try {
    if (localStorage.getItem(key(kind))) return Promise.resolve(true)
  } catch (e) {
    /* storage blocked: ask each time */
  }
  return new Promise((r) => {
    resolve = r
    Object.assign(disclosure, { kind, open: true })
  })
}

export function answer(ok) {
  if (ok) {
    try {
      localStorage.setItem(key(disclosure.kind), '1')
    } catch (e) {
      /* asked again next time */
    }
  }
  disclosure.open = false
  resolve?.(ok)
  resolve = null
}
