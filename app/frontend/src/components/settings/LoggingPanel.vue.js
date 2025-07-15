import { ref, onMounted } from 'vue';
const isLoading = ref(false);
const isLoadingContent = ref(false);
const isCleaningUp = ref(false);
const stats = ref({});
const logsData = ref({});
const activeTab = ref('streamlink');
const showAllLogs = ref(false);
const showLogViewer = ref(false);
const showCleanupDialog = ref(false);
const viewingLogFile = ref(null);
const logContent = ref('');
const tailLines = ref(100);
const daysToKeep = ref(30);
const logTypes = ['streamlink', 'ffmpeg', 'app'];
const getCurrentLogs = () => {
    switch (activeTab.value) {
        case 'streamlink':
            return logsData.value.streamlink_logs || [];
        case 'ffmpeg':
            return logsData.value.ffmpeg_logs || [];
        case 'app':
            return logsData.value.app_logs || [];
        default:
            return [];
    }
};
const getLogCount = (logType) => {
    switch (logType) {
        case 'streamlink':
            return logsData.value.streamlink_logs?.length || 0;
        case 'ffmpeg':
            return logsData.value.ffmpeg_logs?.length || 0;
        case 'app':
            return logsData.value.app_logs?.length || 0;
        default:
            return 0;
    }
};
const formatBytes = (bytes) => {
    if (bytes === 0)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
};
const fetchStats = async () => {
    try {
        const response = await fetch('/api/logging/stats');
        if (response.ok) {
            stats.value = await response.json();
        }
    }
    catch (error) {
        console.error('Error fetching logging stats:', error);
    }
};
const fetchLogs = async () => {
    try {
        isLoading.value = true;
        const response = await fetch('/api/logging/files');
        if (response.ok) {
            logsData.value = await response.json();
        }
    }
    catch (error) {
        console.error('Error fetching log files:', error);
    }
    finally {
        isLoading.value = false;
    }
};
const refreshLogs = async () => {
    await Promise.all([fetchStats(), fetchLogs()]);
};
const viewLogFile = async (logFile) => {
    viewingLogFile.value = logFile;
    showLogViewer.value = true;
    await refreshLogContent();
};
const refreshLogContent = async () => {
    if (!viewingLogFile.value)
        return;
    try {
        isLoadingContent.value = true;
        const response = await fetch(`/api/logging/files/${viewingLogFile.value.type}/${viewingLogFile.value.filename}/tail?lines=${tailLines.value}`);
        if (response.ok) {
            const data = await response.json();
            logContent.value = data.content;
        }
    }
    catch (error) {
        console.error('Error fetching log content:', error);
        logContent.value = 'Error loading log content';
    }
    finally {
        isLoadingContent.value = false;
    }
};
const downloadLogFile = async (logFile) => {
    try {
        const response = await fetch(`/api/logging/files/${logFile.type}/${logFile.filename}`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = logFile.filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }
    }
    catch (error) {
        console.error('Error downloading log file:', error);
        alert('Error downloading log file');
    }
};
const deleteLogFile = async (logFile) => {
    if (!confirm(`Are you sure you want to delete ${logFile.filename}?`))
        return;
    try {
        const response = await fetch(`/api/logging/files/${logFile.type}/${logFile.filename}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            await refreshLogs();
        }
        else {
            throw new Error('Failed to delete log file');
        }
    }
    catch (error) {
        console.error('Error deleting log file:', error);
        alert('Error deleting log file');
    }
};
const cleanupLogs = async () => {
    if (!confirm(`This will permanently delete all logs older than ${daysToKeep.value} days. Continue?`))
        return;
    try {
        isCleaningUp.value = true;
        const response = await fetch(`/api/logging/cleanup?days_to_keep=${daysToKeep.value}`, {
            method: 'POST'
        });
        if (response.ok) {
            showCleanupDialog.value = false;
            await refreshLogs();
            alert('Log cleanup completed successfully');
        }
        else {
            throw new Error('Failed to cleanup logs');
        }
    }
    catch (error) {
        console.error('Error cleaning up logs:', error);
        alert('Error cleaning up logs');
    }
    finally {
        isCleaningUp.value = false;
    }
};
const closeLogViewer = () => {
    showLogViewer.value = false;
    viewingLogFile.value = null;
    logContent.value = '';
};
onMounted(() => {
    refreshLogs();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['log-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['log-content']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logging-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-section content-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.stats.streamlink?.count || 0);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-size" },
});
(__VLS_ctx.formatBytes(__VLS_ctx.stats.streamlink?.total_size || 0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.stats.ffmpeg?.count || 0);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-size" },
});
(__VLS_ctx.formatBytes(__VLS_ctx.stats.ffmpeg?.total_size || 0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.stats.app?.count || 0);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-size" },
});
(__VLS_ctx.formatBytes(__VLS_ctx.stats.app?.total_size || 0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logs-section content-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refreshLogs) },
    ...{ class: "btn btn-secondary" },
    disabled: (__VLS_ctx.isLoading),
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
(__VLS_ctx.isLoading ? 'Loading...' : 'Refresh');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.showCleanupDialog = true;
        } },
    ...{ class: "btn btn-warning" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tabs" },
});
for (const [logType] of __VLS_getVForSourceType((__VLS_ctx.logTypes))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.activeTab = logType;
            } },
        key: (logType),
        ...{ class: (['tab', { active: __VLS_ctx.activeTab === logType }]) },
    });
    (logType.charAt(0).toUpperCase() + logType.slice(1));
    (__VLS_ctx.getLogCount(logType));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-files-list" },
});
if (__VLS_ctx.getCurrentLogs().length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-logs" },
    });
    (__VLS_ctx.activeTab);
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    for (const [logFile] of __VLS_getVForSourceType((__VLS_ctx.getCurrentLogs().slice(0, __VLS_ctx.showAllLogs ? undefined : 10)))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (logFile.filename),
            ...{ class: "log-file-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "file-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "filename" },
        });
        (logFile.filename);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "file-meta" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "size" },
        });
        (__VLS_ctx.formatBytes(logFile.size));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "date" },
        });
        (__VLS_ctx.formatDate(logFile.last_modified));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "file-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.getCurrentLogs().length === 0))
                        return;
                    __VLS_ctx.viewLogFile(logFile);
                } },
            ...{ class: "btn btn-sm btn-secondary" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.getCurrentLogs().length === 0))
                        return;
                    __VLS_ctx.downloadLogFile(logFile);
                } },
            ...{ class: "btn btn-sm btn-primary" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.getCurrentLogs().length === 0))
                        return;
                    __VLS_ctx.deleteLogFile(logFile);
                } },
            ...{ class: "btn btn-sm btn-danger" },
        });
    }
    if (__VLS_ctx.getCurrentLogs().length > 10 && !__VLS_ctx.showAllLogs) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "show-more" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.getCurrentLogs().length === 0))
                        return;
                    if (!(__VLS_ctx.getCurrentLogs().length > 10 && !__VLS_ctx.showAllLogs))
                        return;
                    __VLS_ctx.showAllLogs = true;
                } },
            ...{ class: "btn btn-outline" },
        });
        (__VLS_ctx.getCurrentLogs().length - 10);
    }
}
if (__VLS_ctx.showLogViewer) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeLogViewer) },
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: () => { } },
        ...{ class: "modal-content log-viewer-modal" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.viewingLogFile?.filename);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "log-controls" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        ...{ onChange: (__VLS_ctx.refreshLogContent) },
        value: (__VLS_ctx.tailLines),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "50",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "100",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "500",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "1000",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.refreshLogContent) },
        ...{ class: "btn btn-sm btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeLogViewer) },
        ...{ class: "close-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-body" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "log-content" },
    });
    if (__VLS_ctx.logContent) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
        (__VLS_ctx.logContent);
    }
    else if (__VLS_ctx.isLoadingContent) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "loading" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-content" },
        });
    }
}
if (__VLS_ctx.showCleanupDialog) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showCleanupDialog))
                    return;
                __VLS_ctx.showCleanupDialog = false;
            } },
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: () => { } },
        ...{ class: "modal-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showCleanupDialog))
                    return;
                __VLS_ctx.showCleanupDialog = false;
            } },
        ...{ class: "close-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-body" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        for: "daysToKeep",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        id: "daysToKeep",
        type: "number",
        min: "1",
        max: "365",
        ...{ class: "input-field" },
    });
    (__VLS_ctx.daysToKeep);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "help-text" },
    });
    (__VLS_ctx.daysToKeep);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-footer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showCleanupDialog))
                    return;
                __VLS_ctx.showCleanupDialog = false;
            } },
        ...{ class: "btn btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cleanupLogs) },
        ...{ class: "btn btn-danger" },
        disabled: (__VLS_ctx.isCleaningUp),
    });
    if (__VLS_ctx.isCleaningUp) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "loader" },
        });
    }
    (__VLS_ctx.isCleaningUp ? 'Cleaning...' : 'Delete Old Logs');
}
/** @type {__VLS_StyleScopedClasses['logging-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-size']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-size']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-size']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-section']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['log-files-list']} */ ;
/** @type {__VLS_StyleScopedClasses['no-logs']} */ ;
/** @type {__VLS_StyleScopedClasses['log-file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['file-info']} */ ;
/** @type {__VLS_StyleScopedClasses['filename']} */ ;
/** @type {__VLS_StyleScopedClasses['file-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['size']} */ ;
/** @type {__VLS_StyleScopedClasses['date']} */ ;
/** @type {__VLS_StyleScopedClasses['file-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['show-more']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['log-viewer-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['log-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-body']} */ ;
/** @type {__VLS_StyleScopedClasses['log-content']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
/** @type {__VLS_StyleScopedClasses['no-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-header']} */ ;
/** @type {__VLS_StyleScopedClasses['close-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-body']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['input-field']} */ ;
/** @type {__VLS_StyleScopedClasses['help-text']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isLoading: isLoading,
            isLoadingContent: isLoadingContent,
            isCleaningUp: isCleaningUp,
            stats: stats,
            activeTab: activeTab,
            showAllLogs: showAllLogs,
            showLogViewer: showLogViewer,
            showCleanupDialog: showCleanupDialog,
            viewingLogFile: viewingLogFile,
            logContent: logContent,
            tailLines: tailLines,
            daysToKeep: daysToKeep,
            logTypes: logTypes,
            getCurrentLogs: getCurrentLogs,
            getLogCount: getLogCount,
            formatBytes: formatBytes,
            formatDate: formatDate,
            refreshLogs: refreshLogs,
            viewLogFile: viewLogFile,
            refreshLogContent: refreshLogContent,
            downloadLogFile: downloadLogFile,
            deleteLogFile: deleteLogFile,
            cleanupLogs: cleanupLogs,
            closeLogViewer: closeLogViewer,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
