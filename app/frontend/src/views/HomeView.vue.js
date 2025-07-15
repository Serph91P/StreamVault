import { onMounted, computed, ref } from 'vue';
import { useStreamers } from '@/composables/useStreamers';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
const { streamers, fetchStreamers } = useStreamers();
const { activeRecordings, fetchActiveRecordings } = useRecordingSettings();
const totalStreamers = computed(() => streamers.value.length);
const liveStreamers = computed(() => streamers.value.filter(s => s.is_live).length);
const totalActiveRecordings = computed(() => activeRecordings.value.length);
// For last recording, fetch all streams and find the latest ended stream
const lastRecording = ref(null);
const lastRecordingStreamer = ref(null);
const isLoadingLastRecording = ref(false);
async function fetchLastRecording() {
    isLoadingLastRecording.value = true;
    let allStreams = [];
    for (const streamer of streamers.value) {
        try {
            const response = await fetch(`/api/streamers/${streamer.id}/streams`);
            if (response.ok) {
                const data = await response.json();
                if (data.streams && Array.isArray(data.streams)) { // Add streamer info to each stream
                    const streamsWithStreamer = data.streams.map((stream) => ({
                        ...stream,
                        streamer_name: streamer.username,
                        streamer_id: streamer.id
                    }));
                    allStreams = allStreams.concat(streamsWithStreamer);
                }
            }
        }
        catch (e) {
            // ignore
        }
    }
    // Find the latest ended stream
    const endedStreams = allStreams.filter(s => s.ended_at);
    endedStreams.sort((a, b) => new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime());
    const latestStream = endedStreams[0] || null;
    lastRecording.value = latestStream;
    if (latestStream) {
        lastRecordingStreamer.value = streamers.value.find(s => s.id === latestStream.streamer_id);
    }
    isLoadingLastRecording.value = false;
}
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
