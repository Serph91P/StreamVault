import { ref, computed, onMounted } from 'vue';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { CleanupPolicyType } from '@/types/recording';
const props = defineProps();
const emit = defineEmits();
const recordingSettings = useRecordingSettings();
// State
const isSaving = ref(false);
const isRunningCleanup = ref(false);
const showSnackbar = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success');
const showCleanupResults = ref(false);
const cleanupResults = ref({
    message: '',
    deleted_count: 0,
    deleted_paths: []
});
// Storage stats
const showStorageStats = ref(false);
const storageStats = ref({
    totalSize: 0,
    recordingCount: 0,
    oldestRecording: '',
    newestRecording: ''
});
// Base policy - simplified without complex timeframe logic
const policy = ref({
    type: CleanupPolicyType.COUNT,
    threshold: 10,
    preserve_favorites: true,
    preserve_categories: []
});
// Options
const policyTypes = [
    { label: 'Keep X newest recordings', value: CleanupPolicyType.COUNT },
    { label: 'Limit total size (GB)', value: CleanupPolicyType.SIZE },
    { label: 'Delete older than X days', value: CleanupPolicyType.AGE }
];
const availableCategories = ref([]);
// Computed properties
const policyHint = computed(() => {
    switch (policy.value.type) {
        case CleanupPolicyType.COUNT:
            return `Keep only the ${policy.value.threshold} most recent recordings per streamer`;
        case CleanupPolicyType.SIZE:
            return `Delete old recordings when total size exceeds ${policy.value.threshold} GB per streamer`;
        case CleanupPolicyType.AGE:
            return `Delete recordings older than ${policy.value.threshold} days`;
        default:
            return '';
    }
});
const thresholdLabel = computed(() => {
    switch (policy.value.type) {
        case CleanupPolicyType.COUNT:
            return 'Number of recordings to keep';
        case CleanupPolicyType.SIZE:
            return 'Maximum storage size (GB)';
        case CleanupPolicyType.AGE:
            return 'Maximum age (days)';
        default:
            return 'Threshold';
    }
});
const thresholdHint = computed(() => {
    switch (policy.value.type) {
        case CleanupPolicyType.COUNT:
            return 'Keeps the most recent recordings, deletes older ones';
        case CleanupPolicyType.SIZE:
            return 'Deletes oldest recordings when total size exceeds this limit';
        case CleanupPolicyType.AGE:
            return 'Deletes recordings older than this number of days';
        default:
            return '';
    }
});
const showPreserveCategories = computed(() => {
    return availableCategories.value.length > 0;
});
// Methods
async function loadPolicy() {
    try {
        if (props.isGlobal) {
            // Make sure settings are loaded first
            if (!recordingSettings.settings.value) {
                await recordingSettings.fetchSettings();
            }
            // Load global cleanup policy from settings
            if (recordingSettings.settings.value?.cleanup_policy) {
                const loadedPolicy = recordingSettings.settings.value.cleanup_policy;
                policy.value = ensureCompletePolicy(loadedPolicy);
            }
        }
        else if (props.streamerId) {
            // Load storage stats for streamer
            showStorageStats.value = true;
            await loadStorageStats();
            // Load streamer-specific policy if available
            await recordingSettings.fetchStreamerSettings();
            const streamerSettings = recordingSettings.streamerSettings.value.find((s) => s.streamer_id === props.streamerId);
            if (streamerSettings?.cleanup_policy) {
                policy.value = ensureCompletePolicy(streamerSettings.cleanup_policy);
            }
        }
        // Load available categories
        await loadCategories();
    }
    catch (error) {
        showError('Error loading cleanup policy');
        console.error('Error loading cleanup policy:', error);
    }
}
async function loadCategories() {
    try {
        const categories = await recordingSettings.getAvailableCategories();
        availableCategories.value = categories;
    }
    catch (error) {
        console.error('Error loading categories:', error);
    }
}
async function loadStorageStats() {
    if (!props.streamerId)
        return;
    try {
        const stats = await recordingSettings.getStreamerStorageUsage(props.streamerId);
        storageStats.value = stats;
    }
    catch (error) {
        console.error('Error loading storage stats:', error);
    }
}
async function savePolicy() {
    try {
        isSaving.value = true;
        // Ensure all required properties are present
        const completePolicy = ensureCompletePolicy(policy.value);
        if (props.isGlobal) {
            // Save global cleanup policy
            await recordingSettings.updateCleanupPolicy(completePolicy);
        }
        else if (props.streamerId) {
            // Save streamer-specific cleanup policy
            await recordingSettings.updateStreamerCleanupPolicy(props.streamerId, completePolicy);
        }
        showSuccess('Cleanup policy saved successfully');
        emit('saved', completePolicy);
    }
    catch (error) {
        showError('Error saving cleanup policy');
        console.error('Error saving cleanup policy:', error);
    }
    finally {
        isSaving.value = false;
    }
}
async function runCleanupNow() {
    if (!props.streamerId)
        return;
    try {
        isRunningCleanup.value = true;
        const response = await recordingSettings.cleanupOldRecordings(props.streamerId);
        // Show results dialog with the response from the server
        cleanupResults.value = {
            message: response.message || 'Cleanup completed successfully',
            deleted_count: response.deleted_count || 0,
            deleted_paths: response.deleted_paths || []
        };
        showCleanupResults.value = true;
        // Refresh storage stats
        await loadStorageStats();
    }
    catch (error) {
        showError('Error running cleanup');
        console.error('Error running cleanup:', error);
    }
    finally {
        isRunningCleanup.value = false;
    }
}
async function runCustomCleanupTest() {
    if (!props.streamerId)
        return;
    try {
        isRunningCleanup.value = true;
        // Ensure all required properties are present
        const completePolicy = ensureCompletePolicy(policy.value);
        const result = await recordingSettings.runCustomCleanup(props.streamerId, completePolicy);
        // Show results dialog
        cleanupResults.value = {
            message: result.message || `Test cleanup would delete ${result.deleted_count} recordings`,
            deleted_count: result.deleted_count || 0,
            deleted_paths: result.deleted_paths || []
        };
        showCleanupResults.value = true;
        // Refresh storage stats
        await loadStorageStats();
    }
    catch (error) {
        showError('Error running custom cleanup test');
        console.error('Error running custom cleanup:', error);
    }
    finally {
        isRunningCleanup.value = false;
    }
}
function closeCleanupResults() {
    showCleanupResults.value = false;
    cleanupResults.value = {
        message: '',
        deleted_count: 0,
        deleted_paths: []
    };
}
function formatFileSize(bytes) {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
function formatDate(isoDate) {
    if (!isoDate)
        return 'N/A';
    try {
        return new Date(isoDate).toLocaleString();
    }
    catch (error) {
        return 'Invalid date';
    }
}
function showSuccess(message) {
    snackbarText.value = message;
    snackbarColor.value = 'success';
    showSnackbar.value = true;
    setTimeout(() => {
        showSnackbar.value = false;
    }, 5000);
}
function showError(message) {
    snackbarText.value = message;
    snackbarColor.value = 'error';
    showSnackbar.value = true;
    setTimeout(() => {
        showSnackbar.value = false;
    }, 8000);
}
// Helper function to ensure policy has all required properties
function ensureCompletePolicy(policyObj) {
    return {
        type: policyObj.type || CleanupPolicyType.COUNT,
        threshold: policyObj.threshold || 10,
        preserve_favorites: policyObj.preserve_favorites !== undefined ? policyObj.preserve_favorites : true,
        preserve_categories: policyObj.preserve_categories || []
    };
}
// Load initial data
onMounted(() => {
    loadPolicy();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['deleted-files-list']} */ ;
/** @type {__VLS_StyleScopedClasses['deleted-files-list']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "cleanup-policy-editor" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "policy-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "card-title" },
});
(__VLS_ctx.title);
__VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
    ...{ onSubmit: (__VLS_ctx.savePolicy) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    value: (__VLS_ctx.policy.type),
    ...{ class: "form-control" },
});
for (const [type] of __VLS_getVForSourceType((__VLS_ctx.policyTypes))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        key: (type.value),
        value: (type.value),
    });
    (type.label);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "help-text" },
});
(__VLS_ctx.policyHint);
if (__VLS_ctx.policy.type !== 'custom') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    (__VLS_ctx.thresholdLabel);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "number",
        min: "1",
        ...{ class: "form-control" },
        required: true,
    });
    (__VLS_ctx.policy.threshold);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "help-text" },
    });
    (__VLS_ctx.thresholdHint);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "checkbox-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "checkbox-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    type: "checkbox",
});
(__VLS_ctx.policy.preserve_favorites);
if (__VLS_ctx.showPreserveCategories) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.policy.preserve_categories),
        ...{ class: "form-control" },
        multiple: true,
    });
    for (const [category] of __VLS_getVForSourceType((__VLS_ctx.availableCategories))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
            key: (category.id),
            value: (category.name),
        });
        (category.name);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "help-text" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "submit",
    ...{ class: "btn btn-primary" },
    disabled: (__VLS_ctx.isSaving),
});
(__VLS_ctx.isSaving ? 'Saving...' : 'Save Cleanup Policy');
if (__VLS_ctx.showStorageStats) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "policy-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "card-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.formatFileSize(__VLS_ctx.storageStats.totalSize));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.storageStats.recordingCount);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.formatDate(__VLS_ctx.storageStats.oldestRecording));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.formatDate(__VLS_ctx.storageStats.newestRecording));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.runCleanupNow) },
        ...{ class: "btn btn-danger" },
        disabled: (__VLS_ctx.isRunningCleanup),
    });
    (__VLS_ctx.isRunningCleanup ? 'Cleaning...' : 'Run Cleanup Now');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.runCustomCleanupTest) },
        ...{ class: "btn btn-warning" },
        disabled: (__VLS_ctx.isRunningCleanup),
    });
}
if (__VLS_ctx.showSnackbar) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: (['message', __VLS_ctx.snackbarColor]) },
    });
    (__VLS_ctx.snackbarText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showSnackbar))
                    return;
                __VLS_ctx.showSnackbar = false;
            } },
        ...{ class: "close-btn" },
    });
}
if (__VLS_ctx.showCleanupResults) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeCleanupResults) },
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
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeCleanupResults) },
        ...{ class: "close-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-body" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.cleanupResults.message);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.cleanupResults.deleted_count);
    if (__VLS_ctx.cleanupResults.deleted_paths && __VLS_ctx.cleanupResults.deleted_paths.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
            ...{ class: "deleted-files-list" },
        });
        for (const [path, index] of __VLS_getVForSourceType((__VLS_ctx.cleanupResults.deleted_paths))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                key: (index),
            });
            (path);
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-footer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeCleanupResults) },
        ...{ class: "btn btn-primary" },
    });
}
/** @type {__VLS_StyleScopedClasses['cleanup-policy-editor']} */ ;
/** @type {__VLS_StyleScopedClasses['policy-card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-group']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['policy-card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-body']} */ ;
/** @type {__VLS_StyleScopedClasses['deleted-files-list']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isSaving: isSaving,
            isRunningCleanup: isRunningCleanup,
            showSnackbar: showSnackbar,
            snackbarText: snackbarText,
            snackbarColor: snackbarColor,
            showCleanupResults: showCleanupResults,
            cleanupResults: cleanupResults,
            showStorageStats: showStorageStats,
            storageStats: storageStats,
            policy: policy,
            policyTypes: policyTypes,
            availableCategories: availableCategories,
            policyHint: policyHint,
            thresholdLabel: thresholdLabel,
            thresholdHint: thresholdHint,
            showPreserveCategories: showPreserveCategories,
            savePolicy: savePolicy,
            runCleanupNow: runCleanupNow,
            runCustomCleanupTest: runCustomCleanupTest,
            closeCleanupResults: closeCleanupResults,
            formatFileSize: formatFileSize,
            formatDate: formatDate,
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
