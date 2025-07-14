import { ref, onMounted, computed } from 'vue';
import { usePWA } from '@/composables/usePWA';
const { isInstallable, isInstalled, installPWA, getPlatformInfo } = usePWA();
const showInstallPrompt = ref(false);
const hasBeenDismissed = ref(false);
const platformInfo = ref(null);
// Computed properties for platform-specific content
const installText = computed(() => {
    if (!platformInfo.value)
        return 'Install StreamVault';
    const { platform, browser } = platformInfo.value;
    if (platform === 'iOS' && browser === 'Safari') {
        return 'Add StreamVault to Home Screen';
    }
    if (platform === 'Android') {
        return 'Install StreamVault App';
    }
    if (platform === 'Windows') {
        return 'Install StreamVault';
    }
    if (platform === 'macOS') {
        return 'Add StreamVault to Dock';
    }
    if (platform === 'Linux') {
        return 'Install StreamVault';
    }
    return 'Install StreamVault';
});
const installDescription = computed(() => {
    if (!platformInfo.value)
        return 'Install this app on your device for a better experience';
    const { platform, browser } = platformInfo.value;
    if (platform === 'iOS' && browser === 'Safari') {
        return 'Tap the Share button, then "Add to Home Screen" for quick access';
    }
    if (platform === 'Android') {
        return 'Install for faster loading and offline access';
    }
    if (platform === 'Windows') {
        return 'Install to your Start Menu and taskbar';
    }
    if (platform === 'macOS') {
        return 'Add to your Dock for quick access';
    }
    if (platform === 'Linux') {
        return 'Install for better performance and offline use';
    }
    return 'Install this app on your device for a better experience';
});
onMounted(() => {
    // Show install prompt if app is installable and hasn't been dismissed
    const dismissed = localStorage.getItem('pwa-install-dismissed');
    hasBeenDismissed.value = dismissed === 'true';
    // Show prompt after 3 seconds if installable and not dismissed
    setTimeout(() => {
        if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value) {
            showInstallPrompt.value = true;
        }
    }, 3000);
    // Also check periodically for installability changes (mobile browsers)
    setInterval(() => {
        if (isInstallable.value && !isInstalled.value && !hasBeenDismissed.value && !showInstallPrompt.value) {
            showInstallPrompt.value = true;
        }
    }, 10000);
});
const installApp = async () => {
    try {
        await installPWA();
        showInstallPrompt.value = false;
    }
    catch (error) {
        console.error('Installation failed:', error);
    }
};
const dismissPrompt = () => {
    showInstallPrompt.value = false;
    hasBeenDismissed.value = true;
    localStorage.setItem('pwa-install-dismissed', 'true');
    // Show again after 7 days
    setTimeout(() => {
        localStorage.removeItem('pwa-install-dismissed');
    }, 7 * 24 * 60 * 60 * 1000);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['install-prompt']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__text']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__text']} */ ;
/** @type {__VLS_StyleScopedClasses['install-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['install-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__text']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__text']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__content']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__icon']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__actions']} */ ;
/** @type {__VLS_StyleScopedClasses['install-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
if (__VLS_ctx.showInstallPrompt) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "install-prompt" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "install-prompt__content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "install-prompt__icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "24",
        height: "24",
        viewBox: "0 0 24 24",
        fill: "none",
        xmlns: "http://www.w3.org/2000/svg",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
        d: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
        fill: "currentColor",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "install-prompt__text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.installText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.installDescription);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "install-prompt__actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.installApp) },
        ...{ class: "install-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.dismissPrompt) },
        ...{ class: "dismiss-btn" },
    });
}
/** @type {__VLS_StyleScopedClasses['install-prompt']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__content']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__icon']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__text']} */ ;
/** @type {__VLS_StyleScopedClasses['install-prompt__actions']} */ ;
/** @type {__VLS_StyleScopedClasses['install-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-btn']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            showInstallPrompt: showInstallPrompt,
            installText: installText,
            installDescription: installDescription,
            installApp: installApp,
            dismissPrompt: dismissPrompt,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
