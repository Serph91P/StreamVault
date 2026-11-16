import { readonly, ref } from 'vue'
import type { RegisterSWOptions } from 'vite-plugin-pwa/types'

// Page-owned, memory-only: settings can unmount without losing an update.
const pending = ref(false)
export const pwaUpdateAvailable = readonly(pending)
let updateWorker: ((reload?: boolean) => Promise<void>) | undefined
let activated = false
let destination: string | undefined
let navigating = false

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
  if (!pending.value || !updateWorker) return false
  destination = target
  try {
    if (activated) finishUpdate()
    else await updateWorker(true)
  } catch (error) {
    destination = undefined
    throw error
  }
  return true
}
