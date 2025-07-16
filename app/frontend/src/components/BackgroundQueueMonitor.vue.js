import { ref, computed } from 'vue';
import { useBackgroundQueue } from '@/composables/useBackgroundQueue';
const { activeTasks, recentTasks, queueStats, hasActiveTasks, totalProgress } = useBackgroundQueue();
const showPanel = ref(false);
const statusIconClass = computed(() => {
    if (queueStats.value.active_tasks > 0)
        return 'status-active';
    if (queueStats.value.failed_tasks > 0)
        return 'status-error';
    return 'status-idle';
});
const togglePanel = () => {
    showPanel.value = !showPanel.value;
};
const formatTaskType = (taskType) => {
    const types = {
        'video_conversion': 'Video Conversion',
        'metadata_generation': 'Metadata',
        'chapters_generation': 'Chapters',
        'mp4_remux': 'MP4 Remux',
        'mp4_validation': 'MP4 Validation',
        'thumbnail_generation': 'Thumbnail',
        'cleanup': 'Cleanup',
        'recording': 'Recording Stream',
        'migration': 'Database Migration',
        'image_download': 'Image Download',
        'profile_image_sync': 'Profile Image Sync',
        'category_image_sync': 'Category Image Sync',
        'image_cleanup': 'Image Cleanup'
    };
    return types[taskType] || taskType;
};
const getStatusClass = (status) => {
    const classes = {
        'pending': 'status-pending',
        'running': 'status-running',
        'completed': 'status-completed',
        'failed': 'status-failed',
        'retrying': 'status-retrying'
    };
    return classes[status] || 'status-unknown';
};
const formatTime = (timestamp) => {
    if (!timestamp)
        return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000)
        return 'just now';
    if (diff < 3600000)
        return `${Math.round(diff / 60000)}m ago`;
    if (diff < 86400000)
        return `${Math.round(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['queue-status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['active-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['active-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['task-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-fill']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-running']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-completed']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['status-failed']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['no-tasks']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-label']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-count']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['task-header']} */ ;
/** @type {__VLS_StyleScopedClasses['task-streamer']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "background-queue-monitor" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onClick: (__VLS_ctx.togglePanel) },
    ...{ class: "queue-status-indicator" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-icon" },
    ...{ class: (__VLS_ctx.statusIconClass) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
    width: "16",
    height: "16",
    viewBox: "0 0 16 16",
    fill: "currentColor",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
    d: "M8 2a6 6 0 100 12A6 6 0 008 2zM2 8a6 6 0 1112 0A6 6 0 012 8z",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
    d: "M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "queue-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "queue-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "queue-count" },
});
(__VLS_ctx.queueStats.active_tasks);
if (__VLS_ctx.hasActiveTasks) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "progress-bar" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "progress-fill" },
        ...{ style: ({ width: `${__VLS_ctx.totalProgress}%` }) },
    });
}
if (__VLS_ctx.showPanel) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "queue-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.togglePanel) },
        ...{ class: "close-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-section" },
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
    (__VLS_ctx.queueStats.total_tasks);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-value text-green" },
    });
    (__VLS_ctx.queueStats.completed_tasks);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-value text-red" },
    });
    (__VLS_ctx.queueStats.failed_tasks);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stat-value text-yellow" },
    });
    (__VLS_ctx.queueStats.pending_tasks);
    if (__VLS_ctx.hasActiveTasks) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "active-tasks-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-list" },
        });
        for (const [task] of __VLS_getVForSourceType((__VLS_ctx.activeTasks))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (task.id),
                ...{ class: "task-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "task-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-type" },
            });
            (__VLS_ctx.formatTaskType(task.task_type));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-streamer" },
            });
            (task.payload.streamer_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "task-progress" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "progress-bar" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "progress-fill" },
                ...{ style: ({ width: `${task.progress}%` }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "progress-text" },
            });
            (Math.round(task.progress));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "task-status" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "status-badge" },
                ...{ class: (__VLS_ctx.getStatusClass(task.status)) },
            });
            (task.status);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-time" },
            });
            (__VLS_ctx.formatTime(task.started_at));
        }
    }
    if (__VLS_ctx.recentTasks.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "recent-tasks-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-list" },
        });
        for (const [task] of __VLS_getVForSourceType((__VLS_ctx.recentTasks.slice(0, 10)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (task.id),
                ...{ class: "task-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "task-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-type" },
            });
            (__VLS_ctx.formatTaskType(task.task_type));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-streamer" },
            });
            (task.payload.streamer_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "task-status" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "status-badge" },
                ...{ class: (__VLS_ctx.getStatusClass(task.status)) },
            });
            (task.status);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-time" },
            });
            (__VLS_ctx.formatTime(task.completed_at || task.started_at));
            if (task.error_message) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "task-error" },
                });
                (task.error_message);
            }
        }
    }
    if (!__VLS_ctx.hasActiveTasks && __VLS_ctx.recentTasks.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-tasks" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
}
/** @type {__VLS_StyleScopedClasses['background-queue-monitor']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-info']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-label']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-count']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-fill']} */ ;
/** @type {__VLS_StyleScopedClasses['queue-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-yellow']} */ ;
/** @type {__VLS_StyleScopedClasses['active-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['task-list']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-header']} */ ;
/** @type {__VLS_StyleScopedClasses['task-type']} */ ;
/** @type {__VLS_StyleScopedClasses['task-streamer']} */ ;
/** @type {__VLS_StyleScopedClasses['task-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-fill']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-text']} */ ;
/** @type {__VLS_StyleScopedClasses['task-status']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['task-time']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-tasks-section']} */ ;
/** @type {__VLS_StyleScopedClasses['task-list']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-header']} */ ;
/** @type {__VLS_StyleScopedClasses['task-type']} */ ;
/** @type {__VLS_StyleScopedClasses['task-streamer']} */ ;
/** @type {__VLS_StyleScopedClasses['task-status']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['task-time']} */ ;
/** @type {__VLS_StyleScopedClasses['task-error']} */ ;
/** @type {__VLS_StyleScopedClasses['no-tasks']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            activeTasks: activeTasks,
            recentTasks: recentTasks,
            queueStats: queueStats,
            hasActiveTasks: hasActiveTasks,
            totalProgress: totalProgress,
            showPanel: showPanel,
            statusIconClass: statusIconClass,
            togglePanel: togglePanel,
            formatTaskType: formatTaskType,
            getStatusClass: getStatusClass,
            formatTime: formatTime,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
