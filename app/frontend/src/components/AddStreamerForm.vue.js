import { ref, reactive } from 'vue';
const username = ref('');
const quality = ref('best'); // Default quality
const isLoading = ref(false);
const isValidating = ref(false);
const statusMessage = ref('');
const hasError = ref(false);
const isValid = ref(false);
const validationMessage = ref('');
const streamerInfo = ref(null);
// Benachrichtigungseinstellungen
const notifications = reactive({
    notify_online: true,
    notify_offline: true,
    notify_update: true,
    notify_favorite_category: true
});
// Aufnahmeeinstellungen
const recording = reactive({
    enabled: true,
    quality: '',
    custom_filename: ''
});
// Überprüfe den Benutzernamen über die Twitch API
const validateUsername = async () => {
    if (!username.value.trim())
        return;
    isValidating.value = true;
    validationMessage.value = 'Checking username...';
    isValid.value = false;
    streamerInfo.value = null;
    try {
        const response = await fetch(`/api/streamers/validate/${username.value.trim().toLowerCase()}`);
        const data = await response.json();
        if (response.ok && data.valid) {
            isValid.value = true;
            validationMessage.value = 'Valid Twitch username!';
            streamerInfo.value = data.streamer_info;
        }
        else {
            isValid.value = false;
            validationMessage.value = data.message || 'Invalid Twitch username';
        }
    }
    catch (error) {
        isValid.value = false;
        validationMessage.value = 'Error checking username';
        console.error('Error:', error);
    }
    finally {
        isValidating.value = false;
    }
};
const validateAndSubmit = () => {
    if (!isValid.value) {
        validateUsername();
        return;
    }
    addStreamer();
};
const addStreamer = async () => {
    if (!username.value.trim() || !isValid.value)
        return;
    isLoading.value = true;
    statusMessage.value = 'Adding streamer...';
    hasError.value = false;
    try {
        const cleanUsername = username.value.trim().toLowerCase();
        const response = await fetch(`/api/streamers/${cleanUsername}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                quality: quality.value,
                notifications: {
                    notify_online: notifications.notify_online,
                    notify_offline: notifications.notify_offline,
                    notify_update: notifications.notify_update,
                    notify_favorite_category: notifications.notify_favorite_category
                },
                recording: {
                    enabled: recording.enabled,
                    quality: recording.quality,
                    custom_filename: recording.custom_filename
                }
            })
        });
        const data = await response.json();
        if (response.ok) {
            statusMessage.value = 'Streamer added successfully!';
            username.value = '';
            isValid.value = false;
            streamerInfo.value = null;
            emit('streamer-added');
        }
        else {
            hasError.value = true;
            statusMessage.value = data.message || 'Failed to add streamer';
        }
    }
    catch (error) {
        hasError.value = true;
        statusMessage.value = 'Error connecting to server';
        console.error('Error:', error);
    }
    finally {
        isLoading.value = false;
    }
};
const emit = defineEmits(['streamer-added']);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['validate-button']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-button']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-options']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-options']} */ ;
/** @type {__VLS_StyleScopedClasses['input-group']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-button']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['profile-image']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
    ...{ onSubmit: (__VLS_ctx.validateAndSubmit) },
    ...{ class: "streamer-form" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "input-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    ...{ onBlur: (__VLS_ctx.validateUsername) },
    type: "text",
    value: (__VLS_ctx.username),
    disabled: (__VLS_ctx.isLoading || __VLS_ctx.isValidating),
    placeholder: "Enter Twitch username",
    required: true,
    ...{ class: "input-field interactive-element" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.validateUsername) },
    type: "button",
    disabled: (__VLS_ctx.isLoading || __VLS_ctx.isValidating || !__VLS_ctx.username.trim()),
    ...{ class: "validate-button interactive-element" },
});
if (__VLS_ctx.isValidating) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
(__VLS_ctx.isValidating ? 'Checking...' : 'Check');
if (__VLS_ctx.validationMessage) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-item" },
        ...{ class: ({ error: !__VLS_ctx.isValid, success: __VLS_ctx.isValid }) },
    });
    (__VLS_ctx.validationMessage);
}
if (__VLS_ctx.isValid && __VLS_ctx.streamerInfo) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-panel content-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.streamerInfo.display_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-preview" },
    });
    if (__VLS_ctx.streamerInfo.profile_image_url) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img, __VLS_intrinsicElements.img)({
            src: (__VLS_ctx.streamerInfo.profile_image_url),
            alt: "Profile",
            ...{ class: "profile-image" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-name" },
    });
    (__VLS_ctx.streamerInfo.display_name);
    if (__VLS_ctx.streamerInfo.description) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "streamer-details" },
        });
        (__VLS_ctx.streamerInfo.description);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        for: "quality-select",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        id: "quality-select",
        value: (__VLS_ctx.quality),
        disabled: (__VLS_ctx.isLoading),
        ...{ class: "input-field" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "best",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "1080p60",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "1080p",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "720p60",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "720p",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "480p",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "360p",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "160p",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "audio_only",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-options" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "checkbox",
    });
    (__VLS_ctx.notifications.notify_online);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "checkmark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "checkbox",
    });
    (__VLS_ctx.notifications.notify_offline);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "checkmark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "checkbox",
    });
    (__VLS_ctx.notifications.notify_update);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "checkmark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "checkbox",
    });
    (__VLS_ctx.notifications.notify_favorite_category);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "checkmark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recording-options" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "checkbox",
    });
    (__VLS_ctx.recording.enabled);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "checkmark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-description" },
    });
    if (__VLS_ctx.recording.enabled) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
            for: "recording-quality",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            id: "recording-quality",
            value: (__VLS_ctx.recording.quality),
            ...{ class: "input-field" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "best",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "1080p60",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "1080p",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "720p60",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "720p",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "480p",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "360p",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "160p",
        });
    }
    if (__VLS_ctx.recording.enabled) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
            for: "custom-filename",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
            id: "custom-filename",
            type: "text",
            value: (__VLS_ctx.recording.custom_filename),
            placeholder: "Use global template",
            ...{ class: "input-field" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "submit",
    disabled: (__VLS_ctx.isLoading || __VLS_ctx.isValidating || !__VLS_ctx.isValid),
    ...{ class: "btn btn-primary" },
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
(__VLS_ctx.isLoading ? 'Adding...' : 'Add Streamer');
if (__VLS_ctx.statusMessage) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-item" },
        ...{ class: ({ error: __VLS_ctx.hasError }) },
    });
    (__VLS_ctx.statusMessage);
}
/** @type {__VLS_StyleScopedClasses['streamer-form']} */ ;
/** @type {__VLS_StyleScopedClasses['input-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['interactive-element']} */ ;
/** @type {__VLS_StyleScopedClasses['validate-button']} */ ;
/** @type {__VLS_StyleScopedClasses['interactive-element']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['success']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['profile-image']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-details']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-options']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-title']} */ ;
/** @type {__VLS_StyleScopedClasses['option-description']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-title']} */ ;
/** @type {__VLS_StyleScopedClasses['option-description']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-title']} */ ;
/** @type {__VLS_StyleScopedClasses['option-description']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-title']} */ ;
/** @type {__VLS_StyleScopedClasses['option-description']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-options']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-container']} */ ;
/** @type {__VLS_StyleScopedClasses['checkmark']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-title']} */ ;
/** @type {__VLS_StyleScopedClasses['option-description']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            $emit: emit,
            username: username,
            quality: quality,
            isLoading: isLoading,
            isValidating: isValidating,
            statusMessage: statusMessage,
            hasError: hasError,
            isValid: isValid,
            validationMessage: validationMessage,
            streamerInfo: streamerInfo,
            notifications: notifications,
            recording: recording,
            validateUsername: validateUsername,
            validateAndSubmit: validateAndSubmit,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {
            $emit: emit,
        };
    },
});
; /* PartiallyEnd: #4569/main.vue */
