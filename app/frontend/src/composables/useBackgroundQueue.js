import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useWebSocket } from './useWebSocket';
export function useBackgroundQueue() {
    const activeTasks = ref([]);
    const recentTasks = ref([]);
    const queueStats = ref({
        total_tasks: 0,
        completed_tasks: 0,
        failed_tasks: 0,
        retried_tasks: 0,
        pending_tasks: 0,
        active_tasks: 0,
        workers: 0,
        is_running: false
    });
    const { messages } = useWebSocket();
    // Computed properties
    const hasActiveTasks = computed(() => activeTasks.value.length > 0);
    const totalProgress = computed(() => {
        if (activeTasks.value.length === 0)
            return 0;
        const totalProgress = activeTasks.value.reduce((sum, task) => sum + task.progress, 0);
        return totalProgress / activeTasks.value.length;
    });
    // API calls
    const fetchQueueStats = async () => {
        try {
            const response = await fetch('/api/background-queue/stats');
            if (response.ok) {
                const result = await response.json();
                queueStats.value = result.stats;
            }
        }
        catch (error) {
            console.error('Failed to fetch queue stats:', error);
        }
    };
    const fetchActiveTasks = async () => {
        try {
            const response = await fetch('/api/background-queue/active-tasks');
            if (response.ok) {
                const result = await response.json();
                activeTasks.value = result.active_tasks;
            }
        }
        catch (error) {
            console.error('Failed to fetch active tasks:', error);
        }
    };
    const fetchRecentTasks = async () => {
        try {
            const response = await fetch('/api/background-queue/recent-tasks');
            if (response.ok) {
                const result = await response.json();
                recentTasks.value = result.recent_tasks;
            }
        }
        catch (error) {
            console.error('Failed to fetch recent tasks:', error);
        }
    };
    const fetchTaskStatus = async (taskId) => {
        try {
            const response = await fetch(`/api/background-queue/tasks/${taskId}`);
            if (response.ok) {
                const result = await response.json();
                return result.task;
            }
        }
        catch (error) {
            console.error('Failed to fetch task status:', error);
        }
        return null;
    };
    const cancelStreamTasks = async (streamId) => {
        try {
            const response = await fetch(`/api/background-queue/cancel-stream/${streamId}`, {
                method: 'POST'
            });
            if (response.ok) {
                const result = await response.json();
                console.log(`Cancelled ${result.cancelled_count} tasks for stream ${streamId}`);
                // Refresh data
                await fetchActiveTasks();
                await fetchQueueStats();
            }
        }
        catch (error) {
            console.error('Failed to cancel stream tasks:', error);
        }
    };
    // WebSocket message handling
    const processWebSocketMessage = (message) => {
        if (message.type === 'queue_stats_update') {
            queueStats.value = message.data;
        }
        else if (message.type === 'task_status_update') {
            const taskUpdate = message.data;
            // Update active tasks
            const activeIndex = activeTasks.value.findIndex(t => t.id === taskUpdate.id);
            if (activeIndex !== -1) {
                if (taskUpdate.status === 'completed' || taskUpdate.status === 'failed') {
                    // Move to recent tasks
                    recentTasks.value.unshift(activeTasks.value[activeIndex]);
                    activeTasks.value.splice(activeIndex, 1);
                    // Keep only last 50 recent tasks
                    if (recentTasks.value.length > 50) {
                        recentTasks.value = recentTasks.value.slice(0, 50);
                    }
                }
                else {
                    // Update existing task
                    activeTasks.value[activeIndex] = { ...activeTasks.value[activeIndex], ...taskUpdate };
                }
            }
            else if (taskUpdate.status === 'running' || taskUpdate.status === 'pending') {
                // Add new active task
                activeTasks.value.push(taskUpdate);
            }
        }
        else if (message.type === 'task_progress_update') {
            const progressUpdate = message.data;
            const activeIndex = activeTasks.value.findIndex(t => t.id === progressUpdate.task_id);
            if (activeIndex !== -1) {
                activeTasks.value[activeIndex].progress = progressUpdate.progress;
                if (progressUpdate.message) {
                    activeTasks.value[activeIndex].message = progressUpdate.message;
                }
            }
        }
        else if (message.type === 'recording_job_update') {
            const recordingUpdate = message.data;
            // Handle recording job updates (streamlink/ffmpeg)
            const activeIndex = activeTasks.value.findIndex(t => 
                t.task_type === 'recording' && 
                t.payload.streamer_name === recordingUpdate.streamer_name
            );
            
            if (activeIndex !== -1) {
                // Update existing recording job
                activeTasks.value[activeIndex] = { 
                    ...activeTasks.value[activeIndex], 
                    ...recordingUpdate,
                    task_type: 'recording',
                    status: recordingUpdate.status || 'running'
                };
            } else if (recordingUpdate.status === 'started' || recordingUpdate.status === 'running') {
                // Add new recording job
                activeTasks.value.push({
                    id: `recording_${recordingUpdate.streamer_name}_${Date.now()}`,
                    task_type: 'recording',
                    status: recordingUpdate.status || 'running',
                    payload: recordingUpdate,
                    progress: recordingUpdate.progress || 0,
                    started_at: recordingUpdate.started_at || new Date().toISOString()
                });
            }
        }
    };
    // Watch for WebSocket messages
    let websocketWatcher = null;
    const startWatching = () => {
        if (websocketWatcher)
            return;
        // Watch for new messages in the WebSocket messages array
        websocketWatcher = watch(messages, (newMessages) => {
            if (newMessages.length > 0) {
                // Process the latest message
                const latestMessage = newMessages[newMessages.length - 1];
                processWebSocketMessage(latestMessage);
            }
        }, { deep: true });
    };
    const stopWatching = () => {
        if (websocketWatcher) {
            websocketWatcher();
            websocketWatcher = null;
        }
    };
    // Polling for updates (fallback if WebSocket fails)
    let pollInterval = null;
    const startPolling = () => {
        if (pollInterval)
            return;
        pollInterval = setInterval(async () => {
            await Promise.all([
                fetchQueueStats(),
                fetchActiveTasks()
            ]);
        }, 5000); // Poll every 5 seconds
    };
    const stopPolling = () => {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    };
    // Lifecycle
    onMounted(async () => {
        // Initial data load
        await Promise.all([
            fetchQueueStats(),
            fetchActiveTasks(),
            fetchRecentTasks()
        ]);
        // Start watching for updates
        startWatching();
        startPolling();
    });
    onUnmounted(() => {
        stopWatching();
        stopPolling();
    });
    return {
        activeTasks,
        recentTasks,
        queueStats,
        hasActiveTasks,
        totalProgress,
        fetchQueueStats,
        fetchActiveTasks,
        fetchRecentTasks,
        fetchTaskStatus,
        cancelStreamTasks,
        processWebSocketMessage
    };
}
