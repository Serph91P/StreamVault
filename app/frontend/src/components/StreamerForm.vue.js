import { ref, reactive, watch } from 'vue';
const props = defineProps({
    streamer: {
        type: Object,
        required: false
    },
    editMode: {
        type: Boolean,
        default: false
    }
});
const emit = defineEmits(['submit', 'cancel', 'delete']);
const isSubmitting = ref(false);
const errors = reactive({
    username: ''
});
// Form data with default values
const formData = reactive({
    username: '',
    display_name: '',
    twitch_id: '',
    auto_record: true,
    record_public: true,
    record_subscribers: false,
    quality: 'best'
});
// If editing, populate form with existing streamer data
watch(() => props.streamer, (streamer) => {
    if (streamer) {
        formData.username = streamer.username || '';
        formData.display_name = streamer.display_name || streamer.username || '';
        formData.twitch_id = streamer.twitch_id || '';
        formData.auto_record = streamer.auto_record !== false;
        formData.record_public = streamer.record_public !== false;
        formData.record_subscribers = streamer.record_subscribers === true;
        formData.quality = streamer.quality || 'best';
    }
}, { immediate: true });
// Form validation
const validateForm = () => {
    let isValid = true;
    errors.username = '';
    if (!formData.username.trim()) {
        errors.username = 'Username is required';
        isValid = false;
    }
    return isValid;
};
// Submit form
const submitForm = async () => {
    if (!validateForm())
        return;
    try {
        isSubmitting.value = true;
        const streamerData = {
            username: formData.username.trim(),
            display_name: formData.display_name.trim() || formData.username.trim(),
            twitch_id: formData.twitch_id,
            auto_record: formData.auto_record,
            record_public: formData.record_public,
            record_subscribers: formData.record_subscribers,
            quality: formData.quality
        };
        emit('submit', streamerData);
    }
    catch (error) {
        console.error('Form submission error:', error);
    }
    finally {
        isSubmitting.value = false;
    }
};
const confirmDelete = () => {
    if (confirm(`Are you sure you want to delete ${formData.display_name || formData.username}? This will also remove all recording settings and stream history for this streamer.`)) {
        emit('delete', formData.username);
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['is-invalid']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streamer-form" },
});
if (!__VLS_ctx.editMode) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
    ...{ onSubmit: (__VLS_ctx.submitForm) },
    ...{ class: "form" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    for: "username",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    id: "username",
    value: (__VLS_ctx.formData.username),
    type: "text",
    ...{ class: "form-control" },
    ...{ class: ({ 'is-invalid': __VLS_ctx.errors.username }) },
    disabled: (__VLS_ctx.editMode),
    placeholder: "Twitch username",
    required: true,
});
if (__VLS_ctx.errors.username) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "invalid-feedback" },
    });
    (__VLS_ctx.errors.username);
}
if (__VLS_ctx.editMode) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        for: "displayName",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        id: "displayName",
        value: (__VLS_ctx.formData.display_name),
        type: "text",
        ...{ class: "form-control" },
        placeholder: "Display name",
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    type: "checkbox",
});
(__VLS_ctx.formData.auto_record);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    type: "checkbox",
});
(__VLS_ctx.formData.record_public);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    type: "checkbox",
});
(__VLS_ctx.formData.record_subscribers);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    for: "quality",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    id: "quality",
    value: (__VLS_ctx.formData.quality),
    ...{ class: "form-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "best",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "1080p",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "720p",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "480p",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "worst",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "submit",
    ...{ class: "btn btn-primary" },
    disabled: (__VLS_ctx.isSubmitting),
});
(__VLS_ctx.isSubmitting ? 'Saving...' : (__VLS_ctx.editMode ? 'Save Changes' : 'Add Streamer'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.$emit('cancel');
        } },
    type: "button",
    ...{ class: "btn btn-secondary" },
});
if (__VLS_ctx.editMode) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.confirmDelete) },
        type: "button",
        ...{ class: "btn btn-danger" },
    });
}
/** @type {__VLS_StyleScopedClasses['streamer-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['is-invalid']} */ ;
/** @type {__VLS_StyleScopedClasses['invalid-feedback']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isSubmitting: isSubmitting,
            errors: errors,
            formData: formData,
            submitForm: submitForm,
            confirmDelete: confirmDelete,
        };
    },
    emits: {},
    props: {
        streamer: {
            type: Object,
            required: false
        },
        editMode: {
            type: Boolean,
            default: false
        }
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    emits: {},
    props: {
        streamer: {
            type: Object,
            required: false
        },
        editMode: {
            type: Boolean,
            default: false
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
