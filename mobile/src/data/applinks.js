/**
 * Links that open the phone app instead of the browser.
 *
 * Two kinds of link reach the app (see android/app/src/main/AndroidManifest.xml):
 * - https://<company site>/techy-app/<screen>: Android App Links. Android checks the site's
 *   /.well-known/assetlinks.json (projectit.app_links) and then opens such links straight in the app.
 * - techyapp://open?site=<company site>&path=<screen>: what the website's "Open in the app" bar uses
 *   (components/OpenInApp.vue). It works for every company's site, with no setup on the site.
 *
 * The app opens the screen if it is signed in to that site; otherwise it switches to that site and asks the person
 * to sign in first, then opens the screen.
 */
import { isNative, server, normalizeUrl, chooseServer, signOut } from './native'

export const AFTER_LOGIN = 'techy_after_login'

/** Remember where to go after signing in (a link, or a screen the person tried to open while signed out). */
export function rememberTarget(path) {
  try {
    if (safePath(path)) sessionStorage.setItem(AFTER_LOGIN, path)
  } catch (e) {
    /* storage blocked: Home after signing in */
  }
}
export function takeTarget() {
  try {
    const path = sessionStorage.getItem(AFTER_LOGIN)
    sessionStorage.removeItem(AFTER_LOGIN)
    return safePath(path)
  } catch (e) {
    return ''
  }
}

/** Only the app's own screens: "/ops/work-orders/X?y=1", never another site or a protocol. */
export function safePath(path) {
  const value = String(path || '')
  return /^\/(?!\/)[\w\-./?=&%:+~]*$/.test(value) && !value.startsWith('/account/login') ? value : ''
}

/** { site, path } for a link to the app, or null. */
export function parseLink(url) {
  try {
    const u = new URL(url)
    if (u.protocol === 'techyapp:') {
      return { site: normalizeUrl(u.searchParams.get('site')), path: safePath(u.searchParams.get('path')) || '/' }
    }
    if (u.protocol === 'https:') {
      const m = u.pathname.match(/^\/techy-app(\/.*)?$/)
      if (m) return { site: `${u.protocol}//${u.host}`, path: safePath((m[1] || '/') + u.search) || '/' }
    }
  } catch (e) {
    /* not a URL */
  }
  return null
}

async function open(url, router) {
  const link = parseLink(url)
  if (!link?.site) return
  if (server.url === link.site) {
    if (server.token) return router.push(link.path)
    rememberTarget(link.path)
    return router.replace({ name: 'Login' })
  }
  const host = link.site.replace(/^https:\/\//, '')
  if (server.token && !window.confirm(`This link is for ${host}. Sign out of ${server.company || server.url} and open it?`)) return
  if (server.token) await signOut()
  try {
    await chooseServer(link.site)
  } catch (e) {
    window.alert(e.message)
    return
  }
  rememberTarget(link.path)
  router.replace({ name: 'Login' })
}

let started = false
/** In the phone app: open links the app was started with, or that arrive while it runs. */
export async function startAppLinks(router) {
  if (!isNative || started) return
  started = true
  try {
    const { App } = await import('@capacitor/app')
    App.addListener('appUrlOpen', ({ url }) => open(url, router).catch(() => {}))
    const launch = await App.getLaunchUrl()
    if (launch?.url) {
      await router.isReady()
      open(launch.url, router).catch(() => {})
    }
  } catch (e) {
    /* the App plugin is missing: links open the app's home screen */
  }
}

/** The website's "Open in the app" link for the screen being shown (Android Chrome opens the installed app, or the
 *  Play Store when it is not installed). */
export function intentLink(path, pkg, fallback) {
  const site = window.location.origin
  const query = `site=${encodeURIComponent(site)}&path=${encodeURIComponent(path)}`
  const back = fallback ? `;S.browser_fallback_url=${encodeURIComponent(fallback)}` : ''
  return `intent://open?${query}#Intent;scheme=techyapp;package=${pkg}${back};end`
}
