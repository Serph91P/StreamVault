<template>
  <div v-if="showInstallPrompt" class="install-prompt">
    <div class="install-prompt__content">
      <div class="install-prompt__icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="currentColor"/>
        </svg>
      </div>
      <div class="install-prompt__text">
        <h3>{{ installText }}</h3>
        <p>{{ installDescription }}</p>
      </div>
      <div class="install-prompt__actions">
        <BaseButton variant="secondary" size="sm" @click="openPwaSettings">Setup guide</BaseButton>
        <BaseButton variant="primary" size="sm" @click="installApp">Install</BaseButton>
        <BaseButton variant="outline" size="sm" @click="dismissPrompt">Not now</BaseButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePWA } from '@/composables/usePWA'
import { appStorage } from '@/services/storage'
import BaseButton from '@/components/base/BaseButton.vue'

const { isInstallable, isInstalled, installPWA } = usePWA()
const router = useRouter()
const showInstallPrompt = ref(false)
const hasBeenDismissed = ref(appStorage.pwaInstallDismissed === 'true')

const showTimeout = ref<ReturnType<typeof setTimeout> | null>(null)
const dismissResetTimeout = ref<ReturnType<typeof setTimeout> | null>(null)

const installText = computed(() => {
  return 'Install StreamVault App'
})

const installDescription = computed(() => {
  return 'Install for offline shell access, safe mobile spacing, and a dedicated app experience.'
})

onMounted(() => {
  hasBeenDismissed.value = appStorage.pwaInstallDismissed === 'true'
})

watch(isInstallable, (installable) => {
  if (showTimeout.value) {
    clearTimeout(showTimeout.value)
    showTimeout.value = null
  }

  if (!installable || isInstalled.value || hasBeenDismissed.value) {
    showInstallPrompt.value = false
    return
  }

  if (installable && !isInstalled.value && !hasBeenDismissed.value && !showInstallPrompt.value) {
    showTimeout.value = setTimeout(() => {
      if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value) {
        showInstallPrompt.value = true
      }
      showTimeout.value = null
    }, 3000)
  }
}, { immediate: true })

onUnmounted(() => {
  if (showTimeout.value) clearTimeout(showTimeout.value)
  if (dismissResetTimeout.value) clearTimeout(dismissResetTimeout.value)
})

const installApp = async () => {
  try {
    await installPWA()
    showInstallPrompt.value = false
  } catch (error) {
    console.error('Installation failed:', error)
  }
}

const openPwaSettings = () => {
  showInstallPrompt.value = false
  router.push({ path: '/settings', query: { section: 'pwa' } })
}

const dismissPrompt = () => {
  showInstallPrompt.value = false
  hasBeenDismissed.value = true
  appStorage.setPwaInstallDismissed(true)
  dismissResetTimeout.value = setTimeout(() => {
    appStorage.clearPwaInstallDismissed()
  }, 7 * 24 * 60 * 60 * 1000)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.install-prompt {
  position: fixed;
  bottom: calc(v.$spacing-6 + env(safe-area-inset-bottom, 0px));
  left: v.$spacing-6;
  right: v.$spacing-6;
  border: 1px solid var(--glass-border-hover);
  background: linear-gradient(135deg, var(--glass-bg-strong), var(--background-card));
  border-radius: v.$border-radius-lg;
  box-shadow: var(--glass-shadow-lg), 0 18px 44px rgba(0, 0, 0, 0.42);
  z-index: 1000;
  animation: slideUp v.$duration-300 v.$vue-ease-out;
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));

  @include m.respond-to('md') {
    bottom: v.$spacing-6;
    left: auto;
    max-width: 400px;
  }
}

.install-prompt__content {
  display: flex;
  align-items: center;
  // Icon + text share the first row; the action buttons wrap onto their own
  // row - all three never fit next to the text within the 400px card.
  flex-wrap: wrap;
  padding: v.$spacing-4;
  gap: v.$spacing-3;
}

.install-prompt__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 1px solid rgba(145, 71, 255, 0.42);
  border-radius: var(--radius-full);
  background: rgba(145, 71, 255, 0.16);
  color: var(--accent-color);
  flex-shrink: 0;
}

.install-prompt__text {
  flex: 1;
  min-width: 0;
}

.install-prompt__text h3 {
  margin: 0 0 v.$spacing-1 0;
  font-size: v.$text-base;
  font-weight: v.$font-semibold;
  color: var(--text-primary);
}

.install-prompt__text p {
  margin: 0;
  font-size: v.$text-sm;
  color: var(--text-secondary);
}

.install-prompt__actions {
  display: flex;
  gap: v.$spacing-2;
  flex-basis: 100%;
  justify-content: flex-end;
  flex-wrap: wrap;
}

@keyframes slideUp {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Mobile-only layout adjustments */
@include m.respond-below('md') {
  .install-prompt {
    bottom: calc(68px + env(safe-area-inset-bottom, 0px) + v.$spacing-3);
    left: max(v.$spacing-3, env(safe-area-inset-left, 0px));
    right: max(v.$spacing-3, env(safe-area-inset-right, 0px));
    margin: v.$spacing-2;
    border-radius: v.$border-radius-lg;
  }

  .install-prompt__content {
    padding: v.$spacing-4;
    flex-direction: column;
    text-align: center;
  }

  .install-prompt__icon {
    margin: 0 0 v.$spacing-3 0;
  }

  .install-prompt__actions {
    margin-top: v.$spacing-4;
    justify-content: center;
    flex-direction: column;
    width: 100%;

    :deep(.btn) {
      width: 100%;
    }
  }
}
</style>
