import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
const router = useRouter();
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const error = ref('');
const isValid = computed(() => {
    return (username.value.length >= 3 &&
        password.value.length >= 6 &&
        password.value === confirmPassword.value);
});
const handleSetup = async () => {
    if (!isValid.value)
        return;
    isLoading.value = true;
    error.value = '';
    try {
        const response = await fetch('/auth/setup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
                username: username.value,
                password: password.value,
            }),
        });
        if (response.ok) {
            const data = await response.json();
            alert(data.message || 'Setup completed successfully.');
            router.push('/');
        }
        else {
            const errorResponse = await response.json().catch(() => ({ detail: 'Unknown error' }));
            error.value = errorResponse.detail || 'Setup failed.';
        }
    }
    catch (e) {
        error.value = 'An error occurred while submitting the setup.';
        console.error('Setup submission error:', e);
    }
    finally {
        isLoading.value = false;
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setup-page" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
    ...{ onSubmit: (__VLS_ctx.handleSetup) },
    ...{ class: "setup-form" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    ...{ class: "input-field" },
    type: "text",
    value: (__VLS_ctx.username),
    placeholder: "Admin Username",
    required: true,
});
if (__VLS_ctx.username && __VLS_ctx.username.length < 3) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-msg" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    ...{ class: "input-field" },
    type: "password",
    placeholder: "Password",
    required: true,
});
(__VLS_ctx.password);
if (__VLS_ctx.password && __VLS_ctx.password.length < 6) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-msg" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-group" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    ...{ class: "input-field" },
    type: "password",
    placeholder: "Confirm Password",
    required: true,
});
(__VLS_ctx.confirmPassword);
if (__VLS_ctx.confirmPassword && __VLS_ctx.password !== __VLS_ctx.confirmPassword) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-msg" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "submit",
    ...{ class: "submit-button" },
    disabled: (__VLS_ctx.isLoading || !__VLS_ctx.isValid),
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
(__VLS_ctx.isLoading ? 'Creating Account...' : 'Create Admin Account');
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-msg" },
    });
    (__VLS_ctx.error);
}
/** @type {__VLS_StyleScopedClasses['setup-page']} */ ;
/** @type {__VLS_StyleScopedClasses['setup-form']} */ ;
/** @type {__VLS_StyleScopedClasses['description']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['error-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['error-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['error-msg']} */ ;
/** @type {__VLS_StyleScopedClasses['submit-button']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['error-msg']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            username: username,
            password: password,
            confirmPassword: confirmPassword,
            isLoading: isLoading,
            error: error,
            isValid: isValid,
            handleSetup: handleSetup,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
