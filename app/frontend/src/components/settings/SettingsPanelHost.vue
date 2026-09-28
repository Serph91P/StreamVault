<template>
  <component
    :is="panels[sectionId]"
    v-for="(state, sectionId) in panelState"
    v-show="sectionId === section"
    :key="sectionId"
    v-bind="state.props"
    v-on="state.listeners"
  />
</template>

<script setup lang="ts">
import { reactive, watchEffect, type Component } from 'vue'
import ApiKeysPanel from './ApiKeysPanel.vue'
import FavoritesSettingsPanel from './FavoritesSettingsPanel.vue'
import NotificationSettingsPanel from './NotificationSettingsPanel.vue'
import ProxySettingsPanel from './ProxySettingsPanel.vue'
import PWAPanel from './PWAPanel.vue'
import RecordingSettingsPanel from './RecordingSettingsPanel.vue'
import TwitchConnectionPanel from './TwitchConnectionPanel.vue'

const props = defineProps<{
  section: string
  panelProps: Record<string, unknown>
  panelListeners: Record<string, (...args: any[]) => any>
}>()

const panels: Record<string, Component> = {
  twitch: TwitchConnectionPanel,
  notifications: NotificationSettingsPanel,
  recording: RecordingSettingsPanel,
  storage: RecordingSettingsPanel,
  favorites: FavoritesSettingsPanel,
  pwa: PWAPanel,
  'api-keys': ApiKeysPanel,
  proxy: ProxySettingsPanel
}
const panelState = reactive<Record<string, {
  props: Record<string, unknown>
  listeners: Record<string, (...args: any[]) => any>
}>>({})

watchEffect(() => {
  panelState[props.section] = {
    props: props.panelProps,
    listeners: props.panelListeners
  }
})
</script>
