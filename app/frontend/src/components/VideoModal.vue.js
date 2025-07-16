import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { streamerApi } from '../services/api.js';
const props = defineProps({
    video: {
        type: Object,
        required: true
    }
});
const emit = defineEmits(['close']);
const videoPlayer = ref(null);
const loading = ref(true);
const error = ref(false);
const errorMessage = ref('');
const chapters = ref([]);
const showChapters = ref(false);
const currentChapter = ref(-1);
const videoUrl = computed(() => {
    // Use the stream ID based endpoint
    return `/api/videos/stream/${props.video.id}`;
});
const closeModal = () => {
    if (videoPlayer.value) {
        videoPlayer.value.pause();
        videoPlayer.value.removeEventListener('timeupdate', updateCurrentChapter);
    }
    emit('close');
};
const onLoadStart = () => {
    loading.value = true;
    error.value = false;
};
const onCanPlay = () => {
    loading.value = false;
    error.value = false;
    // Add event listener for time updates to track current chapter
    if (videoPlayer.value) {
        videoPlayer.value.addEventListener('timeupdate', updateCurrentChapter);
    }
};
const onError = (event) => {
    loading.value = false;
    error.value = true;
    const videoEl = event.target;
    if (videoEl.error) {
        switch (videoEl.error.code) {
            case videoEl.error.MEDIA_ERR_ABORTED:
                errorMessage.value = 'Video playback was aborted.';
                break;
            case videoEl.error.MEDIA_ERR_NETWORK:
                errorMessage.value = 'Network error while loading video.';
                break;
            case videoEl.error.MEDIA_ERR_DECODE:
                errorMessage.value = 'Video could not be decoded.';
                break;
            case videoEl.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                errorMessage.value = 'Video format is not supported.';
                break;
            default:
                errorMessage.value = 'Unknown error while loading video.';
        }
    }
    else {
        errorMessage.value = 'Video could not be found. Please check the path and try again.';
    }
    console.error('Video error:', event.target.error, 'URL:', videoUrl.value);
};
const retryVideo = () => {
    if (videoPlayer.value) {
        error.value = false;
        loading.value = true;
        videoPlayer.value.load();
    }
};
const downloadVideo = () => {
    const link = document.createElement('a');
    link.href = videoUrl.value;
    link.download = props.video.title || 'video.mp4';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
const shareVideo = async () => {
    const shareData = {
        title: props.video.title,
        text: `Check out this video from ${props.video.streamer_name}!`,
        url: window.location.href
    };
    if (navigator.share) {
        try {
            await navigator.share(shareData);
        }
        catch (err) {
            if (err.name !== 'AbortError') {
                fallbackShare();
            }
        }
    }
    else {
        fallbackShare();
    }
};
const fallbackShare = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        alert('Link copied to clipboard!');
    }).catch(() => {
        alert(`Share link: ${url}`);
    });
};
const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};
const formatDuration = (seconds) => {
    if (!seconds)
        return 'Unknown';
    // Round to whole seconds to avoid decimal display
    const totalSeconds = Math.round(seconds);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
};
const formatFileSize = (bytes) => {
    if (!bytes)
        return 'Unknown';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
};
// Chapter navigation functions
const loadChapters = async () => {
    try {
        if (!props.video.streamer_id || !props.video.id) {
            console.warn('Missing streamer_id or stream id for loading chapters', {
                streamer_id: props.video.streamer_id,
                video_id: props.video.id
            });
            return;
        }
        const response = await streamerApi.getStreamChapters(props.video.streamer_id, props.video.id);
        chapters.value = response.chapters || [];
    }
    catch (error) {
        console.error('Failed to load chapters:', error);
        chapters.value = [];
    }
};
const toggleChapters = () => {
    showChapters.value = !showChapters.value;
};
const jumpToChapter = (chapter) => {
    if (!videoPlayer.value)
        return;
    try {
        const timeInSeconds = parseTimeToSeconds(chapter.start_time);
        videoPlayer.value.currentTime = timeInSeconds;
        // Update current chapter
        const chapterIndex = chapters.value.indexOf(chapter);
        currentChapter.value = chapterIndex;
    }
    catch (error) {
        console.error('Failed to jump to chapter:', error);
    }
};
const parseTimeToSeconds = (timeString) => {
    // Handle different time formats: "HH:MM:SS.mmm", "MM:SS", ISO datetime
    if (!timeString)
        return 0;
    // If it looks like an ISO datetime, convert to seconds from start
    if (timeString.includes('T')) {
        const chapterTime = new Date(timeString);
        const streamStart = new Date(props.video.created_at || props.video.started_at);
        return Math.max(0, (chapterTime - streamStart) / 1000);
    }
    // Handle "HH:MM:SS.mmm" or "MM:SS" format
    const parts = timeString.split(':');
    if (parts.length === 2) {
        // MM:SS format
        const [minutes, seconds] = parts;
        return parseInt(minutes) * 60 + parseFloat(seconds);
    }
    else if (parts.length === 3) {
        // HH:MM:SS.mmm format
        const [hours, minutes, seconds] = parts;
        return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseFloat(seconds);
    }
    return 0;
};
const formatChapterTime = (timeString) => {
    try {
        const seconds = parseTimeToSeconds(timeString);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    catch (error) {
        return timeString;
    }
};
const updateCurrentChapter = () => {
    if (!videoPlayer.value || chapters.value.length === 0)
        return;
    const currentTime = videoPlayer.value.currentTime;
    let newCurrentChapter = -1;
    for (let i = chapters.value.length - 1; i >= 0; i--) {
        const chapterTime = parseTimeToSeconds(chapters.value[i].start_time);
        if (currentTime >= chapterTime) {
            newCurrentChapter = i;
            break;
        }
    }
    if (newCurrentChapter !== currentChapter.value) {
        currentChapter.value = newCurrentChapter;
    }
};
// Handle ESC key
const handleKeydown = (event) => {
    if (event.key === 'Escape') {
        closeModal();
    }
};
onMounted(() => {
    document.addEventListener('keydown', handleKeydown);
    document.body.style.overflow = 'hidden';
    // Load chapters for this stream
    loadChapters();
});
onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown);
    document.body.style.overflow = '';
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['video-error']} */ ;
/** @type {__VLS_StyleScopedClasses['video-error']} */ ;
/** @type {__VLS_StyleScopedClasses['video-error']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-list']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['video-modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['video-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['video-details']} */ ;
/** @type {__VLS_StyleScopedClasses['video-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-list']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['video-details']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-list']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onClick: (__VLS_ctx.closeModal) },
    ...{ class: "video-modal-overlay" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onClick: () => { } },
    ...{ class: "video-modal" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
(__VLS_ctx.video.title);
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.closeModal) },
    ...{ class: "close-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "24",
    height: "24",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "18",
    y1: "6",
    x2: "6",
    y2: "18",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "6",
    y1: "6",
    x2: "18",
    y2: "18",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.video, __VLS_intrinsicElements.video)({
    ...{ onLoadstart: (__VLS_ctx.onLoadStart) },
    ...{ onCanplay: (__VLS_ctx.onCanPlay) },
    ...{ onError: (__VLS_ctx.onError) },
    ref: "videoPlayer",
    src: (__VLS_ctx.videoUrl),
    controls: true,
    preload: "metadata",
    ...{ class: "video-player" },
});
/** @type {typeof __VLS_ctx.videoPlayer} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "video-loading" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "video-error" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "48",
        height: "48",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
        cx: "12",
        cy: "12",
        r: "10",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
        x1: "15",
        y1: "9",
        x2: "9",
        y2: "15",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
        x1: "9",
        y1: "9",
        x2: "15",
        y2: "15",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.errorMessage);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.retryVideo) },
        ...{ class: "retry-btn" },
    });
}
if (__VLS_ctx.chapters.length > 0 && !__VLS_ctx.loading && !__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chapter-navigation" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.toggleChapters) },
        ...{ class: "chapters-toggle-btn" },
        ...{ class: ({ active: __VLS_ctx.showChapters }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "16",
        height: "16",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.rect, __VLS_intrinsicElements.rect)({
        x: "3",
        y: "3",
        width: "18",
        height: "18",
        rx: "2",
        ry: "2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
        x1: "9",
        y1: "9",
        x2: "15",
        y2: "9",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
        x1: "9",
        y1: "12",
        x2: "15",
        y2: "12",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
        x1: "9",
        y1: "15",
        x2: "15",
        y2: "15",
    });
    (__VLS_ctx.chapters.length);
    if (__VLS_ctx.showChapters) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chapters-list" },
        });
        for (const [chapter, index] of __VLS_getVForSourceType((__VLS_ctx.chapters))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.chapters.length > 0 && !__VLS_ctx.loading && !__VLS_ctx.error))
                            return;
                        if (!(__VLS_ctx.showChapters))
                            return;
                        __VLS_ctx.jumpToChapter(chapter);
                    } },
                key: (index),
                ...{ class: "chapter-item" },
                ...{ class: ({ active: __VLS_ctx.currentChapter === index }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "chapter-time" },
            });
            (__VLS_ctx.formatChapterTime(chapter.start_time));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "chapter-title" },
            });
            (chapter.title || `Chapter ${index + 1}`);
        }
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-details" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
(__VLS_ctx.video.streamer_name);
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "video-date" },
});
(__VLS_ctx.formatDate(__VLS_ctx.video.created_at));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-stats" },
});
if (__VLS_ctx.video.duration) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "16",
        height: "16",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
        cx: "12",
        cy: "12",
        r: "10",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline, __VLS_intrinsicElements.polyline)({
        points: "12,6 12,12 16,14",
    });
    (__VLS_ctx.formatDuration(__VLS_ctx.video.duration));
}
if (__VLS_ctx.video.file_size) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "16",
        height: "16",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
        d: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline, __VLS_intrinsicElements.polyline)({
        points: "14,2 14,8 20,8",
    });
    (__VLS_ctx.formatFileSize(__VLS_ctx.video.file_size));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.downloadVideo) },
    ...{ class: "action-btn download-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.polyline, __VLS_intrinsicElements.polyline)({
    points: "7 10 12 15 17 10",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "12",
    y1: "15",
    x2: "12",
    y2: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.shareVideo) },
    ...{ class: "action-btn share-btn" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    'stroke-width': "2",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "18",
    cy: "5",
    r: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "6",
    cy: "12",
    r: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.circle, __VLS_intrinsicElements.circle)({
    cx: "18",
    cy: "19",
    r: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "8.59",
    y1: "13.51",
    x2: "15.42",
    y2: "17.49",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.line, __VLS_intrinsicElements.line)({
    x1: "15.41",
    y1: "6.51",
    x2: "8.59",
    y2: "10.49",
});
/** @type {__VLS_StyleScopedClasses['video-modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['video-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['video-container']} */ ;
/** @type {__VLS_StyleScopedClasses['video-player']} */ ;
/** @type {__VLS_StyleScopedClasses['video-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['video-error']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapters-list']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['video-details']} */ ;
/** @type {__VLS_StyleScopedClasses['video-info']} */ ;
/** @type {__VLS_StyleScopedClasses['video-date']} */ ;
/** @type {__VLS_StyleScopedClasses['video-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['stat']} */ ;
/** @type {__VLS_StyleScopedClasses['stat']} */ ;
/** @type {__VLS_StyleScopedClasses['video-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['download-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['share-btn']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            $props: __VLS_makeOptional(props),
            ...props,
            $emit: emit,
            videoPlayer: videoPlayer,
            loading: loading,
            error: error,
            errorMessage: errorMessage,
            chapters: chapters,
            showChapters: showChapters,
            currentChapter: currentChapter,
            videoUrl: videoUrl,
            closeModal: closeModal,
            onLoadStart: onLoadStart,
            onCanPlay: onCanPlay,
            onError: onError,
            retryVideo: retryVideo,
            downloadVideo: downloadVideo,
            shareVideo: shareVideo,
            formatDate: formatDate,
            formatDuration: formatDuration,
            formatFileSize: formatFileSize,
            toggleChapters: toggleChapters,
            jumpToChapter: jumpToChapter,
            formatChapterTime: formatChapterTime,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {
            $props: __VLS_makeOptional(props),
            ...props,
            $emit: emit,
        };
    },
});
; /* PartiallyEnd: #4569/main.vue */
