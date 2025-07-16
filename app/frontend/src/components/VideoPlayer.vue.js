import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useCategoryImages } from '@/composables/useCategoryImages';
const props = withDefaults(defineProps(), {
    autoChapters: true
});
const emit = defineEmits();
const videoElement = ref();
const videoWrapper = ref();
const isLoading = ref(true);
const error = ref('');
const currentTime = ref(0);
const videoDuration = ref(0);
const showChapterUI = ref(false);
const chapters = ref([]);
// Category images composable
const { getCategoryImage } = useCategoryImages();
// Current chapter detection
const currentChapterIndex = computed(() => {
    for (let i = chapters.value.length - 1; i >= 0; i--) {
        if (currentTime.value >= chapters.value[i].startTime) {
            return i;
        }
    }
    return 0;
});
const currentChapter = computed(() => {
    return chapters.value[currentChapterIndex.value] || null;
});
// Event handlers
const onVideoLoaded = () => {
    if (videoElement.value) {
        videoDuration.value = videoElement.value.duration;
        emit('video-ready', videoDuration.value);
    }
};
const onTimeUpdate = () => {
    if (videoElement.value) {
        currentTime.value = videoElement.value.currentTime;
        emit('time-update', currentTime.value);
    }
};
const onLoadStart = () => {
    isLoading.value = true;
    error.value = '';
};
const onCanPlay = () => {
    isLoading.value = false;
};
const onVideoError = () => {
    isLoading.value = false;
    error.value = 'Failed to load video. Please check the video file and try again.';
};
const retryLoad = () => {
    if (videoElement.value) {
        videoElement.value.load();
    }
};
// Chapter navigation
const seekToChapter = (startTime) => {
    if (videoElement.value) {
        videoElement.value.currentTime = startTime;
    }
};
const previousChapter = () => {
    if (currentChapterIndex.value > 0) {
        seekToChapter(chapters.value[currentChapterIndex.value - 1].startTime);
    }
};
const nextChapter = () => {
    if (currentChapterIndex.value < chapters.value.length - 1) {
        seekToChapter(chapters.value[currentChapterIndex.value + 1].startTime);
    }
};
const toggleChapterUI = () => {
    showChapterUI.value = !showChapterUI.value;
};
// Chapter loading
const loadChapters = async () => {
    // First, check if we have pre-loaded chapters from props
    if (props.chapters && props.chapters.length > 0) {
        chapters.value = convertApiChaptersToInternal(props.chapters);
        return;
    }
    if (props.streamId && props.autoChapters) {
        try {
            // Fetch chapters from StreamVault API
            const response = await fetch(`/api/streams/${props.streamId}/chapters`);
            if (response.ok) {
                const chaptersData = await response.json();
                chapters.value = chaptersData.map((ch) => ({
                    title: ch.category_name || ch.title || 'Stream Segment',
                    startTime: ch.start_time || 0,
                    duration: ch.duration || 60,
                    gameIcon: getCategoryImage(ch.category_name)
                }));
            }
        }
        catch (e) {
            console.warn('Failed to load auto-generated chapters:', e);
        }
    }
    // If we have a chapters URL, try to parse WebVTT chapters
    if (props.chaptersUrl) {
        try {
            const response = await fetch(props.chaptersUrl);
            if (response.ok) {
                const vttText = await response.text();
                parseWebVTTChapters(vttText);
            }
        }
        catch (e) {
            console.warn('Failed to load WebVTT chapters:', e);
        }
    }
};
// Convert API chapters to internal format
const convertApiChaptersToInternal = (apiChapters) => {
    return apiChapters.map((chapter, index) => ({
        title: chapter.title || `Chapter ${index + 1}`,
        startTime: parseTimeStringToSeconds(chapter.start_time),
        duration: 60, // Default duration, can be calculated between chapters
        gameIcon: undefined
    }));
};
// Parse time string to seconds
const parseTimeStringToSeconds = (timeString) => {
    if (!timeString)
        return 0;
    // Handle ISO datetime format
    if (timeString.includes('T')) {
        // For now, just return 0 as we'd need the stream start time to calculate offset
        return 0;
    }
    // Handle HH:MM:SS.mmm or MM:SS format
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
const parseWebVTTChapters = (vttText) => {
    const lines = vttText.split('\n');
    const parsedChapters = [];
    let i = 0;
    while (i < lines.length) {
        const line = lines[i].trim();
        // Look for timestamp line (e.g., "00:00:00.000 --> 00:05:30.000")
        const timeMatch = line.match(/(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})/);
        if (timeMatch) {
            const startTime = parseVTTTime(timeMatch[1]);
            const endTime = parseVTTTime(timeMatch[2]);
            const duration = endTime - startTime;
            // Next line should be the title
            i++;
            const title = lines[i]?.trim() || 'Chapter';
            parsedChapters.push({
                title,
                startTime,
                duration
            });
        }
        i++;
    }
    if (parsedChapters.length > 0) {
        chapters.value = parsedChapters;
    }
};
const parseVTTTime = (timeStr) => {
    const [hours, minutes, seconds] = timeStr.split(':');
    return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseFloat(seconds);
};
// Utility functions
const formatTime = (seconds) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
};
const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 60) {
        const hrs = Math.floor(mins / 60);
        const remainingMins = mins % 60;
        return `${hrs}h ${remainingMins}m`;
    }
    return `${mins}m ${secs}s`;
};
const getChapterColor = (title) => {
    // Generate consistent colors for different game categories
    let hash = 0;
    for (let i = 0; i < title.length; i++) {
        hash = title.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue}, 70%, 60%)`;
};
// Watch for chapter changes and emit events
watch(currentChapterIndex, (newIndex, oldIndex) => {
    if (newIndex !== oldIndex && chapters.value[newIndex]) {
        emit('chapter-change', chapters.value[newIndex], newIndex);
    }
});
// Keyboard shortcuts
const onKeyDown = (event) => {
    if (!videoElement.value)
        return;
    switch (event.key) {
        case 'ArrowLeft':
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                previousChapter();
            }
            break;
        case 'ArrowRight':
            if (event.ctrlKey || event.metaKey) {
                event.preventDefault();
                nextChapter();
            }
            break;
        case 'c':
        case 'C':
            if (!event.ctrlKey && !event.metaKey) {
                event.preventDefault();
                toggleChapterUI();
            }
            break;
    }
};
onMounted(() => {
    loadChapters();
    document.addEventListener('keydown', onKeyDown);
});
onUnmounted(() => {
    document.removeEventListener('keydown', onKeyDown);
});
// Watch for changes in chapters prop
watch(() => props.chapters, (newChapters) => {
    if (newChapters && newChapters.length > 0) {
        chapters.value = convertApiChaptersToInternal(newChapters);
    }
}, { immediate: true });
const decodedVideoSrc = computed(() => {
    if (!props.videoSrc)
        return '';
    try {
        // URL decode the video source to handle special characters
        const decoded = decodeURIComponent(props.videoSrc);
        return decoded;
    }
    catch (error) {
        console.error('Error decoding video src:', error);
        return props.videoSrc;
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    autoChapters: true
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-game-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-game-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-segment']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['video-controls-extension']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['current-chapter-info']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-overlay']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-player-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-wrapper" },
    ref: "videoWrapper",
});
/** @type {typeof __VLS_ctx.videoWrapper} */ ;
__VLS_asFunctionalElement(__VLS_intrinsicElements.video, __VLS_intrinsicElements.video)({
    ...{ onLoadedmetadata: (__VLS_ctx.onVideoLoaded) },
    ...{ onTimeupdate: (__VLS_ctx.onTimeUpdate) },
    ...{ onLoadstart: (__VLS_ctx.onLoadStart) },
    ...{ onCanplay: (__VLS_ctx.onCanPlay) },
    ...{ onError: (__VLS_ctx.onVideoError) },
    ...{ onAbort: (__VLS_ctx.onVideoError) },
    ref: "videoElement",
    src: (__VLS_ctx.decodedVideoSrc),
    controls: true,
    preload: "metadata",
    ...{ class: "video-element" },
});
/** @type {typeof __VLS_ctx.videoElement} */ ;
if (__VLS_ctx.chaptersUrl) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.track)({
        kind: "chapters",
        src: (__VLS_ctx.chaptersUrl),
        srclang: "en",
        label: "Chapters",
        default: true,
    });
}
if (__VLS_ctx.chapters.length > 0 && __VLS_ctx.showChapterUI) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chapter-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chapter-navigation" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chapter-list" },
    });
    for (const [chapter, index] of __VLS_getVForSourceType((__VLS_ctx.chapters))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.chapters.length > 0 && __VLS_ctx.showChapterUI))
                        return;
                    __VLS_ctx.seekToChapter(chapter.startTime);
                } },
            key: (index),
            ...{ class: "chapter-item" },
            ...{ class: ({ 'active': __VLS_ctx.currentChapterIndex === index }) },
        });
        if (chapter.thumbnail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "chapter-thumbnail" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (chapter.thumbnail),
                alt: (chapter.title),
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chapter-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chapter-title" },
        });
        (chapter.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chapter-time" },
        });
        (__VLS_ctx.formatTime(chapter.startTime));
        if (chapter.duration) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "chapter-duration" },
            });
            (__VLS_ctx.formatDuration(chapter.duration));
        }
        if (chapter.gameIcon) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "chapter-game-icon" },
            });
            if (!chapter.gameIcon.startsWith('icon:')) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                    src: (chapter.gameIcon),
                    alt: (chapter.title),
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: (chapter.gameIcon.replace('icon:', '')) },
                    ...{ class: "category-icon" },
                });
            }
        }
    }
}
if (__VLS_ctx.chapters.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chapter-progress-bar" },
    });
    for (const [chapter, index] of __VLS_getVForSourceType((__VLS_ctx.chapters))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.chapters.length > 0))
                        return;
                    __VLS_ctx.seekToChapter(chapter.startTime);
                } },
            key: (index),
            ...{ class: "chapter-segment" },
            ...{ style: ({
                    width: `${(chapter.duration / __VLS_ctx.videoDuration) * 100}%`,
                    backgroundColor: __VLS_ctx.getChapterColor(chapter.title)
                }) },
            title: (`${chapter.title} - ${__VLS_ctx.formatTime(chapter.startTime)}`),
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-controls-extension" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chapter-controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleChapterUI) },
    ...{ class: "chapter-toggle-btn" },
    ...{ class: ({ 'active': __VLS_ctx.showChapterUI }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "currentColor",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
    d: "M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z",
});
(__VLS_ctx.chapters.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.previousChapter) },
    disabled: (__VLS_ctx.currentChapterIndex <= 0),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "currentColor",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
    d: "M6 6h2v12H6zm3.5 6l8.5 6V6z",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.nextChapter) },
    disabled: (__VLS_ctx.currentChapterIndex >= __VLS_ctx.chapters.length - 1),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "20",
    height: "20",
    viewBox: "0 0 24 24",
    fill: "currentColor",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
    d: "M6 18l8.5-6L6 6v12zm8.5-6l8.5 6V6z",
});
if (__VLS_ctx.currentChapter) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "current-chapter-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "current-chapter-title" },
    });
    (__VLS_ctx.currentChapter.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "current-chapter-progress" },
    });
    (__VLS_ctx.formatTime(__VLS_ctx.currentTime - __VLS_ctx.currentChapter.startTime));
    (__VLS_ctx.formatDuration(__VLS_ctx.currentChapter.duration));
}
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
}
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.retryLoad) },
        ...{ class: "retry-btn" },
    });
}
/** @type {__VLS_StyleScopedClasses['video-player-container']} */ ;
/** @type {__VLS_StyleScopedClasses['video-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['video-element']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-list']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-info']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-game-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-segment']} */ ;
/** @type {__VLS_StyleScopedClasses['video-controls-extension']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['chapter-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['current-chapter-info']} */ ;
/** @type {__VLS_StyleScopedClasses['current-chapter-title']} */ ;
/** @type {__VLS_StyleScopedClasses['current-chapter-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['error-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            videoElement: videoElement,
            videoWrapper: videoWrapper,
            isLoading: isLoading,
            error: error,
            currentTime: currentTime,
            videoDuration: videoDuration,
            showChapterUI: showChapterUI,
            chapters: chapters,
            currentChapterIndex: currentChapterIndex,
            currentChapter: currentChapter,
            onVideoLoaded: onVideoLoaded,
            onTimeUpdate: onTimeUpdate,
            onLoadStart: onLoadStart,
            onCanPlay: onCanPlay,
            onVideoError: onVideoError,
            retryLoad: retryLoad,
            seekToChapter: seekToChapter,
            previousChapter: previousChapter,
            nextChapter: nextChapter,
            toggleChapterUI: toggleChapterUI,
            formatTime: formatTime,
            formatDuration: formatDuration,
            getChapterColor: getChapterColor,
            decodedVideoSrc: decodedVideoSrc,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
