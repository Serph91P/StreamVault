import { computed, onMounted, watch, ref } from 'vue';
import { useStreamers } from '@/composables/useStreamers';
import { useWebSocket } from '@/composables/useWebSocket';
import { useRouter } from 'vue-router';
const { streamers, updateStreamer, fetchStreamers, deleteStreamer } = useStreamers();
const { messages, connectionStatus } = useWebSocket();
const router = useRouter();
const isDeleting = ref(null);
const emit = defineEmits();
const sortedStreamers = computed(() => {
    return [...streamers.value].sort((a, b) => {
        // Sort by live status first (live streamers at top)
        if (a.is_live && !b.is_live)
            return -1;
        if (!a.is_live && b.is_live)
            return 1;
        // Then sort by username alphabetically
        return a.username.localeCompare(b.username);
    });
});
const formatDate = (date) => {
    if (!date)
        return 'Never';
    const now = new Date();
    const updated = new Date(date);
    const diff = now.getTime() - updated.getTime();
    // Less than a minute ago
    if (diff < 60 * 1000) {
        return 'Just now';
    }
    // Less than an hour ago
    if (diff < 60 * 60 * 1000) {
        const minutes = Math.floor(diff / (60 * 1000));
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    }
    // Less than a day ago
    if (diff < 24 * 60 * 60 * 1000) {
        const hours = Math.floor(diff / (60 * 60 * 1000));
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    // Show full date for older updates
    return updated.toLocaleString();
};
const navigateToTwitch = (username) => {
    window.open(`https://twitch.tv/${username}`, '_blank');
};
const handleDelete = async (streamerId) => {
    if (!confirm('Are you sure you want to delete this streamer?'))
        return;
    isDeleting.value = streamerId;
    try {
        if (await deleteStreamer(streamerId)) {
            emit('streamerDeleted');
        }
    }
    finally {
        isDeleting.value = null;
    }
};
const navigateToStreamerDetail = (streamerId, username) => {
    router.push({
        name: 'streamer-detail',
        params: { id: streamerId },
        query: { name: username }
    });
};
watch(messages, (newMessages) => {
    const message = newMessages[newMessages.length - 1];
    if (!message)
        return;
    console.log('StreamerList: New message detected:', message);
    switch (message.type) {
        case 'channel.update': {
            console.log('StreamerList: Processing channel update:', message.data);
            const streamerId = message.data.streamer_id;
            const streamer = streamers.value.find(s => s.id === streamerId);
            const updateData = {
                title: message.data.title || '',
                category_name: message.data.category_name || '',
                language: message.data.language || '',
                last_updated: new Date().toISOString()
                // Keep current live status
            };
            console.log('StreamerList: Updating streamer with data:', updateData);
            updateStreamer(streamerId, updateData);
            break;
        }
        case 'stream.online': {
            console.log('StreamerList: Processing stream online:', message.data);
            const updateData = {
                is_live: true,
                title: message.data.title || '',
                category_name: message.data.category_name || '',
                language: message.data.language || '',
                last_updated: new Date().toISOString()
            };
            updateStreamer(message.data.streamer_id, updateData);
            break;
        }
        case 'stream.offline': {
            console.log('StreamerList: Processing stream offline:', message.data);
            const updateData = {
                is_live: false,
                last_updated: new Date().toISOString()
            };
            updateStreamer(message.data.streamer_id, updateData);
            break;
        }
        case 'recording.started': {
            console.log('StreamerList: Processing recording started:', message.data);
            const streamerId = message.data.streamer_id;
            const streamer = streamers.value.find(s => s.id === streamerId);
            if (streamer) {
                streamer.is_recording = true;
            }
            break;
        }
        case 'recording.stopped': {
            console.log('StreamerList: Processing recording stopped:', message.data);
            const streamerId = message.data.streamer_id;
            const streamer = streamers.value.find(s => s.id === streamerId);
            if (streamer) {
                streamer.is_recording = false;
            }
            break;
        }
    }
}, { deep: true });
// Improved connection handling
watch(connectionStatus, (status) => {
    if (status === 'connected') {
        void fetchStreamers();
    }
}, { immediate: true });
onMounted(() => {
    console.log('StreamerList mounted');
    void fetchStreamers();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name-link']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-content']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-content']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streamer-grid" },
});
const __VLS_0 = {}.TransitionGroup;
/** @type {[typeof __VLS_components.TransitionGroup, typeof __VLS_components.TransitionGroup, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    name: "streamer-card",
}));
const __VLS_2 = __VLS_1({
    name: "streamer-card",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
for (const [streamer] of __VLS_getVForSourceType((__VLS_ctx.sortedStreamers))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (streamer.id),
        ...{ class: "streamer-card" },
        ...{ class: ({ 'live': streamer.is_live }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "profile-image-wrapper" },
    });
    if (streamer.profile_image_url) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
            src: (streamer.profile_image_url),
            ...{ class: "profile-image" },
            alt: (streamer.username),
            loading: "lazy",
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-dot" },
        ...{ class: ({ 'live': streamer.is_live }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.navigateToTwitch(streamer.username);
            } },
        ...{ class: "streamer-name-link" },
    });
    (streamer.username);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-badges" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-badge" },
        ...{ class: ({ 'live': streamer.is_live }) },
    });
    (streamer.is_live ? 'LIVE' : 'OFFLINE');
    if (streamer.is_live && streamer.is_recording) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "status-badge recording" },
            title: "Currently recording",
        });
    }
    else if (streamer.is_live && !streamer.recording_enabled) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "status-badge not-recording" },
            title: "Recording disabled for this streamer",
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-content" },
    });
    if (streamer.title) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (streamer.title || '-');
    }
    if (streamer.category_name) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (streamer.category_name || '-');
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (streamer.language || '-');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.formatDate(streamer.last_updated));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streamer-footer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.handleDelete(streamer.id);
            } },
        ...{ class: "btn btn-danger" },
        disabled: (__VLS_ctx.isDeleting === streamer.id),
    });
    if (__VLS_ctx.isDeleting === streamer.id) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "loader" },
        });
    }
    (__VLS_ctx.isDeleting === streamer.id ? '' : 'Remove');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.navigateToStreamerDetail(streamer.id, streamer.username);
            } },
        ...{ class: "btn btn-primary" },
    });
}
var __VLS_3;
if (!__VLS_ctx.sortedStreamers.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
/** @type {__VLS_StyleScopedClasses['streamer-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-card']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-header']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['profile-image-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['profile-image']} */ ;
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name-link']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['recording']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['not-recording']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-content']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-icon']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isDeleting: isDeleting,
            sortedStreamers: sortedStreamers,
            formatDate: formatDate,
            navigateToTwitch: navigateToTwitch,
            handleDelete: handleDelete,
            navigateToStreamerDetail: navigateToStreamerDetail,
        };
    },
    __typeEmits: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
});
; /* PartiallyEnd: #4569/main.vue */
