import NotificationFeed from '@/components/NotificationFeed.vue';
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue';
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue';
import '@/styles/main.scss';
import { ref, onMounted, watch } from 'vue';
import { useWebSocket } from '@/composables/useWebSocket';
import { useAuth } from '@/composables/useAuth';
const showNotifications = ref(false);
const unreadCount = ref(0);
const lastReadTimestamp = ref(localStorage.getItem('lastReadTimestamp') || '0');
const { messages } = useWebSocket();
const { logout: authLogout, checkStoredAuth } = useAuth();
// PWA-compatible logout function
async function logout() {
    if (confirm('Are you sure you want to logout?')) {
        await authLogout();
    }
}
// PWA AUTH FIX: Check stored auth on app start
onMounted(async () => {
    await checkStoredAuth();
});
// WebSocket message processing - moved here so it runs even when notification panel is closed
const processWebSocketMessage = (message) => {
    console.log('🔥 App: Processing WebSocket message:', message);
    if (!message || !message.type) {
        console.log('❌ App: Invalid message');
        return;
    }
    // Skip connection status messages
    if (message.type === 'connection.status') {
        console.log('⏭️ App: Skipping connection status');
        return;
    }
    // Valid notification types
    const validTypes = [
        'stream.online',
        'stream.offline',
        'channel.update',
        'stream.update',
        'recording.started',
        'recording.completed',
        'recording.failed',
        'test'
    ];
    if (validTypes.includes(message.type)) {
        console.log('✅ App: Valid message type, adding to localStorage');
        addNotificationToStorage(message);
    }
    else {
        console.log('❌ App: Invalid message type:', message.type);
    }
};
// Add notification to localStorage - similar to NotificationFeed logic
const addNotificationToStorage = (message) => {
    try {
        const id = message.data?.test_id || `${message.type}_${Date.now()}_${Math.random()}`;
        const timestamp = message.data?.timestamp
            ? new Date(parseInt(message.data.timestamp) || message.data.timestamp).toISOString()
            : new Date().toISOString();
        const streamer_username = message.data?.username ||
            message.data?.streamer_name ||
            'Unknown';
        const newNotification = {
            id,
            type: message.type,
            timestamp,
            streamer_username,
            data: message.data || {}
        };
        console.log('🔥 App: Created notification:', newNotification);
        // Get existing notifications
        let notifications = [];
        try {
            const existing = localStorage.getItem('streamvault_notifications');
            if (existing) {
                notifications = JSON.parse(existing);
            }
        }
        catch (e) {
            notifications = [];
        }
        // Add new notification to beginning
        notifications.unshift(newNotification);
        // Limit notifications
        if (notifications.length > 100) {
            notifications = notifications.slice(0, 100);
        }
        // Save back to localStorage
        localStorage.setItem('streamvault_notifications', JSON.stringify(notifications));
        console.log('💾 App: Saved notification to localStorage. Total notifications:', notifications.length);
        // Update unread count
        updateUnreadCountFromStorage();
        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('notificationsUpdated', {
            detail: { count: notifications.length }
        }));
    }
    catch (error) {
        console.error('❌ App: Error adding notification to localStorage:', error);
    }
};
// Track previous message count to detect new messages
let previousMessageCount = 0;
// Watch for new WebSocket messages
watch(() => messages.value.length, (newLength) => {
    console.log('🔥 App: Message count changed to', newLength, 'from', previousMessageCount);
    if (newLength > previousMessageCount) {
        console.log('🔥 App: NEW MESSAGES DETECTED!');
        // Process only the new messages
        const newCount = newLength - previousMessageCount;
        const messagesToProcess = messages.value.slice(-newCount);
        console.log('🔥 App: Processing', messagesToProcess.length, 'new messages');
        messagesToProcess.forEach((message, index) => {
            console.log(`🔥 App: Processing new message ${index + 1}:`, message);
            processWebSocketMessage(message);
        });
        previousMessageCount = newLength;
    }
}, { immediate: false });
function toggleNotifications() {
    console.log('🔔 App: Toggling notifications panel');
    showNotifications.value = !showNotifications.value;
    if (showNotifications.value) {
        console.log('🔔 Notifications panel opened');
        // Don't recalculate unread count when opening - let the notifications stay visible
    }
    else {
        console.log('🔔 Notifications panel closed');
    }
}
function markAsRead() {
    console.log('🔔 App: Marking all notifications as read');
    unreadCount.value = 0;
    lastReadTimestamp.value = Date.now().toString();
    localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value);
    console.log('🔔 App: Updated lastReadTimestamp in localStorage to:', lastReadTimestamp.value);
}
function clearAllNotifications() {
    console.log('🔔 App: Clearing all notifications - Event received from NotificationFeed');
    // Clear the notifications from localStorage (redundant but safe)
    localStorage.removeItem('streamvault_notifications');
    // Mark as read
    markAsRead();
    // Reset notification count
    notificationCount.value = 0;
    // Dispatch event to notify other components
    window.dispatchEvent(new CustomEvent('notificationsUpdated', {
        detail: { count: 0 }
    }));
    console.log('🔔 App: All notifications cleared successfully');
}
function closeNotificationPanel() {
    if (showNotifications.value) {
        console.log('🔔 App: Closing notification panel');
        showNotifications.value = false;
        markAsRead(); // Mark as read when panel closes
    }
}
// Function to update unread count from localStorage
function updateUnreadCountFromStorage() {
    const notificationsStr = localStorage.getItem('streamvault_notifications');
    console.log('🔄 App: Checking localStorage for notifications');
    if (notificationsStr) {
        try {
            const notifications = JSON.parse(notificationsStr);
            console.log('🔄 App: Found notifications in localStorage:', notifications.length);
            if (Array.isArray(notifications)) {
                // Only count real notification types, not connection status
                const validNotificationTypes = [
                    'stream.online',
                    'stream.offline',
                    'channel.update',
                    'stream.update',
                    'recording.started',
                    'recording.completed',
                    'recording.failed',
                    'test' // Add test notification type to be counted
                ];
                const unread = notifications.filter(n => {
                    const notifTimestamp = new Date(n.timestamp).getTime();
                    const isValidType = validNotificationTypes.includes(n.type);
                    const isUnread = notifTimestamp > parseInt(lastReadTimestamp.value);
                    console.log(`🔄 App: Notification ${n.id} - Type: ${n.type}, Valid: ${isValidType}, Unread: ${isUnread}`);
                    return isValidType && isUnread;
                });
                unreadCount.value = unread.length;
                console.log('🔢 App: Updated unread count to:', unreadCount.value, 'notifications');
                // Log the actual unread notifications for debugging
                if (unread.length > 0) {
                    console.log('🔢 App: Unread notifications:', unread);
                }
            }
        }
        catch (e) {
            console.error('❌ App: Failed to parse notifications from localStorage', e);
        }
    }
    else {
        console.log('🔄 App: No notifications found in localStorage');
        unreadCount.value = 0;
    }
}
// Update unread count from localStorage on mount
onMounted(() => {
    updateUnreadCountFromStorage();
    // Set initial message count
    previousMessageCount = messages.value.length;
    console.log('🚀 App: Set initial message count to', previousMessageCount);
    // Process any existing WebSocket messages
    if (messages.value.length > 0) {
        console.log('🚀 App: Processing', messages.value.length, 'existing WebSocket messages');
        messages.value.forEach((message, index) => {
            console.log(`🚀 App: Processing existing message ${index + 1}:`, message);
            processWebSocketMessage(message);
        });
    }
    // Listen for clicks outside the notification area to close it
    document.addEventListener('click', (event) => {
        const notificationFeed = document.querySelector('.notification-feed');
        const notificationBell = document.querySelector('.notification-bell');
        if (showNotifications.value &&
            notificationFeed &&
            notificationBell &&
            !notificationFeed.contains(event.target) &&
            !notificationBell.contains(event.target)) {
            closeNotificationPanel(); // Use the proper close function instead of just setting the value
        }
    });
    // Listen for localStorage changes to update count
    window.addEventListener('storage', (e) => {
        if (e.key === 'streamvault_notifications') {
            console.log('📦 App: localStorage notifications changed, updating count');
            updateUnreadCountFromStorage();
        }
    });
    // Listen for custom notifications updated event
    window.addEventListener('notificationsUpdated', () => {
        console.log('📦 App: Custom notificationsUpdated event received, updating count');
        updateUnreadCountFromStorage();
    });
});
// Track the previous message count to detect actual changes
const previousMessageCountApp = ref(0);
// Watch for new messages and update unread count
watch(messages, (newMessages) => {
    console.log('🔄 App: Messages watcher triggered. Messages count:', newMessages.length);
    if (!newMessages || newMessages.length === 0)
        return;
    // Check if we have new messages
    if (newMessages.length > previousMessageCountApp.value) {
        // Get only the new messages since last check
        const newCount = newMessages.length - previousMessageCountApp.value;
        const newMessagesToProcess = newMessages.slice(-newCount);
        // Update our counter for next time
        previousMessageCountApp.value = newMessages.length;
        // Process each new message - but only count them, don't store them (NotificationFeed handles storage)
        newMessagesToProcess.forEach(newMessage => {
            console.log('🔄 App: Processing new message for counting:', newMessage);
            // Only count specific notification types (exclude connection.status to prevent false positives)
            const notificationTypes = [
                'stream.online',
                'stream.offline',
                'channel.update',
                'stream.update',
                'recording.started',
                'recording.completed',
                'recording.failed',
                'test'
            ];
            // Only increment if it's a valid notification type AND panel is not currently shown
            if (notificationTypes.includes(newMessage.type) && !showNotifications.value) {
                console.log('🔢 App: Valid notification type for counter:', newMessage.type);
                // Check if this notification has already been counted
                const notificationTimestamp = newMessage.data?.timestamp || Date.now();
                if (parseInt(notificationTimestamp) > parseInt(lastReadTimestamp.value)) {
                    unreadCount.value++;
                    console.log('🔢 App: Unread count is now', unreadCount.value);
                }
                else {
                    console.log('🔢 App: Notification timestamp older than last read, not incrementing count');
                }
            }
            else {
                console.log('⏭️ App: Skipping unread count for message type:', newMessage.type, 'or panel is open:', showNotifications.value);
            }
        });
    }
    else {
        console.log('🔄 App: No new messages detected');
    }
}, { deep: true, immediate: false }); // Don't process immediately
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['logout-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['logout-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-bell']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-bell']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-notification-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-notification-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-notification-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-overlay']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "app" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "app-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "app-logo" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({
    ...{ class: "main-nav" },
});
const __VLS_0 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    to: "/",
    ...{ class: "nav-link" },
}));
const __VLS_2 = __VLS_1({
    to: "/",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
var __VLS_3;
const __VLS_4 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    to: "/streamers",
    ...{ class: "nav-link" },
}));
const __VLS_6 = __VLS_5({
    to: "/streamers",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
var __VLS_7;
const __VLS_8 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    to: "/videos",
    ...{ class: "nav-link" },
}));
const __VLS_10 = __VLS_9({
    to: "/videos",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
var __VLS_11;
const __VLS_12 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    to: "/add-streamer",
    ...{ class: "nav-link" },
}));
const __VLS_14 = __VLS_13({
    to: "/add-streamer",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
const __VLS_16 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    to: "/subscriptions",
    ...{ class: "nav-link" },
}));
const __VLS_18 = __VLS_17({
    to: "/subscriptions",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
const __VLS_20 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    to: "/settings",
    ...{ class: "nav-link" },
}));
const __VLS_22 = __VLS_21({
    to: "/settings",
    ...{ class: "nav-link" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
/** @type {[typeof BackgroundQueueMonitor, ]} */ ;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent(BackgroundQueueMonitor, new BackgroundQueueMonitor({}));
const __VLS_25 = __VLS_24({}, ...__VLS_functionalComponentArgsRest(__VLS_24));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "nav-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-bell-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleNotifications) },
    ...{ class: "notification-bell" },
    ...{ class: ({ 'has-unread': __VLS_ctx.unreadCount > 0 }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "bell-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M13.73 21a2 2 0 0 1-3.46 0",
});
if (__VLS_ctx.unreadCount > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "notification-count" },
    });
    (__VLS_ctx.unreadCount > 99 ? '99+' : __VLS_ctx.unreadCount);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.logout) },
    ...{ class: "logout-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    xmlns: "http://www.w3.org/2000/svg",
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.polyline, __VLS_intrinsicElements.polyline)({
    points: "16 17 21 12 16 7",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "21",
    y1: "12",
    x2: "9",
    y2: "12",
});
if (__VLS_ctx.showNotifications) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-overlay" },
    });
    /** @type {[typeof NotificationFeed, ]} */ ;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent(NotificationFeed, new NotificationFeed({
        ...{ 'onNotificationsRead': {} },
        ...{ 'onClosePanel': {} },
        ...{ 'onClearAll': {} },
    }));
    const __VLS_28 = __VLS_27({
        ...{ 'onNotificationsRead': {} },
        ...{ 'onClosePanel': {} },
        ...{ 'onClearAll': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    let __VLS_30;
    let __VLS_31;
    let __VLS_32;
    const __VLS_33 = {
        onNotificationsRead: (__VLS_ctx.markAsRead)
    };
    const __VLS_34 = {
        onClosePanel: (__VLS_ctx.closeNotificationPanel)
    };
    const __VLS_35 = {
        onClearAll: (__VLS_ctx.clearAllNotifications)
    };
    var __VLS_29;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-content" },
});
const __VLS_36 = {}.RouterView;
/** @type {[typeof __VLS_components.RouterView, typeof __VLS_components.routerView, typeof __VLS_components.RouterView, typeof __VLS_components.routerView, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
{
    const { default: __VLS_thisSlot } = __VLS_39.slots;
    const [{ Component }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_40 = {}.transition;
    /** @type {[typeof __VLS_components.Transition, typeof __VLS_components.transition, typeof __VLS_components.Transition, typeof __VLS_components.transition, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        name: "page",
        mode: "out-in",
    }));
    const __VLS_42 = __VLS_41({
        name: "page",
        mode: "out-in",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = ((Component));
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
    const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
    var __VLS_43;
    __VLS_39.slots['' /* empty slot name completion */];
}
var __VLS_39;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mobile-nav-bottom" },
});
const __VLS_48 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    to: "/",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_50 = __VLS_49({
    to: "/",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.polyline, __VLS_intrinsicElements.polyline)({
    points: "9 22 9 12 15 12 15 22",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_51;
const __VLS_52 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    to: "/streamers",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_54 = __VLS_53({
    to: "/streamers",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "12",
    cy: "12",
    r: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M2 12h20",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_55;
const __VLS_56 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    to: "/videos",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_58 = __VLS_57({
    to: "/videos",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.polygon, __VLS_intrinsicElements.polygon)({
    points: "23 7 16 12 23 17 23 7",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.rect, __VLS_intrinsicElements.rect)({
    x: "1",
    y: "5",
    width: "15",
    height: "14",
    rx: "2",
    ry: "2",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_59;
const __VLS_60 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    to: "/add-streamer",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_62 = __VLS_61({
    to: "/add-streamer",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "12",
    cy: "12",
    r: "10",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "12",
    y1: "8",
    x2: "12",
    y2: "16",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "8",
    y1: "12",
    x2: "16",
    y2: "12",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_63;
const __VLS_64 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    to: "/subscriptions",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_66 = __VLS_65({
    to: "/subscriptions",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M13.73 21a2 2 0 0 1-3.46 0",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_67;
const __VLS_68 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    to: "/settings",
    ...{ class: "mobile-nav-item" },
}));
const __VLS_70 = __VLS_69({
    to: "/settings",
    ...{ class: "mobile-nav-item" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "12",
    cy: "12",
    r: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_71;
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleNotifications) },
    ...{ class: "mobile-nav-item mobile-notification-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    ...{ class: "mobile-nav-icon" },
    xmlns: "http://www.w3.org/2000/svg",
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M13.73 21a2 2 0 0 1-3.46 0",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
if (__VLS_ctx.unreadCount > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "mobile-notification-indicator" },
    });
}
/** @type {[typeof PWAInstallPrompt, ]} */ ;
// @ts-ignore
const __VLS_72 = __VLS_asFunctionalComponent(PWAInstallPrompt, new PWAInstallPrompt({}));
const __VLS_73 = __VLS_72({}, ...__VLS_functionalComponentArgsRest(__VLS_72));
/** @type {__VLS_StyleScopedClasses['app']} */ ;
/** @type {__VLS_StyleScopedClasses['app-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['app-logo']} */ ;
/** @type {__VLS_StyleScopedClasses['main-nav']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-link']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-bell-container']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-bell']} */ ;
/** @type {__VLS_StyleScopedClasses['has-unread']} */ ;
/** @type {__VLS_StyleScopedClasses['bell-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-count']} */ ;
/** @type {__VLS_StyleScopedClasses['logout-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-bottom']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-notification-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mobile-notification-indicator']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            NotificationFeed: NotificationFeed,
            PWAInstallPrompt: PWAInstallPrompt,
            BackgroundQueueMonitor: BackgroundQueueMonitor,
            showNotifications: showNotifications,
            unreadCount: unreadCount,
            logout: logout,
            toggleNotifications: toggleNotifications,
            markAsRead: markAsRead,
            clearAllNotifications: clearAllNotifications,
            closeNotificationPanel: closeNotificationPanel,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
