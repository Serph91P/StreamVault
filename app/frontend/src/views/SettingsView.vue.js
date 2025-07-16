import { ref, onMounted, computed, watch } from 'vue';
import { useNotificationSettings } from '@/composables/useNotificationSettings';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useWebSocket } from '@/composables/useWebSocket';
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue';
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue';
import FavoritesSettingsPanel from '@/components/settings/FavoritesSettingsPanel.vue';
import PWAPanel from '@/components/settings/PWAPanel.vue';
// Verfügbare Tabs als Array für einfachere Verwaltung
const availableTabs = computed(() => [
    { id: 'notifications', label: 'Notifications' },
    { id: 'recording', label: 'Recording' },
    { id: 'favorites', label: 'Favorite Games' },
    { id: 'pwa', label: 'PWA & Mobile' }
    // { id: 'logging', label: 'Logging & Monitoring' }
]);
const { settings: notificationSettings, fetchSettings: fetchNotificationSettings, updateSettings: updateNotificationSettings, getStreamerSettings: getNotificationStreamerSettings, updateStreamerSettings: updateStreamerNotificationSettings } = useNotificationSettings();
const { settings: recordingSettings, streamerSettings: recordingStreamerSettings, activeRecordings, fetchSettings: fetchRecordingSettings, updateSettings: updateRecordingSettings, fetchStreamerSettings: fetchRecordingStreamerSettings, updateStreamerSettings: updateStreamerRecordingSettings, fetchActiveRecordings, stopRecording, cleanupOldRecordings } = useRecordingSettings();
const activeTab = ref('notifications');
const notificationStreamerSettings = ref([]);
const isLoading = ref(true);
const isSaving = ref(false);
// Poll for active recordings
let pollingInterval = undefined;
onMounted(async () => {
    isLoading.value = true;
    try {
        // Load notification settings
        await fetchNotificationSettings();
        notificationStreamerSettings.value = await getNotificationStreamerSettings();
        // Load recording settings with better error handling
        try {
            await fetchRecordingSettings();
        }
        catch (e) {
            console.error("Failed to load recording settings:", e);
        }
        try {
            await fetchRecordingStreamerSettings();
        }
        catch (e) {
            console.error("Failed to load recording streamer settings:", e);
        }
        try {
            await fetchActiveRecordings();
        }
        catch (e) {
            console.error("Failed to load active recordings:", e);
        }
        // Active recordings are now updated via WebSocket
    }
    catch (error) {
        console.error('Failed to load settings:', error);
    }
    finally {
        isLoading.value = false;
    }
});
// WebSocket integration for real-time active recordings updates  
const { messages } = useWebSocket();
watch(messages, (newMessages) => {
    if (newMessages.length === 0)
        return;
    const latestMessage = newMessages[newMessages.length - 1];
    // Handle active recordings updates via WebSocket
    if (latestMessage.type === 'active_recordings_update') {
        activeRecordings.value = latestMessage.data || [];
    }
    else if (latestMessage.type === 'recording_started' || latestMessage.type === 'recording_stopped') {
        // Refresh when recording state changes
        fetchActiveRecordings();
    }
});
// Notification handlers
const handleUpdateNotificationSettings = async (newSettings) => {
    try {
        isSaving.value = true;
        await updateNotificationSettings(newSettings);
        alert('Notification settings saved successfully!');
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to update notification settings');
    }
    finally {
        isSaving.value = false;
    }
};
const handleUpdateStreamerNotificationSettings = async (streamerId, settings) => {
    try {
        const updatedSettings = await updateStreamerNotificationSettings(streamerId, settings);
        const index = notificationStreamerSettings.value.findIndex(s => s.streamer_id === streamerId);
        if (index !== -1) {
            notificationStreamerSettings.value[index] = {
                ...notificationStreamerSettings.value[index],
                ...updatedSettings
            };
        }
    }
    catch (error) {
        console.error('Failed to update streamer notification settings:', error);
    }
};
const handleTestNotification = async () => {
    try {
        const response = await fetch('/api/settings/test-notification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to send test notification');
        }
        alert('Test notification sent successfully!');
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to send test notification');
    }
};
// Recording handlers
const handleUpdateRecordingSettings = async (newSettings) => {
    try {
        isSaving.value = true;
        await updateRecordingSettings(newSettings);
        alert('Recording settings saved successfully!');
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to update recording settings');
    }
    finally {
        isSaving.value = false;
    }
};
const handleUpdateStreamerRecordingSettings = async (streamerId, settings) => {
    try {
        await updateStreamerRecordingSettings(streamerId, settings);
    }
    catch (error) {
        console.error('Failed to update streamer recording settings:', error);
    }
};
const handleStopRecording = async (streamerId) => {
    try {
        const success = await stopRecording(streamerId);
        if (success) {
            alert('Recording stopped successfully.');
        }
        else {
            alert('Failed to stop recording.');
        }
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to stop recording');
    }
};
const handleCleanupRecordings = async (streamerId) => {
    try {
        const success = await cleanupOldRecordings(streamerId);
        if (success) {
            alert('Old recordings cleaned up successfully.');
        }
        else {
            alert('Failed to clean up recordings.');
        }
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to clean up recordings');
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-container']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-container']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "settings-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "settings-container" },
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-indicator" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-tabs-wrapper" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-tabs" },
    });
    for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.availableTabs))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    __VLS_ctx.activeTab = tab.id;
                } },
            key: (tab.id),
            ...{ class: ({ active: __VLS_ctx.activeTab === tab.id }) },
            ...{ class: "tab-button" },
            'aria-selected': (__VLS_ctx.activeTab === tab.id),
            role: "tab",
        });
        (tab.label);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-content" },
    });
    if (__VLS_ctx.activeTab === 'notifications') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-pane" },
            role: "tabpanel",
        });
        /** @type {[typeof NotificationSettingsPanel, ]} */ ;
        // @ts-ignore
        const __VLS_0 = __VLS_asFunctionalComponent(NotificationSettingsPanel, new NotificationSettingsPanel({
            ...{ 'onUpdateSettings': {} },
            ...{ 'onUpdateStreamerSettings': {} },
            ...{ 'onTestNotification': {} },
            settings: (__VLS_ctx.notificationSettings || {
                notification_url: '',
                notifications_enabled: true,
                apprise_docs_url: '',
                notify_online_global: true,
                notify_offline_global: true,
                notify_update_global: true,
                notify_favorite_category_global: false
            }),
            streamerSettings: (__VLS_ctx.notificationStreamerSettings),
        }));
        const __VLS_1 = __VLS_0({
            ...{ 'onUpdateSettings': {} },
            ...{ 'onUpdateStreamerSettings': {} },
            ...{ 'onTestNotification': {} },
            settings: (__VLS_ctx.notificationSettings || {
                notification_url: '',
                notifications_enabled: true,
                apprise_docs_url: '',
                notify_online_global: true,
                notify_offline_global: true,
                notify_update_global: true,
                notify_favorite_category_global: false
            }),
            streamerSettings: (__VLS_ctx.notificationStreamerSettings),
        }, ...__VLS_functionalComponentArgsRest(__VLS_0));
        let __VLS_3;
        let __VLS_4;
        let __VLS_5;
        const __VLS_6 = {
            onUpdateSettings: (__VLS_ctx.handleUpdateNotificationSettings)
        };
        const __VLS_7 = {
            onUpdateStreamerSettings: (__VLS_ctx.handleUpdateStreamerNotificationSettings)
        };
        const __VLS_8 = {
            onTestNotification: (__VLS_ctx.handleTestNotification)
        };
        var __VLS_2;
    }
    if (__VLS_ctx.activeTab === 'recording') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-pane" },
            role: "tabpanel",
        });
        /** @type {[typeof RecordingSettingsPanel, ]} */ ;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent(RecordingSettingsPanel, new RecordingSettingsPanel({
            ...{ 'onUpdate': {} },
            ...{ 'onUpdateStreamer': {} },
            ...{ 'onStopRecording': {} },
            ...{ 'onCleanupRecordings': {} },
            settings: (__VLS_ctx.recordingSettings),
            streamerSettings: (__VLS_ctx.recordingStreamerSettings),
            activeRecordings: (__VLS_ctx.activeRecordings),
        }));
        const __VLS_10 = __VLS_9({
            ...{ 'onUpdate': {} },
            ...{ 'onUpdateStreamer': {} },
            ...{ 'onStopRecording': {} },
            ...{ 'onCleanupRecordings': {} },
            settings: (__VLS_ctx.recordingSettings),
            streamerSettings: (__VLS_ctx.recordingStreamerSettings),
            activeRecordings: (__VLS_ctx.activeRecordings),
        }, ...__VLS_functionalComponentArgsRest(__VLS_9));
        let __VLS_12;
        let __VLS_13;
        let __VLS_14;
        const __VLS_15 = {
            onUpdate: (__VLS_ctx.handleUpdateRecordingSettings)
        };
        const __VLS_16 = {
            onUpdateStreamer: (__VLS_ctx.handleUpdateStreamerRecordingSettings)
        };
        const __VLS_17 = {
            onStopRecording: (__VLS_ctx.handleStopRecording)
        };
        const __VLS_18 = {
            onCleanupRecordings: (__VLS_ctx.handleCleanupRecordings)
        };
        var __VLS_11;
    }
    if (__VLS_ctx.activeTab === 'favorites') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-pane" },
            role: "tabpanel",
        });
        /** @type {[typeof FavoritesSettingsPanel, ]} */ ;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent(FavoritesSettingsPanel, new FavoritesSettingsPanel({}));
        const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
    }
    if (__VLS_ctx.activeTab === 'pwa') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-pane" },
            role: "tabpanel",
        });
        /** @type {[typeof PWAPanel, ]} */ ;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent(PWAPanel, new PWAPanel({}));
        const __VLS_23 = __VLS_22({}, ...__VLS_functionalComponentArgsRest(__VLS_22));
    }
}
/** @type {__VLS_StyleScopedClasses['settings-view']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-container']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-pane']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-pane']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-pane']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-pane']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            NotificationSettingsPanel: NotificationSettingsPanel,
            RecordingSettingsPanel: RecordingSettingsPanel,
            FavoritesSettingsPanel: FavoritesSettingsPanel,
            PWAPanel: PWAPanel,
            availableTabs: availableTabs,
            notificationSettings: notificationSettings,
            recordingSettings: recordingSettings,
            recordingStreamerSettings: recordingStreamerSettings,
            activeRecordings: activeRecordings,
            activeTab: activeTab,
            notificationStreamerSettings: notificationStreamerSettings,
            isLoading: isLoading,
            handleUpdateNotificationSettings: handleUpdateNotificationSettings,
            handleUpdateStreamerNotificationSettings: handleUpdateStreamerNotificationSettings,
            handleTestNotification: handleTestNotification,
            handleUpdateRecordingSettings: handleUpdateRecordingSettings,
            handleUpdateStreamerRecordingSettings: handleUpdateStreamerRecordingSettings,
            handleStopRecording: handleStopRecording,
            handleCleanupRecordings: handleCleanupRecordings,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
