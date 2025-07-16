import { ref, computed, onMounted, onUnmounted, watch, defineEmits } from 'vue';
import { useWebSocket } from '@/composables/useWebSocket';
import { useCategoryImages } from '@/composables/useCategoryImages';
const emit = defineEmits(['notifications-read', 'close-panel', 'clear-all']);
const notifications = ref([]);
const { messages } = useWebSocket();
const { getCategoryImage } = useCategoryImages();
const MAX_NOTIFICATIONS = 100;
// Debounce mechanism to prevent rapid duplicate notifications
const recentNotifications = new Map();
const DEBOUNCE_TIME = 2000; // 2 seconds
// Function to generate a unique key for notifications
const generateNotificationKey = (notification) => {
    return `${notification.type}_${notification.streamer_username}_${notification.data?.title || ''}`;
};
// Sort notifications by timestamp (newest first)
const sortedNotifications = computed(() => {
    return [...notifications.value].sort((a, b) => {
        return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });
});
// Format relative time (e.g. "5 minutes ago")
const formatTime = (timestamp) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diff = now.getTime() - time.getTime();
    if (diff < 60 * 1000) {
        return 'Just now';
    }
    if (diff < 60 * 60 * 1000) {
        const minutes = Math.floor(diff / (60 * 1000));
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    }
    if (diff < 24 * 60 * 60 * 1000) {
        const hours = Math.floor(diff / (60 * 60 * 1000));
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    }
    if (diff < 7 * 24 * 60 * 60 * 1000) {
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        return `${days} day${days !== 1 ? 's' : ''} ago`;
    }
    return time.toLocaleDateString();
};
// Format notification title based on type
const formatTitle = (notification) => {
    const username = notification.streamer_username || notification.data?.streamer_name || notification.data?.username || 'Unknown';
    if (notification.data?.test_id) {
        return 'Test Notification';
    }
    switch (notification.type) {
        case 'stream.online':
            return `${username} is Live`;
        case 'stream.offline':
            return `${username} Stream Ended`;
        case 'channel.update':
        case 'stream.update':
            return `${username} Updated Stream`;
        case 'recording.started':
            return `Recording Started`;
        case 'recording.completed':
            return `Recording Completed`;
        case 'recording.failed':
            return `Recording Failed`;
        default:
            return notification.title || 'Notification';
    }
};
// Format notification message based on type and data
const formatMessage = (notification) => {
    const { type, data } = notification;
    const username = notification.streamer_username || data?.streamer_name || data?.username || 'Unknown';
    if (data?.message) {
        return data.message;
    }
    switch (type) {
        case 'stream.online':
            return data?.title ? `${username} is live: "${data.title}"` : `${username} is now streaming`;
        case 'stream.offline':
            return `${username} has gone offline`;
        case 'channel.update':
        case 'stream.update':
            return data?.title ? `New title: ${data.title}` : `${username} updated their stream`;
        case 'recording.started':
            return `Started recording ${username}'s stream`;
        case 'recording.completed':
            return `Successfully completed recording ${username}'s stream`;
        case 'recording.failed':
            return data?.error ? `Failed to record ${username}'s stream: ${data.error}` : `Failed to record ${username}'s stream`;
        case 'test':
            return data?.message || 'This is a test notification to verify the system is working properly';
        default:
            return `New notification for ${username}`;
    }
};
// Get CSS class based on notification type
const getNotificationClass = (type) => {
    switch (type) {
        case 'stream.online':
            return 'online';
        case 'stream.offline':
            return 'offline';
        case 'channel.update':
        case 'stream.update':
            return 'update';
        case 'recording.started':
            return 'recording';
        case 'recording.completed':
            return 'success';
        case 'recording.failed':
            return 'error';
        case 'test':
            return 'test';
        default:
            return 'info';
    }
};
// Add a new notification - IMPROVED VERSION
const addNotification = (message) => {
    console.log('🔥 NotificationFeed: ADDING NOTIFICATION:', message);
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
        console.log('🔥 NotificationFeed: CREATED NOTIFICATION:', newNotification);
        // Check debounce to prevent rapid duplicates
        const notificationKey = generateNotificationKey(newNotification);
        const now = Date.now();
        const lastTime = recentNotifications.get(notificationKey);
        if (lastTime && (now - lastTime) < DEBOUNCE_TIME) {
            console.log('🔥 NotificationFeed: Notification debounced (too soon after last identical notification)');
            return;
        }
        // Update debounce tracker
        recentNotifications.set(notificationKey, now);
        // Clean up old debounce entries (older than 5 minutes)
        for (const [key, time] of recentNotifications.entries()) {
            if (now - time > 300000) { // 5 minutes
                recentNotifications.delete(key);
            }
        }
        // Enhanced duplicate detection
        const isDuplicate = (existing, incoming) => {
            // Same type and streamer
            if (existing.type !== incoming.type || existing.streamer_username !== incoming.streamer_username) {
                return false;
            }
            // For stream updates, check if title/content is the same
            if (incoming.type === 'channel.update' || incoming.type === 'stream.update') {
                const existingTitle = existing.data?.title || '';
                const incomingTitle = incoming.data?.title || '';
                // If same title and within 30 seconds, it's a duplicate
                const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime());
                if (existingTitle === incomingTitle && timeDiff < 30000) {
                    return true;
                }
            }
            // For stream.online, check within 10 seconds
            if (incoming.type === 'stream.online') {
                const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime());
                return timeDiff < 10000;
            }
            // For recording events, check within 5 seconds
            if (incoming.type.startsWith('recording.')) {
                const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime());
                return timeDiff < 5000;
            }
            return false;
        };
        // Find existing duplicate
        const existingIndex = notifications.value.findIndex(n => isDuplicate(n, newNotification));
        if (existingIndex >= 0) {
            console.log('🔥 NotificationFeed: Duplicate notification found, replacing');
            notifications.value[existingIndex] = newNotification;
        }
        else {
            console.log('🔥 NotificationFeed: Adding new notification');
            // Add to beginning
            notifications.value.unshift(newNotification);
        }
        // Limit notifications
        if (notifications.value.length > MAX_NOTIFICATIONS) {
            notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS);
        }
        console.log('🔥 NotificationFeed: NOTIFICATIONS ARRAY NOW HAS:', notifications.value.length, 'items');
        console.log('🔥 NotificationFeed: ALL NOTIFICATIONS:', notifications.value);
        // Save to localStorage
        saveNotifications();
    }
    catch (error) {
        console.error('❌ NotificationFeed: Error adding notification:', error);
    }
};
// Remove a specific notification
const removeNotification = (id) => {
    notifications.value = notifications.value.filter(n => n.id !== id);
    saveNotifications();
};
// Clear all notifications
const clearAllNotifications = (event) => {
    console.log('🗑️ NotificationFeed: Clear all button clicked!');
    console.log('🗑️ NotificationFeed: Event object:', event);
    console.log('🗑️ NotificationFeed: Event target:', event?.target);
    console.log('🗑️ NotificationFeed: Current notifications count:', notifications.value.length);
    // Prevent any default behavior or propagation
    if (event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
    }
    // Clear notifications directly
    notifications.value = [];
    console.log('🗑️ NotificationFeed: Cleared notifications array directly');
    // Clear localStorage immediately and confirm
    try {
        localStorage.removeItem('streamvault_notifications');
        const check = localStorage.getItem('streamvault_notifications');
        console.log('🗑️ NotificationFeed: localStorage after removal:', check);
        // Set empty array to be extra sure
        localStorage.setItem('streamvault_notifications', JSON.stringify([]));
        const checkAgain = localStorage.getItem('streamvault_notifications');
        console.log('🗑️ NotificationFeed: localStorage after setting empty array:', checkAgain);
    }
    catch (error) {
        console.error('❌ NotificationFeed: Error clearing localStorage:', error);
    }
    // Dispatch event immediately
    window.dispatchEvent(new CustomEvent('notificationsUpdated', {
        detail: { count: 0 }
    }));
    console.log('🗑️ NotificationFeed: Dispatched notificationsUpdated event');
    // Also emit to App.vue for any additional cleanup
    emit('clear-all');
    console.log('🗑️ NotificationFeed: Emitted clear-all event to App.vue');
    // Close the panel after clearing
    emit('close-panel');
    console.log('🗑️ NotificationFeed: Emitted close-panel event');
};
// Save notifications to localStorage
const saveNotifications = () => {
    try {
        localStorage.setItem('streamvault_notifications', JSON.stringify(notifications.value));
        console.log('💾 NotificationFeed: Saved', notifications.value.length, 'notifications to localStorage');
        // Dispatch a custom event to notify other components (like App.vue) that notifications changed
        window.dispatchEvent(new CustomEvent('notificationsUpdated', {
            detail: { count: notifications.value.length }
        }));
    }
    catch (error) {
        console.error('❌ NotificationFeed: Error saving notifications:', error);
    }
};
// Load notifications from localStorage
const loadNotifications = () => {
    try {
        const saved = localStorage.getItem('streamvault_notifications');
        console.log('📂 NotificationFeed: Raw localStorage value:', saved);
        if (saved) {
            const parsed = JSON.parse(saved);
            console.log('📂 NotificationFeed: Parsed localStorage value:', parsed);
            if (Array.isArray(parsed) && parsed.length > 0) {
                notifications.value = parsed;
                console.log('📂 NotificationFeed: Loaded', parsed.length, 'notifications from localStorage');
            }
            else {
                notifications.value = [];
                console.log('📂 NotificationFeed: Empty or invalid array in localStorage, starting with empty notifications');
            }
        }
        else {
            notifications.value = [];
            console.log('📂 NotificationFeed: No localStorage data found, starting with empty notifications');
        }
    }
    catch (error) {
        console.error('❌ NotificationFeed: Error loading notifications:', error);
        notifications.value = [];
    }
};
// Process WebSocket message
const processMessage = (message) => {
    console.log('⚡ NotificationFeed: PROCESSING MESSAGE:', message);
    if (!message || !message.type) {
        console.log('❌ NotificationFeed: Invalid message');
        return;
    }
    // Skip connection status messages
    if (message.type === 'connection.status') {
        console.log('⏭️ NotificationFeed: Skipping connection status');
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
        'test' // Add test type
    ];
    if (validTypes.includes(message.type)) {
        console.log('✅ NotificationFeed: Valid message type, adding notification');
        addNotification(message);
    }
    else {
        console.log('❌ NotificationFeed: Invalid message type:', message.type);
    }
};
// Track previous message count to detect actual changes
const previousMessageCount = ref(0);
// Watch for new messages - IMPROVED VERSION
watch(() => messages.value.length, (newLength) => {
    console.log('🔥 NotificationFeed: Message count changed to', newLength, 'from', previousMessageCount.value);
    if (newLength > previousMessageCount.value) {
        console.log('🔥 NotificationFeed: NEW MESSAGES DETECTED!');
        // Process only the new messages since last check
        const newCount = newLength - previousMessageCount.value;
        const messagesToProcess = messages.value.slice(-newCount);
        console.log('🔥 NotificationFeed: Processing', messagesToProcess.length, 'new messages');
        messagesToProcess.forEach((message, index) => {
            console.log(`🔥 NotificationFeed: Processing new message ${index + 1}:`, message);
            processMessage(message);
        });
        // Update our counter for next time
        previousMessageCount.value = newLength;
    }
}, { immediate: false }); // Don't process immediately to avoid double processing
// On mount
onMounted(() => {
    console.log('🚀 NotificationFeed: Component mounted');
    // Load existing notifications from localStorage FIRST
    loadNotifications();
    // Set the initial message count to current messages length
    previousMessageCount.value = messages.value.length;
    console.log('🚀 NotificationFeed: Set initial message count to', previousMessageCount.value);
    // Process ALL existing WebSocket messages (they may not be in localStorage yet)
    console.log('🚀 NotificationFeed: Processing', messages.value.length, 'existing WebSocket messages');
    messages.value.forEach((message, index) => {
        console.log(`🚀 NotificationFeed: Processing existing message ${index + 1}:`, message);
        processMessage(message);
    });
    console.log('🚀 NotificationFeed: Component fully loaded with', notifications.value.length, 'notifications');
    // Listen for external notification updates (like clear all from App.vue)
    window.addEventListener('notificationsUpdated', handleNotificationsUpdated);
    // DON'T auto-mark as read - let the user see the notifications until they manually close the panel
});
// Handle external notification updates
const handleNotificationsUpdated = (event) => {
    console.log('📡 NotificationFeed: Received notificationsUpdated event:', event.detail);
    // Reload notifications from localStorage to stay in sync
    loadNotifications();
};
// Mark notifications as read when component is unmounted (panel closes)
onUnmounted(() => {
    console.log('🚀 NotificationFeed: Component unmounting, marking notifications as read');
    // Remove event listener
    window.removeEventListener('notificationsUpdated', handleNotificationsUpdated);
    emit('notifications-read');
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['online']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['offline']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['update']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['recording']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['success']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['info']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['test']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-small']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-small']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-feed']} */ ;
/** @type {__VLS_StyleScopedClasses['feed-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['bell-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['section-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-content']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-header']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-title']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-time']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-message']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['category-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-small']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['feed-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['section-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-title']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-message']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-feed']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-feed" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "feed-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-icon" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "icon-ring" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "bell-icon" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "section-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "section-subtitle" },
});
(__VLS_ctx.notifications.length);
(__VLS_ctx.notifications.length !== 1 ? 's' : '');
if (__VLS_ctx.notifications.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.clearAllNotifications) },
        ...{ onMousedown: () => { } },
        ...{ onMouseup: () => { } },
        ...{ onTouchstart: (__VLS_ctx.clearAllNotifications) },
        ...{ class: "clear-all-btn" },
        'aria-label': "Clear all notifications",
        type: "button",
        ref: "clearButton",
    });
    /** @type {typeof __VLS_ctx.clearButton} */ ;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ onClick: (__VLS_ctx.clearAllNotifications) },
        ...{ class: "clear-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ onClick: (__VLS_ctx.clearAllNotifications) },
        ...{ class: "clear-text" },
    });
}
if (__VLS_ctx.notifications.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-notifications" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "icon-circle" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    const __VLS_0 = {}.TransitionGroup;
    /** @type {[typeof __VLS_components.TransitionGroup, typeof __VLS_components.TransitionGroup, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        name: "notification",
        tag: "div",
        ...{ class: "notification-list" },
    }));
    const __VLS_2 = __VLS_1({
        name: "notification",
        tag: "div",
        ...{ class: "notification-list" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    for (const [notification] of __VLS_getVForSourceType((__VLS_ctx.sortedNotifications))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (notification.id),
            ...{ class: "notification-item" },
            ...{ class: (__VLS_ctx.getNotificationClass(notification.type)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "notification-indicator" },
            ...{ class: (__VLS_ctx.getNotificationClass(notification.type)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "notification-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "icon-wrapper" },
            ...{ class: (__VLS_ctx.getNotificationClass(notification.type)) },
        });
        if (notification.type === 'stream.online') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'stream.offline') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'channel.update' || notification.type === 'stream.update') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'recording.started') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'recording.completed') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'recording.failed') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else if (notification.type === 'test') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "notification-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "notification-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "notification-title" },
        });
        (__VLS_ctx.formatTitle(notification));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "notification-time" },
        });
        (__VLS_ctx.formatTime(notification.timestamp));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "notification-message" },
        });
        (__VLS_ctx.formatMessage(notification));
        if (notification.data?.game_name || notification.data?.category_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "category-tag" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "category-image-small" },
            });
            if (!__VLS_ctx.getCategoryImage(notification.data?.game_name || notification.data?.category_name || '').startsWith('icon:')) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                    src: (__VLS_ctx.getCategoryImage(notification.data?.game_name || notification.data?.category_name || '')),
                    alt: (notification.data?.game_name || notification.data?.category_name),
                    loading: "lazy",
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: (__VLS_ctx.getCategoryImage(notification.data?.game_name || notification.data?.category_name || '').replace('icon:', '')) },
                    ...{ class: "category-icon" },
                });
            }
            (notification.data?.game_name || notification.data?.category_name);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.notifications.length === 0))
                        return;
                    __VLS_ctx.removeNotification(notification.id);
                } },
            ...{ class: "notification-dismiss" },
            'aria-label': "Dismiss notification",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "dismiss-icon" },
        });
    }
    var __VLS_3;
}
/** @type {__VLS_StyleScopedClasses['notification-feed']} */ ;
/** @type {__VLS_StyleScopedClasses['feed-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-ring']} */ ;
/** @type {__VLS_StyleScopedClasses['bell-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['header-text']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['section-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['clear-text']} */ ;
/** @type {__VLS_StyleScopedClasses['no-notifications']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-content']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-header']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-title']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-time']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-message']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['category-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-small']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['dismiss-icon']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            notifications: notifications,
            getCategoryImage: getCategoryImage,
            sortedNotifications: sortedNotifications,
            formatTime: formatTime,
            formatTitle: formatTitle,
            formatMessage: formatMessage,
            getNotificationClass: getNotificationClass,
            removeNotification: removeNotification,
            clearAllNotifications: clearAllNotifications,
        };
    },
    emits: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    emits: {},
});
; /* PartiallyEnd: #4569/main.vue */
