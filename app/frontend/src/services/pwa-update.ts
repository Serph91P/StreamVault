import { readonly, ref } from 'vue'
import type { RegisterSWOptions } from 'vite-plugin-pwa/types'

// Page-owned, memory-only: settings can unmount without losing an update.
const pending = ref(false)
export const pwaUpdateAvailable = readonly(pending)
let updateWorker: ((reload?: boolean) => Promise<void>) | undefined
let activated = false
let destination: string | undefined
let navigating = false
let registration: ServiceWorkerRegistration | undefined

function finishUpdate() {
  if (!activated || destination === undefined || navigating) return
  navigating = true
  pending.value = false
  // Assigning the current URL with a hash is only a same-document navigation.
  if (destination === window.location.href) window.location.reload()
  else window.location.assign(destination)
}

export function initializePWAUpdates(register: (options: RegisterSWOptions) => (reload?: boolean) => Promise<void>) {
  if (updateWorker) return
  updateWorker = register({
    onRegisteredSW(_url, value) { registration = value },
    onNeedRefresh() { pending.value = true },
    onNeedReload() {
      // Foreign activation is not consent to discard this tab's form/playback.
      activated = true
      pending.value = true
      finishUpdate()
    },
    onRegisterError(error) {
      console.error('Service Worker registration failed:', error)
    },
  })
}

// Only an explicit Update now or a successful login supplies this boundary.
export async function applyPWAUpdate(target = window.location.href): Promise<boolean> {
  if (destination !== undefined) return true
  if ((!pending.value && !registration?.waiting) || !updateWorker) return false
  // Native waiting precedes Workbox's delayed prompt event. A successful login
  // may win that race; consume the real waiting worker, not stale callback state.
  pending.value = true
  destination = target
  const controllerChanged = () => {
    activated = true
    finishUpdate()
  }
  try {
    if (activated) finishUpdate()
    else {
      // Workbox installs its controlling listener only after prompting. Observe
      // native control too when deliberate activation precedes that notification.
      navigator.serviceWorker?.addEventListener('controllerchange', controllerChanged, { once: true })
      await updateWorker(true)
    }
  } catch (error) {
    navigator.serviceWorker?.removeEventListener('controllerchange', controllerChanged)
    destination = undefined
    throw error
  }
  return true
}
