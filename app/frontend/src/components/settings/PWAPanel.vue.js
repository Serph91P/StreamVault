import { ref, computed, onMounted } from 'vue';
import { usePWA } from '@/composables/usePWA';
const { isInstallable, isInstalled, isOnline, pushSupported, notificationPermission, installPWA, subscribeToPush, unsubscribeFromPush, showNotification, requestNotificationPermission } = usePWA();
const isEnablingNotifications = ref(false);
const isDisablingNotifications = ref(false);
const isSendingTest = ref(false);
const statusMessage = ref('');
const statusType = ref('');
const permissionText = computed(() => {
    switch (notificationPermission.value) {
        case 'granted': return 'Granted';
        case 'denied': return 'Denied';
        case 'default': return 'Not Asked';
        default: return 'Unknown';
    }
});
const installApp = async () => {
    try {
        await installPWA();
        showStatus('App installation initiated', 'success');
    }
    catch (error) {
        console.error('App installation failed:', error);
        showStatus('App installation failed', 'error');
    }
};
const enableNotifications = async () => {
    try {
        isEnablingNotifications.value = true;
        const permission = await requestNotificationPermission();
        if (permission === 'granted') {
            const subscription = await subscribeToPush();
            if (subscription) {
                showStatus('Push notifications enabled successfully', 'success');
            }
            else {
                showStatus('Failed to enable push notifications', 'error');
            }
        }
        else {
            showStatus('Notification permission denied', 'error');
        }
    }
    catch (error) {
        console.error('Failed to enable notifications:', error);
        showStatus('Failed to enable notifications', 'error');
    }
    finally {
        isEnablingNotifications.value = false;
    }
};
const disableNotifications = async () => {
    try {
        isDisablingNotifications.value = true;
        const success = await unsubscribeFromPush();
        if (success) {
            showStatus('Push notifications disabled', 'success');
        }
        else {
            showStatus('Failed to disable push notifications', 'error');
        }
    }
    catch (error) {
        console.error('Failed to disable notifications:', error);
        showStatus('Failed to disable notifications', 'error');
    }
    finally {
        isDisablingNotifications.value = false;
    }
};
const sendTestNotification = async () => {
    try {
        isSendingTest.value = true;
        // Try server-side push notification first
        const response = await fetch('/api/push/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.sent_count > 0) {
                showStatus(result.message, 'success');
                return;
            }
            else {
                console.warn('Server push failed:', result.message);
                // Fall through to local notification
            }
        }
        // If server push fails, try local notification via Service Worker
        try {
            await showNotification('🧪 StreamVault Test (Local)', {
                body: 'This is a local test notification. If you see this, your browser supports notifications!',
                icon: '/android-icon-192x192.png',
                badge: '/android-icon-96x96.png',
                tag: 'test-local-notification',
                requireInteraction: true,
                data: {
                    type: 'test_local',
                    timestamp: Date.now()
                }
            });
            showStatus('Local test notification sent successfully', 'success');
        }
        catch (localError) {
            console.error('Local notification also failed:', localError);
            // Try browser native notification as last resort
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('🧪 StreamVault Test (Native)', {
                    body: 'This is a native browser notification. Notifications are working!',
                    icon: '/android-icon-192x192.png',
                    tag: 'test-native-notification'
                });
                showStatus('Native test notification sent successfully', 'success');
            }
            else {
                throw new Error('All notification methods failed');
            }
        }
    }
    catch (error) {
        console.error('Failed to send test notification:', error);
        showStatus('Failed to send test notification. Check console for details.', 'error');
    }
    finally {
        isSendingTest.value = false;
    }
};
const showStatus = (message, type) => {
    statusMessage.value = message;
    statusType.value = type;
    // Clear message after 5 seconds
    setTimeout(() => {
        statusMessage.value = '';
        statusType.value = '';
    }, 5000);
};
const sendLocalTestNotification = async () => {
    try {
        // Try local notification to test PWA functionality
        if ('serviceWorker' in navigator && 'Notification' in window) {
            const permission = await requestNotificationPermission();
            if (permission === 'granted') {
                const notificationOptions = {
                    body: 'This is a local PWA test notification. If you see this, your PWA notifications are working!',
                    icon: '/android-icon-192x192.png',
                    badge: '/android-icon-96x96.png',
                    tag: 'pwa-test',
                    requireInteraction: true,
                    vibrate: [200, 100, 200],
                    actions: [
                        {
                            action: 'close',
                            title: 'Close'
                        }
                    ]
                };
                await showNotification('🧪 StreamVault PWA Test', notificationOptions);
                showStatus('Local PWA notification sent! Check your device.', 'success');
            }
            else {
                showStatus('Notification permission not granted', 'error');
            }
        }
        else {
            showStatus('PWA features not supported in this browser', 'error');
        }
    }
    catch (error) {
        console.error('Local test notification failed:', error);
        showStatus('Local test notification failed', 'error');
    }
};
onMounted(() => {
    // Any initialization logic
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['pwa-section']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['status-message']} */ ;
/** @type {__VLS_StyleScopedClasses['status-message']} */ ;
/** @type {__VLS_StyleScopedClasses['status-message']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "pwa-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "pwa-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "setting-description" },
});
(__VLS_ctx.isInstalled ? 'StreamVault is installed as an app' : 'StreamVault can be installed as an app for better experience');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-badge" },
    ...{ class: ({ 'installed': __VLS_ctx.isInstalled, 'not-installed': !__VLS_ctx.isInstalled }) },
});
(__VLS_ctx.isInstalled ? 'Installed' : 'Not Installed');
if (__VLS_ctx.isInstallable && !__VLS_ctx.isInstalled) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.installApp) },
        ...{ class: "btn btn-primary install-btn" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "setting-description" },
});
(__VLS_ctx.isOnline ? 'You are currently online' : 'You are currently offline');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-badge" },
    ...{ class: ({ 'online': __VLS_ctx.isOnline, 'offline': !__VLS_ctx.isOnline }) },
});
(__VLS_ctx.isOnline ? 'Online' : 'Offline');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "pwa-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "setting-description" },
});
(__VLS_ctx.pushSupported ? 'Your browser supports push notifications' : 'Your browser does not support push notifications');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-badge" },
    ...{ class: ({ 'supported': __VLS_ctx.pushSupported, 'not-supported': !__VLS_ctx.pushSupported }) },
});
(__VLS_ctx.pushSupported ? 'Supported' : 'Not Supported');
if (__VLS_ctx.pushSupported) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "setting-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-control" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-badge" },
        ...{ class: ({
                'granted': __VLS_ctx.notificationPermission === 'granted',
                'denied': __VLS_ctx.notificationPermission === 'denied',
                'default': __VLS_ctx.notificationPermission === 'default'
            }) },
    });
    (__VLS_ctx.permissionText);
    if (__VLS_ctx.notificationPermission !== 'granted') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.enableNotifications) },
            ...{ class: "btn btn-primary" },
            disabled: (__VLS_ctx.isEnablingNotifications),
        });
        (__VLS_ctx.isEnablingNotifications ? 'Enabling...' : 'Enable Notifications');
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.disableNotifications) },
            ...{ class: "btn btn-secondary" },
            disabled: (__VLS_ctx.isDisablingNotifications),
        });
        (__VLS_ctx.isDisablingNotifications ? 'Disabling...' : 'Disable Notifications');
    }
}
if (__VLS_ctx.notificationPermission === 'granted') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "setting-description" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-control" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.sendTestNotification) },
        ...{ class: "btn btn-secondary" },
        disabled: (__VLS_ctx.isSendingTest),
    });
    (__VLS_ctx.isSendingTest ? 'Sending...' : 'Send Test');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.sendLocalTestNotification) },
        ...{ class: "btn btn-primary" },
        ...{ style: {} },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "pwa-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "setting-description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-badge supported" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "setting-description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "setting-control" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-badge supported" },
});
if (__VLS_ctx.statusMessage) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-message" },
        ...{ class: (__VLS_ctx.statusType) },
    });
    (__VLS_ctx.statusMessage);
}
/** @type {__VLS_StyleScopedClasses['pwa-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['pwa-section']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['installed']} */ ;
/** @type {__VLS_StyleScopedClasses['not-installed']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['install-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['online']} */ ;
/** @type {__VLS_StyleScopedClasses['offline']} */ ;
/** @type {__VLS_StyleScopedClasses['pwa-section']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['supported']} */ ;
/** @type {__VLS_StyleScopedClasses['not-supported']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['granted']} */ ;
/** @type {__VLS_StyleScopedClasses['denied']} */ ;
/** @type {__VLS_StyleScopedClasses['default']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['pwa-section']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['supported']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-item']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-info']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-description']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-control']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['supported']} */ ;
/** @type {__VLS_StyleScopedClasses['status-message']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isInstallable: isInstallable,
            isInstalled: isInstalled,
            isOnline: isOnline,
            pushSupported: pushSupported,
            notificationPermission: notificationPermission,
            isEnablingNotifications: isEnablingNotifications,
            isDisablingNotifications: isDisablingNotifications,
            isSendingTest: isSendingTest,
            statusMessage: statusMessage,
            statusType: statusType,
            permissionText: permissionText,
            installApp: installApp,
            enableNotifications: enableNotifications,
            disableNotifications: disableNotifications,
            sendTestNotification: sendTestNotification,
            sendLocalTestNotification: sendLocalTestNotification,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
