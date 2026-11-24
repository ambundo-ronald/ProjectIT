/**
 * Keeping the phone app up to date (Play Store installs).
 *
 * - Play updates installed apps on its own, usually within a day or two when the phone is on Wi-Fi and charging.
 * - On top of that, each time the app opens it asks Play whether a newer version exists (Play's in-app update), and
 *   shows a bar: *Update*, which downloads in the background, then *Restart*.
 * - The company's site says which app version it needs at least (min_app_version, projectit.app_links). An older app
 *   asks Play for its full-screen update straight away; if Play cannot (an app installed from an APK), the bar says an
 *   update is needed and opens the Play Store.
 */
import { reactive } from 'vue'
import { isNative, APP_VERSION } from './native'

/** state: '' (nothing to do), 'available', 'downloading', 'ready' (downloaded: restart to install). */
export const update = reactive({ state: '', required: false, version: '', progress: 0, playUrl: '' })

/** True when version a is newer than b ("1.10.0" > "1.9.2"). */
export function newer(a, b) {
  const pa = String(a || '').split('.').map((n) => parseInt(n, 10) || 0)
  const pb = String(b || '').split('.').map((n) => parseInt(n, 10) || 0)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0)
  }
  return false
}

async function plugin() {
  try {
    return await import('@capawesome/capacitor-app-update')
  } catch (e) {
    return null
  }
}

let checked = false
/** Once per app start, after the company's site answered hello (it says the oldest app it works with). */
export async function checkForUpdate(hello = {}) {
  if (!isNative || checked) return
  checked = true
  update.playUrl = hello.play_url || ''
  const required = !!hello.min_app_version && newer(hello.min_app_version, APP_VERSION)
  const p = await plugin()
  let info = null
  try {
    info = p ? await p.AppUpdate.getAppUpdateInfo() : null
  } catch (e) {
    info = null // not installed from Play (an APK), or Play unavailable
  }
  const available = info && [p.AppUpdateAvailability.UPDATE_AVAILABLE, p.AppUpdateAvailability.UPDATE_IN_PROGRESS].includes(info.updateAvailability)
  if (available && required && info.immediateUpdateAllowed) {
    try {
      await p.AppUpdate.performImmediateUpdate() // Play's own full-screen update; the app restarts when done
      return
    } catch (e) {
      /* the person closed it: the bar below stays */
    }
  }
  if (available || required) Object.assign(update, { state: 'available', required, version: info?.availableVersionName || '' })
}

/** Download in the background (Play), or open the Play Store when Play cannot update in place. */
export async function startUpdate() {
  const p = await plugin()
  try {
    const info = await p.AppUpdate.getAppUpdateInfo()
    if (!info.flexibleUpdateAllowed) throw new Error('flexible update not allowed')
    await p.AppUpdate.addListener('onFlexibleUpdateStateChange', (s) => {
      if (s.installStatus === p.FlexibleUpdateInstallStatus.DOWNLOADED) update.state = 'ready'
      else if (s.installStatus === p.FlexibleUpdateInstallStatus.DOWNLOADING) {
        update.state = 'downloading'
        update.progress = s.totalBytesToDownload ? Math.round((100 * s.bytesDownloaded) / s.totalBytesToDownload) : 0
      } else if ([p.FlexibleUpdateInstallStatus.FAILED, p.FlexibleUpdateInstallStatus.CANCELED].includes(s.installStatus)) update.state = 'available'
    })
    update.state = 'downloading'
    await p.AppUpdate.startFlexibleUpdate()
  } catch (e) {
    update.state = 'available'
    await openStore(p)
  }
}

/** Install the downloaded update (the app restarts). */
export async function finishUpdate() {
  const p = await plugin()
  await p?.AppUpdate.completeFlexibleUpdate()
}

async function openStore(p) {
  try {
    await p.AppUpdate.openAppStore()
  } catch (e) {
    if (update.playUrl) {
      const { openExternal } = await import('./native')
      openExternal(update.playUrl)
    }
  }
}
