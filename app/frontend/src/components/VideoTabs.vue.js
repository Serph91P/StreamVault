import { ref, computed, watch } from 'vue';
import VideoPlayer from './VideoPlayer.vue';
const props = defineProps();
const activeTab = ref('player');
const currentVideo = ref(props.initialVideo || null);
const sortBy = ref('date');
const sortOrder = ref('desc');
const tabs = computed(() => [
    {
        id: 'player',
        title: 'Player',
        icon: '▶️',
        count: null
    },
    {
        id: 'list',
        title: 'Videos',
        icon: '📋',
        count: props.videos.length
    },
    {
        id: 'stats',
        title: 'Statistics',
        icon: '📊',
        count: null
    }
]);
const sortedVideos = computed(() => {
    const sorted = [...props.videos].sort((a, b) => {
        let aVal, bVal;
        switch (sortBy.value) {
            case 'title':
                aVal = a.title.toLowerCase();
                bVal = b.title.toLowerCase();
                break;
            case 'duration':
                aVal = a.duration;
                bVal = b.duration;
                break;
            case 'game':
                aVal = (a.game || '').toLowerCase();
                bVal = (b.game || '').toLowerCase();
                break;
            case 'date':
            default:
                aVal = a.date.getTime();
                bVal = b.date.getTime();
                break;
        }
        if (sortOrder.value === 'asc') {
            return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        }
        else {
            return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
        }
    });
    return sorted;
});
const totalDuration = computed(() => {
    return props.videos.reduce((total, video) => total + (video.duration || 0), 0);
});
const totalSize = computed(() => {
    return props.videos.reduce((total, video) => total + (video.fileSize || 0), 0);
});
const uniqueGames = computed(() => {
    const games = new Set(props.videos.map(v => v.game).filter(Boolean));
    return Array.from(games);
});
const gameStats = computed(() => {
    const stats = new Map();
    props.videos.forEach(video => {
        const game = video.game || 'Unbekannt';
        const current = stats.get(game) || { count: 0, duration: 0 };
        current.count++;
        current.duration += video.duration || 0;
        stats.set(game, current);
    });
    return Array.from(stats.entries()).map(([name, data]) => ({
        name,
        ...data
    })).sort((a, b) => b.count - a.count);
});
const selectVideo = (video) => {
    currentVideo.value = video;
    activeTab.value = 'player';
};
const onChapterChange = (chapter, index) => {
    console.log('Chapter changed:', chapter, index);
};
const onVideoReady = (duration) => {
    console.log('Video ready, duration:', duration);
};
const formatDate = (date) => {
    return new Intl.DateTimeFormat('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
};
const formatDuration = (seconds) => {
    if (!seconds)
        return '00:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
};
const formatFileSize = (bytes) => {
    if (!bytes)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};
// Auto-select first video if none selected
watch(() => props.videos, (newVideos) => {
    if (!currentVideo.value && newVideos.length > 0) {
        currentVideo.value = newVideos[0];
    }
}, { immediate: true });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['tab-header']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-header']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-header']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-count']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['video-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['games-breakdown']} */ ;
/** @type {__VLS_StyleScopedClasses['game-item']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-headers']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-header']} */ ;
/** @type {__VLS_StyleScopedClasses['video-info']} */ ;
/** @type {__VLS_StyleScopedClasses['video-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "video-tabs-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tab-headers" },
});
for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.activeTab = tab.id;
            } },
        key: (tab.id),
        ...{ class: (['tab-header', { active: __VLS_ctx.activeTab === tab.id }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tab-icon" },
    });
    (tab.icon);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tab-title" },
    });
    (tab.title);
    if (tab.count) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "tab-count" },
        });
        (tab.count);
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tab-content" },
});
if (__VLS_ctx.activeTab === 'player') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "video-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.currentVideo?.title || 'Stream Recording');
    if (__VLS_ctx.currentVideo) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "info-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "icon" },
        });
        (__VLS_ctx.formatDate(__VLS_ctx.currentVideo.date));
        if (__VLS_ctx.currentVideo.duration) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "icon" },
            });
            (__VLS_ctx.formatDuration(__VLS_ctx.currentVideo.duration));
        }
        if (__VLS_ctx.currentVideo.game) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "icon" },
            });
            (__VLS_ctx.currentVideo.game);
        }
    }
    if (__VLS_ctx.currentVideo) {
        /** @type {[typeof VideoPlayer, ]} */ ;
        // @ts-ignore
        const __VLS_0 = __VLS_asFunctionalComponent(VideoPlayer, new VideoPlayer({
            ...{ 'onChapterChange': {} },
            ...{ 'onVideoReady': {} },
            videoSrc: (__VLS_ctx.currentVideo.src),
            streamId: (__VLS_ctx.currentVideo.streamId),
            chaptersUrl: (__VLS_ctx.currentVideo.chaptersUrl),
        }));
        const __VLS_1 = __VLS_0({
            ...{ 'onChapterChange': {} },
            ...{ 'onVideoReady': {} },
            videoSrc: (__VLS_ctx.currentVideo.src),
            streamId: (__VLS_ctx.currentVideo.streamId),
            chaptersUrl: (__VLS_ctx.currentVideo.chaptersUrl),
        }, ...__VLS_functionalComponentArgsRest(__VLS_0));
        let __VLS_3;
        let __VLS_4;
        let __VLS_5;
        const __VLS_6 = {
            onChapterChange: (__VLS_ctx.onChapterChange)
        };
        const __VLS_7 = {
            onVideoReady: (__VLS_ctx.onVideoReady)
        };
        var __VLS_2;
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-video-selected" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-video-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
}
if (__VLS_ctx.activeTab === 'list') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "video-list-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "section-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "list-controls" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.sortBy),
        ...{ class: "sort-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "date",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "title",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "duration",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "game",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.activeTab === 'list'))
                    return;
                __VLS_ctx.sortOrder = __VLS_ctx.sortOrder === 'asc' ? 'desc' : 'asc';
            } },
        ...{ class: "sort-order-btn" },
    });
    (__VLS_ctx.sortOrder === 'asc' ? '↑' : '↓');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "video-grid" },
    });
    for (const [video] of __VLS_getVForSourceType((__VLS_ctx.sortedVideos))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activeTab === 'list'))
                        return;
                    __VLS_ctx.selectVideo(video);
                } },
            key: (video.id),
            ...{ class: (['video-card', { active: __VLS_ctx.currentVideo?.id === video.id }]) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-thumbnail" },
        });
        if (video.thumbnail) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (video.thumbnail),
                alt: (video.title),
            });
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "default-thumbnail" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "thumbnail-icon" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-duration" },
        });
        (__VLS_ctx.formatDuration(video.duration));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-details" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "video-title" },
        });
        (video.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "video-date" },
        });
        (__VLS_ctx.formatDate(video.date));
        if (video.game) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "video-game" },
            });
            (video.game);
        }
        if (video.fileSize) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "video-size" },
            });
            (__VLS_ctx.formatFileSize(video.fileSize));
        }
    }
    if (__VLS_ctx.videos.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-videos" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-videos-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
}
if (__VLS_ctx.activeTab === 'stats') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tab-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.videos.length);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.formatDuration(__VLS_ctx.totalDuration));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.formatFileSize(__VLS_ctx.totalSize));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (__VLS_ctx.uniqueGames.length);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "games-breakdown" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "game-list" },
    });
    for (const [game] of __VLS_getVForSourceType((__VLS_ctx.gameStats))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (game.name),
            ...{ class: "game-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "game-name" },
        });
        (game.name || 'Unbekannt');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "game-count" },
        });
        (game.count);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "game-duration" },
        });
        (__VLS_ctx.formatDuration(game.duration));
    }
}
/** @type {__VLS_StyleScopedClasses['video-tabs-container']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-headers']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-header']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-count']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-content']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['video-section']} */ ;
/** @type {__VLS_StyleScopedClasses['video-info']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['no-video-selected']} */ ;
/** @type {__VLS_StyleScopedClasses['no-video-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['video-list-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['list-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['sort-select']} */ ;
/** @type {__VLS_StyleScopedClasses['sort-order-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['video-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['default-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['thumbnail-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['video-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['video-details']} */ ;
/** @type {__VLS_StyleScopedClasses['video-title']} */ ;
/** @type {__VLS_StyleScopedClasses['video-date']} */ ;
/** @type {__VLS_StyleScopedClasses['video-game']} */ ;
/** @type {__VLS_StyleScopedClasses['video-size']} */ ;
/** @type {__VLS_StyleScopedClasses['no-videos']} */ ;
/** @type {__VLS_StyleScopedClasses['no-videos-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['games-breakdown']} */ ;
/** @type {__VLS_StyleScopedClasses['game-list']} */ ;
/** @type {__VLS_StyleScopedClasses['game-item']} */ ;
/** @type {__VLS_StyleScopedClasses['game-name']} */ ;
/** @type {__VLS_StyleScopedClasses['game-count']} */ ;
/** @type {__VLS_StyleScopedClasses['game-duration']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            VideoPlayer: VideoPlayer,
            activeTab: activeTab,
            currentVideo: currentVideo,
            sortBy: sortBy,
            sortOrder: sortOrder,
            tabs: tabs,
            sortedVideos: sortedVideos,
            totalDuration: totalDuration,
            totalSize: totalSize,
            uniqueGames: uniqueGames,
            gameStats: gameStats,
            selectVideo: selectVideo,
            onChapterChange: onChapterChange,
            onVideoReady: onVideoReady,
            formatDate: formatDate,
            formatDuration: formatDuration,
            formatFileSize: formatFileSize,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
