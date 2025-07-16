import { ref, computed, watch, onMounted } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useFilenamePresets } from '@/composables/useFilenamePresets';
import { QUALITY_OPTIONS, FILENAME_VARIABLES } from '@/types/recording';
import CleanupPolicyEditor from '@/components/CleanupPolicyEditor.vue';
const props = defineProps();
const emits = defineEmits();
// Tab management
const activeTab = ref('recording');
const tabs = [
    { id: 'recording', label: 'Recording', icon: '📹' },
    { id: 'network', label: 'Network', icon: '🌐' },
    { id: 'storage', label: 'Storage', icon: '🗂️' }
];
const { isLoading, error } = useRecordingSettings();
// Filename presets from API
const { presets: FILENAME_PRESETS, isLoading: presetsLoading, error: presetsError } = useFilenamePresets();
// State for streamer cleanup policy dialog
const showStreamerPolicyDialog = ref(false);
const selectedStreamer = ref(null);
// Proxy settings state
const proxySettings = ref({
    enabled: false,
    http_proxy: '',
    https_proxy: ''
});
// Computed properties for real-time validation
const httpProxyError = computed(() => {
    if (!proxySettings.value.enabled || !proxySettings.value.http_proxy.trim()) {
        return '';
    }
    if (!validateProxyUrl(proxySettings.value.http_proxy)) {
        return 'HTTP proxy URL must start with "http://" or "https://"';
    }
    return '';
});
const httpsProxyError = computed(() => {
    if (!proxySettings.value.enabled || !proxySettings.value.https_proxy.trim()) {
        return '';
    }
    if (!validateProxyUrl(proxySettings.value.https_proxy)) {
        return 'HTTPS proxy URL must start with "http://" or "https://"';
    }
    return '';
});
// Check if proxy settings have validation errors
const hasProxyErrors = computed(() => {
    return httpProxyError.value !== '' || httpsProxyError.value !== '';
});
// Load proxy settings from GlobalSettings API
const loadProxySettings = async () => {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const globalSettings = await response.json();
            proxySettings.value = {
                enabled: !!(globalSettings.http_proxy || globalSettings.https_proxy),
                http_proxy: globalSettings.http_proxy || '',
                https_proxy: globalSettings.https_proxy || ''
            };
        }
    }
    catch (error) {
        console.error('Failed to load proxy settings:', error);
    }
};
// Validate proxy URL format
const validateProxyUrl = (url) => {
    if (!url || !url.trim()) {
        return true; // Empty URLs are valid (no proxy)
    }
    const trimmedUrl = url.trim();
    return trimmedUrl.startsWith('http://') || trimmedUrl.startsWith('https://');
};
// Save proxy settings to GlobalSettings API
const saveProxySettings = async () => {
    try {
        // Check for validation errors before attempting to save
        if (hasProxyErrors.value) {
            // Don't save if there are validation errors - the errors are already shown in the UI
            return;
        }
        const response = await fetch('/api/settings');
        if (!response.ok)
            throw new Error('Failed to load current settings');
        const globalSettings = await response.json();
        // Update proxy fields
        const updatedSettings = {
            ...globalSettings,
            http_proxy: proxySettings.value.enabled ? proxySettings.value.http_proxy : '',
            https_proxy: proxySettings.value.enabled ? proxySettings.value.https_proxy : ''
        };
        const saveResponse = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updatedSettings),
        });
        if (!saveResponse.ok) {
            throw new Error('Failed to save proxy settings');
        }
        console.log('Proxy settings saved successfully');
    }
    catch (error) {
        console.error('Failed to save proxy settings:', error);
        alert('Failed to save proxy settings. Please try again.');
    }
};
// Load proxy settings on component mount
onMounted(() => {
    loadProxySettings();
});
// Function to detect preset from template
const detectPresetFromTemplate = (template) => {
    const preset = FILENAME_PRESETS.find((p) => p.description === template);
    return preset ? preset.value : 'default';
};
// Create a copy of the settings for editing
const data = ref({
    enabled: props.settings?.enabled ?? false,
    output_directory: props.settings?.output_directory ?? '/recordings',
    filename_template: props.settings?.filename_template ?? '{streamer}/{streamer}_{year}{month}-{day}_{hour}-{minute}_{title}_{game}',
    filename_preset: props.settings?.filename_preset || detectPresetFromTemplate(props.settings?.filename_template ?? ''),
    default_quality: props.settings?.default_quality ?? 'best',
    use_chapters: props.settings?.use_chapters ?? true,
    use_category_as_chapter_title: props.settings?.use_category_as_chapter_title ?? false
});
const updateFilenameTemplate = () => {
    const preset = FILENAME_PRESETS.find((p) => p.value === data.value.filename_preset);
    if (preset) {
        data.value.filename_template = preset.description;
    }
};
// Update local data when props change
watch(() => props.settings, (newSettings) => {
    if (newSettings) {
        data.value = {
            ...newSettings,
            filename_preset: newSettings.filename_preset || detectPresetFromTemplate(newSettings.filename_template ?? '')
        };
    }
}, { deep: true });
const isSaving = ref(false);
// Preview filename with example data
const previewFilename = computed(() => {
    if (!data.value.filename_template)
        return '';
    const now = new Date();
    const year = now.getFullYear().toString();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    const hour = now.getHours().toString().padStart(2, '0');
    const minute = now.getMinutes().toString().padStart(2, '0');
    const second = now.getSeconds().toString().padStart(2, '0');
    let filename = data.value.filename_template;
    // Replace variables
    filename = filename
        .replace(/{streamer}/g, 'example_streamer')
        .replace(/{title}/g, 'Example Stream Title')
        .replace(/{game}/g, 'Example Game')
        .replace(/{twitch_id}/g, '123456789')
        .replace(/{year}/g, year)
        .replace(/{month}/g, month)
        .replace(/{day}/g, day)
        .replace(/{hour}/g, hour)
        .replace(/{minute}/g, minute)
        .replace(/{second}/g, second)
        .replace(/{timestamp}/g, `${year}${month}${day}_${hour}${minute}${second}`)
        .replace(/{datetime}/g, `${year}-${month}-${day}_${hour}-${minute}-${second}`)
        .replace(/{id}/g, 'stream_12345')
        .replace(/{season}/g, `S${year}-${month}`)
        .replace(/{episode}/g, '01');
    // Add .mp4 if not present
    if (!filename.toLowerCase().endsWith('.mp4')) {
        filename += '.mp4';
    }
    return filename;
});
// Update filename template when preset changes
const updateFilenameFromPreset = () => {
    const selectedPreset = FILENAME_PRESETS.find((preset) => preset.value === data.value.filename_preset);
    if (selectedPreset) {
        data.value.filename_template = selectedPreset.description;
    }
};
const saveSettings = async () => {
    try {
        isSaving.value = true;
        // Save recording settings
        emits('update', {
            enabled: data.value.enabled,
            output_directory: data.value.output_directory,
            filename_template: data.value.filename_template,
            filename_preset: data.value.filename_preset,
            default_quality: data.value.default_quality,
            use_chapters: data.value.use_chapters,
            use_category_as_chapter_title: data.value.use_category_as_chapter_title
        });
        // Save proxy settings separately
        await saveProxySettings();
    }
    catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings. Please try again.');
    }
    finally {
        isSaving.value = false;
    }
};
const updateStreamerSetting = (streamerId, settings) => {
    emits('updateStreamer', streamerId, settings);
};
const toggleAllStreamers = async (enabled) => {
    if (!props.streamerSettings)
        return;
    for (const streamer of props.streamerSettings) {
        if (!streamer?.streamer_id)
            continue;
        await updateStreamerSetting(streamer.streamer_id, { enabled });
    }
};
const stopRecording = (streamerId) => {
    emits('stopRecording', streamerId);
};
const isActiveRecording = (streamerId) => {
    return props.activeRecordings.some((rec) => rec.streamer_id === streamerId);
};
const formatDate = (date) => {
    return new Date(date).toLocaleString();
};
const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
};
const toggleStreamerRecording = (streamerId, enabled) => {
    updateStreamerSetting(streamerId, { enabled });
};
const handleCleanupPolicySaved = (policy) => {
    if (props.settings) {
        const updatedSettings = {
            ...props.settings,
            cleanup_policy: policy
        };
        emits('update', updatedSettings);
    }
};
// Methods for per-streamer cleanup policy editor
const openCleanupPolicyEditor = (streamer) => {
    selectedStreamer.value = streamer;
    showStreamerPolicyDialog.value = true;
};
const closeStreamerPolicyDialog = () => {
    showStreamerPolicyDialog.value = false;
    selectedStreamer.value = null;
};
const handleStreamerPolicySaved = (policy) => {
    console.log('Streamer cleanup policy saved:', policy);
    closeStreamerPolicyDialog();
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-message']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['th-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active-recordings']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-settings']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-action']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-examples']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-examples']} */ ;
/** @type {__VLS_StyleScopedClasses['example-item']} */ ;
/** @type {__VLS_StyleScopedClasses['example-item']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-tips']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-tips']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-form']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-body']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-configuration']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-examples']} */ ;
/** @type {__VLS_StyleScopedClasses['example-item']} */ ;
/** @type {__VLS_StyleScopedClasses['example-item']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['button-group']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-form']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['variable-tag']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-message" },
    });
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-form" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-navigation" },
    });
    for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.error))
                        return;
                    __VLS_ctx.activeTab = tab.id;
                } },
            key: (tab.id),
            ...{ class: (['tab-button', { active: __VLS_ctx.activeTab === tab.id }]) },
        });
        (tab.icon);
        (tab.label);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-content" },
    });
    if (__VLS_ctx.activeTab === 'recording') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "settings-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            type: "checkbox",
        });
        (__VLS_ctx.data.enabled);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            ...{ class: "form-control" },
        });
        (__VLS_ctx.data.output_directory);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            value: (__VLS_ctx.data.default_quality),
            ...{ class: "form-control" },
        });
        for (const [option] of __VLS_getVForSourceType((__VLS_ctx.QUALITY_OPTIONS))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                key: (option.value),
                value: (option.value),
            });
            (option.label);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            ...{ onChange: (__VLS_ctx.updateFilenameFromPreset) },
            value: (__VLS_ctx.data.filename_preset),
            ...{ class: "form-control" },
            disabled: (__VLS_ctx.presetsLoading),
        });
        if (__VLS_ctx.presetsLoading) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "",
            });
        }
        for (const [preset] of __VLS_getVForSourceType((__VLS_ctx.FILENAME_PRESETS))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                key: (preset.value),
                value: (preset.value),
            });
            (preset.label);
        }
        if (__VLS_ctx.presetsError) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "error-text" },
            });
            (__VLS_ctx.presetsError);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            ...{ class: "form-control" },
            ...{ style: {} },
        });
        (__VLS_ctx.data.filename_template);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "variables-container" },
        });
        for (const [variable] of __VLS_getVForSourceType((__VLS_ctx.FILENAME_VARIABLES))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                key: (variable.key),
                ...{ class: "variable-tag" },
            });
            (variable.key);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({
            ...{ class: "example-output" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            type: "checkbox",
        });
        (__VLS_ctx.data.use_chapters);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            type: "checkbox",
        });
        (__VLS_ctx.data.use_category_as_chapter_title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
    }
    if (__VLS_ctx.activeTab === 'network') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "settings-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "section-description" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            type: "checkbox",
        });
        (__VLS_ctx.proxySettings.enabled);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "help-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        if (__VLS_ctx.proxySettings.enabled) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "proxy-configuration" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "form-group" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                placeholder: "http://proxy.example.com:8080",
                ...{ class: "form-control" },
                ...{ class: ({ 'error': __VLS_ctx.httpProxyError }) },
            });
            (__VLS_ctx.proxySettings.http_proxy);
            if (__VLS_ctx.httpProxyError) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "error-text" },
                });
                (__VLS_ctx.httpProxyError);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "help-text" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "form-group" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                placeholder: "https://proxy.example.com:8080",
                ...{ class: "form-control" },
                ...{ class: ({ 'error': __VLS_ctx.httpsProxyError }) },
            });
            (__VLS_ctx.proxySettings.https_proxy);
            if (__VLS_ctx.httpsProxyError) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "error-text" },
                });
                (__VLS_ctx.httpsProxyError);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "help-text" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "proxy-examples" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "proxy-tips" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h6, __VLS_intrinsicElements.h6)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        }
    }
    if (__VLS_ctx.activeTab === 'storage') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tab-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "settings-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "section-description" },
        });
        /** @type {[typeof CleanupPolicyEditor, ]} */ ;
        // @ts-ignore
        const __VLS_0 = __VLS_asFunctionalComponent(CleanupPolicyEditor, new CleanupPolicyEditor({
            ...{ 'onSaved': {} },
            isGlobal: (true),
            title: "Global Cleanup Policy",
        }));
        const __VLS_1 = __VLS_0({
            ...{ 'onSaved': {} },
            isGlobal: (true),
            title: "Global Cleanup Policy",
        }, ...__VLS_functionalComponentArgsRest(__VLS_0));
        let __VLS_3;
        let __VLS_4;
        let __VLS_5;
        const __VLS_6 = {
            onSaved: (__VLS_ctx.handleCleanupPolicySaved)
        };
        var __VLS_2;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.saveSettings) },
        ...{ class: "btn btn-primary" },
        disabled: (__VLS_ctx.isSaving),
    });
    (__VLS_ctx.isSaving ? 'Saving...' : 'Save Settings');
}
if (__VLS_ctx.activeRecordings.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "active-recordings" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recordings-grid" },
    });
    for (const [recording] of __VLS_getVForSourceType((__VLS_ctx.activeRecordings))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (recording.streamer_id),
            ...{ class: "recording-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "recording-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "streamer-name" },
        });
        (recording.streamer_name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "recording-indicator" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "recording-details" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.formatDate(recording.started_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.formatDuration(recording.duration));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (recording.quality);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "output-path" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (recording.output_path);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activeRecordings.length > 0))
                        return;
                    __VLS_ctx.stopRecording(recording.streamer_id);
                } },
            ...{ class: "btn btn-danger" },
            disabled: (__VLS_ctx.isLoading),
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streamer-settings" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
if (!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-streamers-message" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-controls" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                    return;
                __VLS_ctx.toggleAllStreamers(true);
            } },
        ...{ class: "btn btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                    return;
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
    __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
    for (const [streamer] of __VLS_getVForSourceType((__VLS_ctx.streamerSettings))) {
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
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                        return;
                    __VLS_ctx.updateStreamerSetting(streamer.streamer_id, { enabled: streamer.enabled });
                } },
            type: "checkbox",
        });
        (streamer.enabled);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
            ...{ onChange: (...[$event]) => {
                    if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                        return;
                    __VLS_ctx.updateStreamerSetting(streamer.streamer_id, { quality: streamer.quality });
                } },
            value: (streamer.quality),
            ...{ class: "form-control form-control-sm" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            value: "",
        });
        for (const [option] of __VLS_getVForSourceType((__VLS_ctx.QUALITY_OPTIONS))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                key: (option.value),
                value: (option.value),
            });
            (option.label);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            ...{ onChange: (...[$event]) => {
                    if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                        return;
                    __VLS_ctx.updateStreamerSetting(streamer.streamer_id, { custom_filename: streamer.custom_filename });
                } },
            type: "text",
            value: (streamer.custom_filename),
            placeholder: "Use global template",
            ...{ class: "form-control form-control-sm" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "streamer-actions" },
        });
        if (__VLS_ctx.isActiveRecording(streamer.streamer_id)) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                            return;
                        if (!(__VLS_ctx.isActiveRecording(streamer.streamer_id)))
                            return;
                        __VLS_ctx.stopRecording(streamer.streamer_id);
                    } },
                ...{ class: "btn btn-danger btn-sm" },
                disabled: (__VLS_ctx.isLoading),
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.streamerSettings || __VLS_ctx.streamerSettings.length === 0))
                        return;
                    __VLS_ctx.openCleanupPolicyEditor(streamer);
                } },
            ...{ class: "btn btn-info btn-sm" },
            disabled: (__VLS_ctx.isLoading),
            title: "Configure cleanup policy for this streamer",
        });
    }
}
if (__VLS_ctx.showStreamerPolicyDialog) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeStreamerPolicyDialog) },
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: () => { } },
        ...{ class: "modal-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.selectedStreamer?.username || 'Streamer');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeStreamerPolicyDialog) },
        ...{ class: "close-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-body" },
    });
    if (__VLS_ctx.selectedStreamer) {
        /** @type {[typeof CleanupPolicyEditor, ]} */ ;
        // @ts-ignore
        const __VLS_7 = __VLS_asFunctionalComponent(CleanupPolicyEditor, new CleanupPolicyEditor({
            ...{ 'onSaved': {} },
            streamerId: (__VLS_ctx.selectedStreamer.streamer_id),
            title: (`Cleanup Policy for ${__VLS_ctx.selectedStreamer.username}`),
            isGlobal: (false),
        }));
        const __VLS_8 = __VLS_7({
            ...{ 'onSaved': {} },
            streamerId: (__VLS_ctx.selectedStreamer.streamer_id),
            title: (`Cleanup Policy for ${__VLS_ctx.selectedStreamer.username}`),
            isGlobal: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_7));
        let __VLS_10;
        let __VLS_11;
        let __VLS_12;
        const __VLS_13 = {
            onSaved: (__VLS_ctx.handleStreamerPolicySaved)
        };
        var __VLS_9;
    }
}
/** @type {__VLS_StyleScopedClasses['loading-message']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-form']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['variables-container']} */ ;
/** @type {__VLS_StyleScopedClasses['variable-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['example-output']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['section-description']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-configuration']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-examples']} */ ;
/** @type {__VLS_StyleScopedClasses['proxy-tips']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['section-description']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['active-recordings']} */ ;
/** @type {__VLS_StyleScopedClasses['recordings-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-card']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-header']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-details']} */ ;
/** @type {__VLS_StyleScopedClasses['output-path']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-settings']} */ ;
/** @type {__VLS_StyleScopedClasses['no-streamers-message']} */ ;
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
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-info']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-body']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            QUALITY_OPTIONS: QUALITY_OPTIONS,
            FILENAME_VARIABLES: FILENAME_VARIABLES,
            CleanupPolicyEditor: CleanupPolicyEditor,
            activeTab: activeTab,
            tabs: tabs,
            isLoading: isLoading,
            error: error,
            FILENAME_PRESETS: FILENAME_PRESETS,
            presetsLoading: presetsLoading,
            presetsError: presetsError,
            showStreamerPolicyDialog: showStreamerPolicyDialog,
            selectedStreamer: selectedStreamer,
            proxySettings: proxySettings,
            httpProxyError: httpProxyError,
            httpsProxyError: httpsProxyError,
            data: data,
            isSaving: isSaving,
            updateFilenameFromPreset: updateFilenameFromPreset,
            saveSettings: saveSettings,
            updateStreamerSetting: updateStreamerSetting,
            toggleAllStreamers: toggleAllStreamers,
            stopRecording: stopRecording,
            isActiveRecording: isActiveRecording,
            formatDate: formatDate,
            formatDuration: formatDuration,
            handleCleanupPolicySaved: handleCleanupPolicySaved,
            openCleanupPolicyEditor: openCleanupPolicyEditor,
            closeStreamerPolicyDialog: closeStreamerPolicyDialog,
            handleStreamerPolicySaved: handleStreamerPolicySaved,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
