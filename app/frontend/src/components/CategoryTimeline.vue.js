import { computed } from 'vue';
import { useCategoryImages } from '@/composables/useCategoryImages';
const props = defineProps();
const { getCategoryImage } = useCategoryImages();
// Filter events to only show category changes
const categoryEvents = computed(() => {
    return props.events
        .filter(event => event.category_name && (event.event_type === 'channel.update' || event.event_type === 'stream.online'))
        .sort((a, b) => new Date(a.timestamp || '').getTime() - new Date(b.timestamp || '').getTime());
});
const getCategoryIcon = (categoryName) => {
    if (!categoryName)
        return 'fas fa-video';
    const imageUrl = getCategoryImage(categoryName);
    // If it's an icon (starts with icon:), return the icon class
    if (imageUrl.startsWith('icon:')) {
        return imageUrl.replace('icon:', '');
    }
    // For actual images, return a generic gaming icon as fallback for the timeline
    return 'fas fa-gamepad';
};
const getTimelinePosition = (event, index) => {
    if (categoryEvents.value.length <= 1)
        return 50;
    // Calculate position based on chronological order
    const totalEvents = categoryEvents.value.length;
    const margin = 5; // 5% margin on each side
    const usableWidth = 100 - (margin * 2);
    return margin + (index * (usableWidth / (totalEvents - 1)));
};
const formatTime = (timestamp) => {
    if (!timestamp)
        return 'Unknown time';
    const date = new Date(timestamp);
    return date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
const getNextTimestamp = (currentIndex) => {
    if (currentIndex < categoryEvents.value.length - 1) {
        return categoryEvents.value[currentIndex + 1].timestamp;
    }
    // If this is the last category change, use stream end time or current time
    return props.streamEnded || new Date().toISOString();
};
const calculateDuration = (startTime, endTime) => {
    if (!startTime || !endTime)
        return 'Unknown';
    const start = new Date(startTime);
    const end = new Date(endTime);
    const diff = end.getTime() - start.getTime();
    if (diff < 0)
        return 'Unknown';
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    if (hours > 0) {
        return `${hours}h ${minutes}m ${seconds}s`;
    }
    else if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    }
    else {
        return `${seconds}s`;
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['timeline-header']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-header']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-note']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-item']} */ ;
/** @type {__VLS_StyleScopedClasses['marker-content']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-item']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['category-list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['category-list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['category-item']} */ ;
/** @type {__VLS_StyleScopedClasses['category-marker']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-time']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-content']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-content']} */ ;
/** @type {__VLS_StyleScopedClasses['horizontal-timeline']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['category-list']} */ ;
/** @type {__VLS_StyleScopedClasses['category-item']} */ ;
/** @type {__VLS_StyleScopedClasses['category-name']} */ ;
// CSS variable injection 
// CSS variable injection end 
if (__VLS_ctx.categoryEvents.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "category-timeline" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "timeline-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-history" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "category-count" },
    });
    (__VLS_ctx.categoryEvents.length);
    (__VLS_ctx.categoryEvents.length === 1 ? 'category' : 'categories');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "timeline-legend" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "legend-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "legend-marker" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "legend-note" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-info-circle" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "horizontal-timeline" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "timeline-track" },
    });
    for (const [event, index] of __VLS_getVForSourceType((__VLS_ctx.categoryEvents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (event.id),
            ...{ class: "timeline-item" },
            ...{ style: ({ left: __VLS_ctx.getTimelinePosition(event, index) + '%' }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "timeline-marker" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "marker-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "category-icon-wrapper" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: (__VLS_ctx.getCategoryIcon(event.category_name)) },
            ...{ class: "category-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "timeline-tooltip" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tooltip-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (event.category_name || 'Unknown Category');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tooltip-time" },
        });
        (__VLS_ctx.formatTime(event.timestamp));
        if (event.title) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tooltip-title" },
            });
            (event.title);
        }
        if (index < __VLS_ctx.categoryEvents.length - 1) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tooltip-duration" },
            });
            (__VLS_ctx.calculateDuration(event.timestamp, __VLS_ctx.getNextTimestamp(index)));
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "category-list-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "category-list" },
    });
    for (const [event, index] of __VLS_getVForSourceType((__VLS_ctx.categoryEvents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (event.id),
            ...{ class: "category-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "category-marker" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: (__VLS_ctx.getCategoryIcon(event.category_name)) },
            ...{ class: "category-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "category-details" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "category-name" },
        });
        (event.category_name || 'Unknown');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "category-time" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "far fa-clock" },
        });
        (__VLS_ctx.formatTime(event.timestamp));
        if (index < __VLS_ctx.categoryEvents.length - 1) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-duration" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-hourglass-half" },
            });
            (__VLS_ctx.calculateDuration(event.timestamp, __VLS_ctx.getNextTimestamp(index)));
        }
    }
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-category-history" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-data-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-info-circle" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "help-text" },
    });
}
/** @type {__VLS_StyleScopedClasses['category-timeline']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-header']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-history']} */ ;
/** @type {__VLS_StyleScopedClasses['category-count']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-marker']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-note']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-info-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['horizontal-timeline']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-track']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-item']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-marker']} */ ;
/** @type {__VLS_StyleScopedClasses['marker-content']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['timeline-tooltip']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-header']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-time']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['category-list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-list']} */ ;
/** @type {__VLS_StyleScopedClasses['category-list']} */ ;
/** @type {__VLS_StyleScopedClasses['category-item']} */ ;
/** @type {__VLS_StyleScopedClasses['category-marker']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-details']} */ ;
/** @type {__VLS_StyleScopedClasses['category-name']} */ ;
/** @type {__VLS_StyleScopedClasses['category-time']} */ ;
/** @type {__VLS_StyleScopedClasses['far']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-clock']} */ ;
/** @type {__VLS_StyleScopedClasses['category-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-hourglass-half']} */ ;
/** @type {__VLS_StyleScopedClasses['no-category-history']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-content']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-info-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            categoryEvents: categoryEvents,
            getCategoryIcon: getCategoryIcon,
            getTimelinePosition: getTimelinePosition,
            formatTime: formatTime,
            getNextTimestamp: getNextTimestamp,
            calculateDuration: calculateDuration,
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
