import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import VideoPlayer from '@/components/VideoPlayer.vue';
const route = useRoute();
const router = useRouter();
const streamerId = computed(() => route.params.streamerId);
const streamId = computed(() => route.params.streamId);
const streamTitle = computed(() => route.query.title || `Stream ${streamId.value}`);
const streamerName = computed(() => route.query.streamerName);
const chapterData = ref(null);
const isLoading = ref(true);
const error = ref(null);
const loadChapterData = async () => {
    try {
        isLoading.value = true;
        error.value = null;
        const response = await fetch(`/api/streamers/${streamerId.value}/streams/${streamId.value}/chapters`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Stream not found');
            }
            throw new Error(`Failed to load video data: ${response.statusText}`);
        }
        chapterData.value = await response.json();
    }
    catch (err) {
        console.error('Error loading chapter data:', err);
        error.value = err instanceof Error ? err.message : 'Failed to load video data';
    }
    finally {
        isLoading.value = false;
    }
};
const retryLoad = () => {
    loadChapterData();
};
const goBack = () => {
    router.back();
};
onMounted(() => {
    loadChapterData();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-info']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['player-header']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-info']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-container']} */ ;
/** @type {__VLS_StyleScopedClasses['no-video-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-player-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "player-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.goBack) },
    ...{ class: "back-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stream-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
(__VLS_ctx.streamTitle);
if (__VLS_ctx.streamerName) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.streamerName);
}
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.retryLoad) },
        ...{ class: "btn btn-primary" },
    });
}
else if (!__VLS_ctx.chapterData?.video_url) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-video-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.retryLoad) },
        ...{ class: "btn btn-secondary" },
    });
}
else {
    /** @type {[typeof VideoPlayer, ]} */ ;
    // @ts-ignore
    const __VLS_0 = __VLS_asFunctionalComponent(VideoPlayer, new VideoPlayer({
        videoSrc: (__VLS_ctx.chapterData.video_url),
        chapters: (__VLS_ctx.chapterData.chapters),
        streamTitle: (__VLS_ctx.chapterData.stream_title),
        ...{ class: "video-player-container" },
    }));
    const __VLS_1 = __VLS_0({
        videoSrc: (__VLS_ctx.chapterData.video_url),
        chapters: (__VLS_ctx.chapterData.chapters),
        streamTitle: (__VLS_ctx.chapterData.stream_title),
        ...{ class: "video-player-container" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_0));
}
/** @type {__VLS_StyleScopedClasses['video-player-view']} */ ;
/** @type {__VLS_StyleScopedClasses['player-header']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-info']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['error-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['no-video-container']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['video-player-container']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            VideoPlayer: VideoPlayer,
            streamTitle: streamTitle,
            streamerName: streamerName,
            chapterData: chapterData,
            isLoading: isLoading,
            error: error,
            retryLoad: retryLoad,
            goBack: goBack,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
