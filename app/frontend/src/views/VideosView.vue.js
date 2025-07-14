import { ref, computed, onMounted } from 'vue';
import VideoModal from '@/components/VideoModal.vue';
import { api } from '@/services/api';
const loading = ref(true);
const searchQuery = ref('');
const activeFilter = ref('all');
const activeCategoryFilter = ref('all');
const selectedVideo = ref(null);
const videos = ref([]);
const error = ref(null);
const filters = [
    { label: 'All', value: 'all' },
    { label: 'Today', value: 'today' },
    { label: 'This Week', value: 'week' },
    { label: 'This Month', value: 'month' }
];
// Get unique categories from videos
const availableCategories = computed(() => {
    const categories = videos.value
        .map(video => video.category_name)
        .filter(category => category && category.trim() !== '')
        .filter((category, index, array) => array.indexOf(category) === index)
        .sort();
    return [
        { label: 'All Categories', value: 'all' },
        ...categories.map(category => ({ label: category, value: category }))
    ];
});
const filteredVideos = computed(() => {
    let filtered = videos.value;
    // Filter by search query
    if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        filtered = filtered.filter(video => (video.title || '').toLowerCase().includes(query) ||
            (video.streamer_name || '').toLowerCase().includes(query));
    }
    // Filter by category
    if (activeCategoryFilter.value !== 'all') {
        filtered = filtered.filter(video => video.category_name === activeCategoryFilter.value);
    }
    // Filter by date
    if (activeFilter.value !== 'all') {
        const now = new Date();
        const filterDate = new Date();
        switch (activeFilter.value) {
            case 'today':
                filterDate.setHours(0, 0, 0, 0);
                break;
            case 'week':
                filterDate.setDate(now.getDate() - 7);
                break;
            case 'month':
                filterDate.setMonth(now.getMonth() - 1);
                break;
        }
        filtered = filtered.filter(video => {
            if (!video.created_at)
                return false;
            try {
                const videoDate = new Date(video.created_at);
                return videoDate >= filterDate;
            }
            catch (e) {
                console.warn('Invalid date format:', video.created_at);
                return false;
            }
        });
    }
    // Sort by date (newest first)
    const result = filtered.sort((a, b) => {
        try {
            const dateA = new Date(a.created_at || 0);
            const dateB = new Date(b.created_at || 0);
            return dateB - dateA;
        }
        catch (e) {
            return 0;
        }
    });
    return result;
});
const loadVideos = async () => {
    try {
        loading.value = true;
        error.value = null;
        const response = await api.get('/api/videos');
        // API returns array directly, not wrapped in data
        videos.value = Array.isArray(response) ? response : (response.data || []);
    }
    catch (err) {
        console.error('Error loading videos:', err);
        error.value = err.response?.data?.detail || 'Failed to load videos';
        videos.value = [];
    }
    finally {
        loading.value = false;
    }
};
const searchVideos = () => {
    // Trigger reactivity by updating computed
    // The computed property will automatically filter
};
const openVideoModal = (video) => {
    selectedVideo.value = video;
};
const closeVideoModal = () => {
    selectedVideo.value = null;
};
const handleThumbnailError = (event) => {
    event.target.style.display = 'none';
};
const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = (now - date) / (1000 * 60 * 60);
    if (diffInHours < 24) {
        return `${Math.floor(diffInHours)} hours ago`;
    }
    else if (diffInHours < 24 * 7) {
        return `${Math.floor(diffInHours / 24)} days ago`;
    }
    else {
        return date.toLocaleDateString('en-US', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }
};
const formatDuration = (seconds) => {
    if (!seconds)
        return '';
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
        return '';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
};
onMounted(() => {
    loadVideos();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['view-header']} */ ;
/** @type {__VLS_StyleScopedClasses['view-header']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['search-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['category-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['category-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['category-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['error-state']} */ ;
/** @type {__VLS_StyleScopedClasses['error-state']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['videos-view']} */ ;
/** @type {__VLS_StyleScopedClasses['view-header']} */ ;
/** @type {__VLS_StyleScopedClasses['filters']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['videos-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['video-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['category-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['category-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "videos-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "view-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filters" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "search-box" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
    value: (__VLS_ctx.searchQuery),
    type: "text",
    placeholder: "Search videos...",
    ...{ class: "search-input" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.searchVideos) },
    ...{ class: "search-btn" },
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
    cx: "11",
    cy: "11",
    r: "8",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path, __VLS_intrinsicElements.path)({
    d: "m21 21-4.35-4.35",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-buttons" },
});
for (const [filter] of __VLS_getVForSourceType((__VLS_ctx.filters))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.activeFilter = filter.value;
            } },
        key: (filter.value),
        ...{ class: (['filter-btn', { active: __VLS_ctx.activeFilter === filter.value }]) },
    });
    (filter.label);
}
if (__VLS_ctx.availableCategories.length > 1) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "category-filter" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "category-buttons" },
    });
    for (const [category] of __VLS_getVForSourceType((__VLS_ctx.availableCategories))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.availableCategories.length > 1))
                        return;
                    __VLS_ctx.activeCategoryFilter = category.value;
                } },
            key: (category.value),
            ...{ class: (['category-btn', { active: __VLS_ctx.activeCategoryFilter === category.value }]) },
        });
        (category.label);
    }
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "64",
        height: "64",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "1.5",
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
    (__VLS_ctx.error);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.loadVideos) },
        ...{ class: "retry-btn" },
    });
}
else if (__VLS_ctx.filteredVideos.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "videos-grid" },
    });
    for (const [video] of __VLS_getVForSourceType((__VLS_ctx.filteredVideos))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!!(__VLS_ctx.error))
                        return;
                    if (!(__VLS_ctx.filteredVideos.length > 0))
                        return;
                    __VLS_ctx.openVideoModal(video);
                } },
            key: (video.id),
            ...{ class: "video-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-thumbnail" },
        });
        if (video.thumbnail_url) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img, __VLS_intrinsicElements.img)({
                ...{ onError: (__VLS_ctx.handleThumbnailError) },
                src: (video.thumbnail_url),
                alt: (video.title),
                ...{ class: "thumbnail-image" },
            });
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "thumbnail-placeholder" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
                width: "48",
                height: "48",
                viewBox: "0 0 24 24",
                fill: "none",
                stroke: "currentColor",
                'stroke-width': "2",
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
        }
        if (video.duration) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "video-duration" },
            });
            (__VLS_ctx.formatDuration(video.duration));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-overlay" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
            ...{ class: "play-icon" },
            width: "24",
            height: "24",
            viewBox: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            'stroke-width': "2",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.polygon, __VLS_intrinsicElements.polygon)({
            points: "5 3 19 12 5 21 5 3",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
            ...{ class: "video-title" },
        });
        (video.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "video-streamer" },
        });
        (video.streamer_name);
        if (video.category_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "video-category" },
            });
            (video.category_name);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "video-meta" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "video-date" },
        });
        (__VLS_ctx.formatDate(video.created_at));
        if (video.file_size) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "video-size" },
            });
            (__VLS_ctx.formatFileSize(video.file_size));
        }
    }
}
else if (!__VLS_ctx.loading && !__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "64",
        height: "64",
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "1.5",
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
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.searchQuery) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.searchQuery);
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
}
if (__VLS_ctx.selectedVideo) {
    /** @type {[typeof VideoModal, ]} */ ;
    // @ts-ignore
    const __VLS_0 = __VLS_asFunctionalComponent(VideoModal, new VideoModal({
        ...{ 'onClose': {} },
        video: (__VLS_ctx.selectedVideo),
    }));
    const __VLS_1 = __VLS_0({
        ...{ 'onClose': {} },
        video: (__VLS_ctx.selectedVideo),
    }, ...__VLS_functionalComponentArgsRest(__VLS_0));
    let __VLS_3;
    let __VLS_4;
    let __VLS_5;
    const __VLS_6 = {
        onClose: (__VLS_ctx.closeVideoModal)
    };
    var __VLS_2;
}
/** @type {__VLS_StyleScopedClasses['videos-view']} */ ;
/** @type {__VLS_StyleScopedClasses['view-header']} */ ;
/** @type {__VLS_StyleScopedClasses['filters']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['search-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['category-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['category-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['category-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['error-state']} */ ;
/** @type {__VLS_StyleScopedClasses['retry-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['videos-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['video-card']} */ ;
/** @type {__VLS_StyleScopedClasses['video-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['thumbnail-image']} */ ;
/** @type {__VLS_StyleScopedClasses['thumbnail-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['video-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['video-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['play-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['video-info']} */ ;
/** @type {__VLS_StyleScopedClasses['video-title']} */ ;
/** @type {__VLS_StyleScopedClasses['video-streamer']} */ ;
/** @type {__VLS_StyleScopedClasses['video-category']} */ ;
/** @type {__VLS_StyleScopedClasses['video-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['video-date']} */ ;
/** @type {__VLS_StyleScopedClasses['video-size']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            VideoModal: VideoModal,
            loading: loading,
            searchQuery: searchQuery,
            activeFilter: activeFilter,
            activeCategoryFilter: activeCategoryFilter,
            selectedVideo: selectedVideo,
            error: error,
            filters: filters,
            availableCategories: availableCategories,
            filteredVideos: filteredVideos,
            loadVideos: loadVideos,
            searchVideos: searchVideos,
            openVideoModal: openVideoModal,
            closeVideoModal: closeVideoModal,
            handleThumbnailError: handleThumbnailError,
            formatDate: formatDate,
            formatDuration: formatDuration,
            formatFileSize: formatFileSize,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
