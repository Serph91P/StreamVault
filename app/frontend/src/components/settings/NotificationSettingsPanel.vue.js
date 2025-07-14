import { ref, computed, onUnmounted } from 'vue';
// Props
const props = defineProps({
    settings: {
        type: Object,
        required: true
    },
    streamerSettings: {
        type: Array,
        required: true
    }
});
// Typed version of streamerSettings to fix TS errors
const typedStreamerSettings = computed(() => {
    return props.streamerSettings;
});
// Emits
const emit = defineEmits(['update-settings', 'update-streamer-settings', 'test-notification']);
// Data kopieren, um sie im Formular zu verwenden
const data = ref({
    notificationUrl: props.settings.notification_url || '',
    notificationsEnabled: props.settings.notifications_enabled !== false,
    notifyOnlineGlobal: props.settings.notify_online_global !== false,
    notifyOfflineGlobal: props.settings.notify_offline_global !== false,
    notifyUpdateGlobal: props.settings.notify_update_global !== false,
    notifyFavoriteCategoryGlobal: props.settings.notify_favorite_category_global !== false
});
// Add these new refs for validation
const showValidationError = ref(false);
const inputTimeout = ref(null);
const showTooltip = ref(false);
let tooltipTimeout = undefined;
// Handle input with debounce
const handleInput = () => {
    // Clear existing timeout
    if (inputTimeout.value) {
        clearTimeout(inputTimeout.value);
    }
    // Set a new timeout to show validation after typing stops
    inputTimeout.value = window.setTimeout(() => {
        showValidationError.value = true;
    }, 1000); // Show validation error 1 second after typing stops
};
// Handle blur event (when user clicks outside the input)
const handleBlur = () => {
    if (inputTimeout.value) {
        clearTimeout(inputTimeout.value);
    }
    showValidationError.value = true;
};
const handleTooltipMouseEnter = () => {
    if (tooltipTimeout) {
        window.clearTimeout(tooltipTimeout);
        tooltipTimeout = undefined;
    }
    showTooltip.value = true;
};
const handleTooltipMouseLeave = () => {
    tooltipTimeout = window.setTimeout(() => {
        showTooltip.value = false;
    }, 300);
};
// Cleanup timeout on component unmount
onUnmounted(() => {
    if (inputTimeout.value) {
        clearTimeout(inputTimeout.value);
    }
    if (tooltipTimeout) {
        window.clearTimeout(tooltipTimeout);
    }
});
// Validierung und Speichern
const KNOWN_SCHEMES = [
    'discord', 'telegram', 'tgram', 'slack', 'pushover', 'mailto',
    'ntfy', 'matrix', 'twilio', 'msteams', 'slack', 'gchat', 'ligne',
    'signal', 'whatsapp', 'rocket', 'pushbullet', 'apprise', 'http',
    'https', 'twitter', 'slack', 'dbus'
];
const isSaving = ref(false);
const isValidNotificationUrl = computed(() => {
    const url = data.value.notificationUrl.trim();
    // Empty URL is considered valid (though not for saving)
    if (!url)
        return true;
    // Handle multiple URLs separated by comma
    if (url.includes(',')) {
        return url.split(',')
            .every((part) => {
            const trimmedPart = part.trim();
            return trimmedPart === '' || validateSingleUrl(trimmedPart);
        });
    }
    return validateSingleUrl(url);
});
const validateSingleUrl = (url) => {
    // Basic URL structure check
    if (!url.includes('://'))
        return false;
    // Extract scheme
    const scheme = url.split('://')[0].toLowerCase();
    // Check against known schemes
    if (KNOWN_SCHEMES.includes(scheme))
        return true;
    // Allow custom schemes that follow the pattern: xxx://
    return /^[a-zA-Z]+:\/\/.+/.test(url);
};
// Can Save Computed
const canSave = computed(() => {
    return isValidNotificationUrl.value &&
        (data.value.notificationUrl.trim() !== '' || !data.value.notificationsEnabled);
});
// Aktionen
const saveSettings = async () => {
    if (isSaving.value)
        return;
    try {
        isSaving.value = true;
        emit('update-settings', {
            notification_url: data.value.notificationUrl,
            notifications_enabled: data.value.notificationsEnabled,
            notify_online_global: data.value.notifyOnlineGlobal,
            notify_offline_global: data.value.notifyOfflineGlobal,
            notify_update_global: data.value.notifyUpdateGlobal,
            notify_favorite_category_global: data.value.notifyFavoriteCategoryGlobal
        });
    }
    catch (error) {
        console.error('Failed to save settings:', error);
    }
    finally {
        isSaving.value = false;
    }
};
const updateStreamerSettings = (streamerId, settings) => {
    emit('update-streamer-settings', streamerId, settings);
};
const toggleAllForStreamer = (streamerId, enabled) => {
    if (!streamerId)
        return;
    const settingsUpdate = {
        notify_online: enabled,
        notify_offline: enabled,
        notify_update: enabled
    };
    emit('update-streamer-settings', streamerId, settingsUpdate);
};
const toggleAllStreamers = (enabled) => {
    if (!props.streamerSettings)
        return;
    for (const streamer of typedStreamerSettings.value) {
        if (!streamer?.streamer_id)
            continue;
        toggleAllForStreamer(streamer.streamer_id, enabled);
    }
};
const testNotification = () => {
    emit('test-notification');
};
const testWebSocketNotification = async () => {
    try {
        const response = await fetch('/api/settings/test-websocket-notification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to send test WebSocket notification');
        }
        alert('Test WebSocket notification sent! Check the notification bell.');
    }
    catch (error) {
        alert(error instanceof Error ? error.message : 'Failed to send test WebSocket notification');
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['table-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['table-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['actions-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-group']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "settings-form" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "input-with-tooltip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    ...{ onFocus: (...[$event]) => {
            __VLS_ctx.showTooltip = true;
        } },
    ...{ onInput: (__VLS_ctx.handleInput) },
    ...{ onBlur: (__VLS_ctx.handleBlur) },
    placeholder: "e.g., discord://webhook1,telegram://bot_token/chat_id",
    ...{ class: "form-control" },
    ...{ class: ({ 'is-invalid': __VLS_ctx.showValidationError && !__VLS_ctx.isValidNotificationUrl && __VLS_ctx.data.notificationUrl.trim() }) },
});
(__VLS_ctx.data.notificationUrl);
if (__VLS_ctx.showValidationError && !__VLS_ctx.isValidNotificationUrl && __VLS_ctx.data.notificationUrl.trim()) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "invalid-feedback" },
    });
}
if (__VLS_ctx.showTooltip) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onMouseenter: (__VLS_ctx.handleTooltipMouseEnter) },
        ...{ onMouseleave: (__VLS_ctx.handleTooltipMouseLeave) },
        ...{ class: "tooltip-wrapper" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tooltip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
        ...{ onClick: () => { } },
        href: "https://github.com/caronc/apprise/wiki#notification-services",
        target: "_blank",
        rel: "noopener noreferrer",
        ...{ class: "tooltip-link" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    type: "checkbox",
});
(__VLS_ctx.data.notificationsEnabled);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "checkbox-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.saveSettings) },
    ...{ class: "btn btn-primary" },
    disabled: (__VLS_ctx.isSaving || !__VLS_ctx.canSave),
});
(__VLS_ctx.isSaving ? 'Saving...' : 'Save Settings');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.testNotification) },
    ...{ class: "btn btn-secondary" },
    disabled: (!__VLS_ctx.data.notificationsEnabled || !__VLS_ctx.data.notificationUrl),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.testWebSocketNotification) },
    ...{ class: "btn btn-secondary" },
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streamer-notifications" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.toggleAllStreamers(true);
        } },
    ...{ class: "btn btn-secondary" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.toggleAllStreamers(false);
        } },
    ...{ class: "btn btn-secondary" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streamer-table" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "th-tooltip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "th-tooltip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "th-tooltip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "th-tooltip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
for (const [streamer] of __VLS_getVForSourceType((__VLS_ctx.typedStreamerSettings))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
        key: (streamer.streamer_id),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        ...{ class: "streamer-info" },
    });
    if (streamer.profile_image_url) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "streamer-avatar" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
            src: (streamer.profile_image_url),
            alt: (streamer.username || ''),
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "streamer-name" },
    });
    (streamer.username || 'Unknown Streamer');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        'data-label': "Online",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (...[$event]) => {
                __VLS_ctx.updateStreamerSettings(streamer.streamer_id, { notify_online: streamer.notify_online });
            } },
        type: "checkbox",
    });
    (streamer.notify_online);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        'data-label': "Offline",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (...[$event]) => {
                __VLS_ctx.updateStreamerSettings(streamer.streamer_id, { notify_offline: streamer.notify_offline });
            } },
        type: "checkbox",
    });
    (streamer.notify_offline);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        'data-label': "Updates",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (...[$event]) => {
                __VLS_ctx.updateStreamerSettings(streamer.streamer_id, { notify_update: streamer.notify_update });
            } },
        type: "checkbox",
    });
    (streamer.notify_update);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        'data-label': "Favorites",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (...[$event]) => {
                __VLS_ctx.updateStreamerSettings(streamer.streamer_id, { notify_favorite_category: streamer.notify_favorite_category });
            } },
        type: "checkbox",
    });
    (streamer.notify_favorite_category);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
        ...{ class: "actions-cell" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "btn-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.toggleAllForStreamer(streamer.streamer_id, true);
            } },
        ...{ class: "btn btn-sm btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.toggleAllForStreamer(streamer.streamer_id, false);
            } },
        ...{ class: "btn btn-sm btn-secondary" },
    });
}
/** @type {__VLS_StyleScopedClasses['settings-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-with-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['is-invalid']} */ ;
/** @type {__VLS_StyleScopedClasses['invalid-feedback']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-link']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-notifications']} */ ;
/** @type {__VLS_StyleScopedClasses['table-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['th-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['th-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['th-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['th-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['actions-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-group']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            typedStreamerSettings: typedStreamerSettings,
            data: data,
            showValidationError: showValidationError,
            showTooltip: showTooltip,
            handleInput: handleInput,
            handleBlur: handleBlur,
            handleTooltipMouseEnter: handleTooltipMouseEnter,
            handleTooltipMouseLeave: handleTooltipMouseLeave,
            isSaving: isSaving,
            isValidNotificationUrl: isValidNotificationUrl,
            canSave: canSave,
            saveSettings: saveSettings,
            updateStreamerSettings: updateStreamerSettings,
            toggleAllForStreamer: toggleAllForStreamer,
            toggleAllStreamers: toggleAllStreamers,
            testNotification: testNotification,
            testWebSocketNotification: testWebSocketNotification,
        };
    },
    emits: {},
    props: {
        settings: {
            type: Object,
            required: true
        },
        streamerSettings: {
            type: Array,
            required: true
        }
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    emits: {},
    props: {
        settings: {
            type: Object,
            required: true
        },
        streamerSettings: {
            type: Array,
            required: true
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
