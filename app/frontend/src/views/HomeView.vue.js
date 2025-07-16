import { onMounted, computed, ref, watch } from 'vue';
import { useStreamers } from '@/composables/useStreamers';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useWebSocket } from '@/composables/useWebSocket';
const { streamers, fetchStreamers, updateStreamer } = useStreamers();
const { activeRecordings, fetchActiveRecordings } = useRecordingSettings();
const { messages, connectionStatus } = useWebSocket();
const totalStreamers = computed(() => streamers.value.length);
const liveStreamers = computed(() => streamers.value.filter(s => s.is_live).length);
const totalActiveRecordings = computed(() => activeRecordings.value ? activeRecordings.value.length : 0);
// For last recording, fetch all streams and find the latest ended stream
const lastRecording = ref(null);
const lastRecordingStreamer = ref(null);
const isLoadingLastRecording = ref(false);
async function fetchLastRecording() {
    isLoadingLastRecording.value = true;
    try {
        // Use a single API call to get the latest recording instead of looping through all streamers
        const response = await fetch('/api/recordings/latest');
        if (response.ok) {
            const data = await response.json();
            lastRecording.value = data.recording || null;
            if (data.recording) {
                lastRecordingStreamer.value = streamers.value.find(s => String(s.id) === String(data.recording.streamer_id));
            }
        }
        else {
            // Fallback: Get only last 5 recordings from a dedicated endpoint
            const fallbackResponse = await fetch('/api/recordings/recent?limit=1');
            if (fallbackResponse.ok) {
                const fallbackData = await fallbackResponse.json();
                const recordings = fallbackData.recordings || [];
                lastRecording.value = recordings[0] || null;
                if (recordings[0]) {
                    lastRecordingStreamer.value = streamers.value.find(s => String(s.id) === String(recordings[0].streamer_id));
                }
            }
        }
    }
    catch (error) {
        console.error('Failed to fetch last recording:', error);
        lastRecording.value = null;
        lastRecordingStreamer.value = null;
    }
    isLoadingLastRecording.value = false;
}
// WebSocket message handling
watch(messages, (newMessages) => {
    const message = newMessages[newMessages.length - 1];
    if (!message)
        return;
    switch (message.type) {
        case 'stream.online': {
            updateStreamer(String(message.data.streamer_id), {
                is_live: true,
                title: message.data.title || '',
                category_name: message.data.category_name || '',
                language: message.data.language || '',
                last_updated: new Date().toISOString()
            });
            break;
        }
        case 'stream.offline': {
            updateStreamer(String(message.data.streamer_id), {
                is_live: false,
                last_updated: new Date().toISOString()
            });
            break;
        }
        case 'recording.started': {
            const streamerId = Number(message.data.streamer_id);
            const streamer = streamers.value.find(s => String(s.id) === String(streamerId));
            if (streamer) {
                streamer.is_recording = true;
            }
            // Refresh active recordings count
            fetchActiveRecordings();
            break;
        }
        case 'recording.stopped': {
            const streamerId = Number(message.data.streamer_id);
            const streamer = streamers.value.find(s => String(s.id) === String(streamerId));
            if (streamer) {
                streamer.is_recording = false;
            }
            // Refresh active recordings count
            fetchActiveRecordings();
            break;
        }
    }
}, { deep: true });
// Connection status handling
watch(connectionStatus, (status) => {
    if (status === 'connected') {
        void fetchStreamers();
        void fetchActiveRecordings();
    }
}, { immediate: true });
onMounted(async () => {
    await fetchStreamers();
    await fetchActiveRecordings();
    await fetchLastRecording();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['status-box']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-actions']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "home-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-box" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "dashboard-stats" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.totalStreamers);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.liveStreamers);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.totalActiveRecordings);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "stat-value" },
});
if (__VLS_ctx.isLoadingLastRecording) {
}
else if (__VLS_ctx.lastRecording) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.lastRecording.streamer_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.br)({});
    (__VLS_ctx.lastRecording.title || 'Untitled');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.br)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.lastRecording.ended_at ? new Date(__VLS_ctx.lastRecording.ended_at).toLocaleString() : '');
}
else {
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "dashboard-actions" },
});
const __VLS_0 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    to: "/streamers",
    ...{ class: "btn btn-primary" },
}));
const __VLS_2 = __VLS_1({
    to: "/streamers",
    ...{ class: "btn btn-primary" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
var __VLS_3;
const __VLS_4 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    to: "/add-streamer",
    ...{ class: "btn btn-secondary" },
}));
const __VLS_6 = __VLS_5({
    to: "/add-streamer",
    ...{ class: "btn btn-secondary" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['home-view']} */ ;
/** @type {__VLS_StyleScopedClasses['container']} */ ;
/** @type {__VLS_StyleScopedClasses['status-box']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-stats']} */ ;
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
/** @type {__VLS_StyleScopedClasses['dashboard-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            totalStreamers: totalStreamers,
            liveStreamers: liveStreamers,
            totalActiveRecordings: totalActiveRecordings,
            lastRecording: lastRecording,
            isLoadingLastRecording: isLoadingLastRecording,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
