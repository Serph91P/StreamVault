import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStreams } from '@/composables/useStreams';
import { useRecordingSettings } from '@/composables/useRecordingSettings';
import { useWebSocket } from '@/composables/useWebSocket';
import { useCategoryImages } from '@/composables/useCategoryImages';
import CategoryTimeline from './CategoryTimeline.vue';
const route = useRoute();
const router = useRouter();
const streamerId = computed(() => route.params.id || route.query.id);
const streamerName = computed(() => route.query.name);
const { streams, isLoading, fetchStreams } = useStreams();
const { activeRecordings, fetchActiveRecordings, stopRecording: stopStreamRecording } = useRecordingSettings();
const { messages } = useWebSocket();
const { getCategoryImage, preloadCategoryImages } = useCategoryImages();
// State for recording actions
const isStartingRecording = ref(false);
const isStoppingRecording = ref(false);
const isStartingOfflineRecording = ref(false);
const localRecordingState = ref({});
//State for stream deletion
const showDeleteModal = ref(false);
const streamToDelete = ref(null);
const deletingStreamId = ref(null);
const deleteResults = ref(null);
const showDeleteAllModal = ref(false);
const deletingAllStreams = ref(false);
// State for expandable streams
const expandedStreams = ref({});
// Computed property um zu prüfen, ob es Live-Streams gibt
const hasLiveStreams = computed(() => {
    return streams.value.some(stream => !stream.ended_at);
});
// Category image handling
const getCategoryImageSrc = (categoryName) => {
    return getCategoryImage(categoryName);
};
// Formatierungsfunktionen
const formatDate = (date) => {
    if (!date)
        return 'Unknown';
    return new Date(date).toLocaleString();
};
const calculateDuration = (start, end) => {
    if (!start)
        return 'Unknown';
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const durationMs = endTime - startTime;
    if (durationMs < 0)
        return 'Invalid time';
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    }
    else {
        return `${minutes}m ${seconds % 60}s`;
    }
};
// Navigation zurück
const handleBack = () => {
    router.push('/');
};
// Watch video function
const watchVideo = (stream) => {
    router.push({
        name: 'VideoPlayer',
        params: {
            streamerId: streamerId.value,
            streamId: stream.id
        },
        query: {
            title: stream.title || `Stream ${stream.id}`,
            streamerName: streamerName.value
        }
    });
};
// Prüfen, ob ein Stream aktuell aufgenommen wird
const isStreamRecording = (streamerIdValue) => {
    // Ensure we're working with numbers
    const targetStreamerId = Number(streamerIdValue);
    // First check local state which gets updated immediately via WebSockets
    if (localRecordingState.value[targetStreamerId] !== undefined) {
        console.log(`Using local recording state for ${targetStreamerId}: ${localRecordingState.value[targetStreamerId]}`);
        return localRecordingState.value[targetStreamerId];
    }
    // Then check activeRecordings from the server
    if (!activeRecordings.value || !Array.isArray(activeRecordings.value)) {
        console.log(`No active recordings available for ${targetStreamerId}`);
        return false;
    }
    console.log(`Active recordings for ${targetStreamerId}:`, activeRecordings.value);
    const isRecording = activeRecordings.value.some(rec => {
        // Ensure both are treated as numbers for comparison
        const recordingStreamerId = Number(rec.streamer_id);
        return recordingStreamerId === targetStreamerId;
    });
    console.log(`Stream ${targetStreamerId} recording status: ${isRecording}`);
    return isRecording;
};
// Aufnahme starten
const startRecording = async (streamerIdValue) => {
    try {
        isStartingRecording.value = true;
        // Ensure we're working with numbers
        const targetStreamerId = Number(streamerIdValue);
        // Update local state immediately for better UX
        localRecordingState.value[targetStreamerId] = true;
        const response = await fetch(`/api/recording/force/${targetStreamerId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to start recording');
        }
        // Keep local state since it was successful
        console.log(`Successfully started recording for streamer ${targetStreamerId}`);
        // Fetch active recordings to ensure our UI is in sync
        await fetchActiveRecordings();
    }
    catch (error) {
        console.error('Failed to start recording:', error);
        alert(`Failed to start recording: ${error instanceof Error ? error.message : String(error)}`);
        // Reset local state on failure
        localRecordingState.value[Number(streamerIdValue)] = false;
    }
    finally {
        isStartingRecording.value = false;
    }
};
// Neue Methode: Force-Offline-Recording starten
const forceOfflineRecording = async (streamerIdValue) => {
    try {
        isStartingOfflineRecording.value = true;
        // Ensure we're working with numbers
        const targetStreamerId = Number(streamerIdValue);
        // Update local state immediately for better UX
        localRecordingState.value[targetStreamerId] = true;
        const response = await fetch(`/api/recording/force-offline/${targetStreamerId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to start offline recording');
        }
        // Keep local state since it was successful
        console.log(`Successfully started offline recording for streamer ${targetStreamerId}`);
        // Fetch active recordings to ensure our UI is in sync
        await fetchActiveRecordings();
        // Reload streams to show the newly created stream
        await fetchStreams(streamerId.value);
    }
    catch (error) {
        console.error('Failed to start offline recording:', error);
        alert(`Failed to start offline recording: ${error instanceof Error ? error.message : String(error)}`);
        // Reset local state on failure
        localRecordingState.value[Number(streamerIdValue)] = false;
    }
    finally {
        isStartingOfflineRecording.value = false;
    }
};
// Aufnahme stoppen
const stopRecording = async (streamerIdValue) => {
    try {
        isStoppingRecording.value = true;
        // Ensure we're working with numbers
        const targetStreamerId = Number(streamerIdValue);
        // Sofort Status lokal aktualisieren für bessere UX
        localRecordingState.value[targetStreamerId] = false;
        await stopStreamRecording(targetStreamerId);
        // Nach erfolgreicher API-Anfrage trotzdem aktualisieren
        await fetchActiveRecordings();
    }
    catch (error) {
        console.error('Failed to stop recording:', error);
        alert(`Failed to stop recording: ${error instanceof Error ? error.message : String(error)}`);
        // Setze den lokalen Status zurück, wenn die Anfrage fehlschlägt
        localRecordingState.value[Number(streamerIdValue)] = true;
    }
    finally {
        isStoppingRecording.value = false;
    }
};
// Toggle stream expansion
const toggleStreamExpansion = (streamId) => {
    expandedStreams.value[streamId] = !expandedStreams.value[streamId];
};
// Stream deletion functions
const confirmDeleteStream = (stream) => {
    streamToDelete.value = stream;
    showDeleteModal.value = true;
};
const cancelDelete = () => {
    showDeleteModal.value = false;
    streamToDelete.value = null;
};
const deleteStream = async () => {
    if (!streamToDelete.value || !streamerId.value)
        return;
    try {
        deletingStreamId.value = streamToDelete.value.id;
        const response = await fetch(`/api/streamers/${streamerId.value}/streams/${streamToDelete.value.id}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete stream');
        }
        const result = await response.json();
        deleteResults.value = result;
        console.log('Delete stream result:', result);
        // Remove stream from the UI
        streams.value = streams.value.filter(s => s.id !== streamToDelete.value.id);
        // Close the modal
        showDeleteModal.value = false;
        streamToDelete.value = null;
        // Show success success
        alert(`Stream deleted successfully. Removed ${result.deleted_files_count} associated files.`);
    }
    catch (error) {
        console.error('Failed to delete stream:', error);
        alert(`Failed to delete stream: ${error instanceof Error ? error.message : String(error)}`);
    }
    finally {
        deletingStreamId.value = null;
    }
};
// New function to confirm deletion of all streams
const confirmDeleteAllStreams = () => {
    showDeleteAllModal.value = true;
};
// Cancel deletion of all streams
const cancelDeleteAll = () => {
    showDeleteAllModal.value = false;
};
// Delete all streams for the current streamer
const deleteAllStreams = async () => {
    if (!streamerId.value)
        return;
    try {
        deletingAllStreams.value = true;
        const response = await fetch(`/api/streamers/${streamerId.value}/streams`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete all streams');
        }
        const result = await response.json();
        console.log('Delete all streams result:', result);
        // Clear the streams list in the UI
        streams.value = [];
        // Close the modal
        showDeleteAllModal.value = false;
        // Show success message
        alert(`All streams deleted successfully. Removed ${result.deleted_files_count} associated files.`);
    }
    catch (error) {
        console.error('Failed to delete all streams:', error);
        alert(`Failed to delete all streams: ${error instanceof Error ? error.message : String(error)}`);
    }
    finally {
        deletingAllStreams.value = false;
    }
};
// Daten laden
const loadStreams = async () => {
    if (streamerId.value) {
        await fetchStreams(streamerId.value);
        await fetchActiveRecordings();
        console.log("Loaded active recordings:", activeRecordings.value);
        // Preload category images for all streams
        const categories = streams.value
            .map(stream => stream.category_name)
            .filter((name) => Boolean(name))
            .filter((value, index, self) => self.indexOf(value) === index); // Remove duplicates
        if (categories.length > 0) {
            preloadCategoryImages(categories);
        }
    }
};
onMounted(async () => {
    await loadStreams();
    // Load initial active recordings
    await fetchActiveRecordings();
    console.log("Initial active recordings:", activeRecordings.value);
});
// WebSocket-Nachrichten überwachen
watch(messages, (newMessages) => {
    if (newMessages.length === 0)
        return;
    const latestMessage = newMessages[newMessages.length - 1];
    console.log('Received WebSocket message:', latestMessage);
    // Handle WebSocket messages
    if (latestMessage.type === 'active_recordings_update') {
        console.log('Updating active recordings from WebSocket:', latestMessage.data);
        activeRecordings.value = latestMessage.data || [];
    }
    else if (latestMessage.type === 'recording_started' || latestMessage.type === 'recording_stopped') {
        // Refresh active recordings when recording state changes
        console.log('Recording state changed, refreshing active recordings');
        fetchActiveRecordings();
    }
    // Update local state based on WebSocket events
    if (latestMessage.type === 'recording.started') {
        const streamerId = Number(latestMessage.data.streamer_id);
        console.log(`Recording started for streamer ${streamerId}`);
        // Update local state immediately
        localRecordingState.value[streamerId] = true;
        // Also update our local cache of activeRecordings
        if (!activeRecordings.value) {
            activeRecordings.value = [];
        }
        // Add or update the recording in our cache
        const existingIndex = activeRecordings.value.findIndex(r => Number(r.streamer_id) === streamerId);
        if (existingIndex >= 0) {
            activeRecordings.value[existingIndex] = latestMessage.data;
        }
        else {
            activeRecordings.value.push(latestMessage.data);
        }
        // Still fetch from server to ensure we're in sync
        fetchActiveRecordings();
    }
    else if (latestMessage.type === 'recording.stopped') {
        const streamerId = Number(latestMessage.data.streamer_id);
        console.log(`Recording stopped for streamer ${streamerId}`);
        // Update local state immediately
        localRecordingState.value[streamerId] = false;
        // Remove from our local cache
        if (activeRecordings.value) {
            activeRecordings.value = activeRecordings.value.filter(r => Number(r.streamer_id) !== streamerId);
        }
        // Sync with server
        fetchActiveRecordings();
    }
    else if (latestMessage.type === 'stream.online') {
        // Wenn ein neuer Stream erkannt wird, aktualisieren wir die Stream-Liste
        if (Number(latestMessage.data.streamer_id) === Number(streamerId.value)) {
            fetchStreams(streamerId.value);
        }
    }
}, { deep: true });
// Daten neu laden, wenn sich die StreamerID ändert
watch(streamerId, (newId, oldId) => {
    if (newId && newId !== oldId) {
        loadStreams();
    }
});
const handleImageError = (event, categoryName) => {
    const img = event.target;
    const container = img.parentElement;
    console.error(`Failed to load category image for: ${categoryName}`);
    // Hide the image
    img.style.display = 'none';
    // Show fallback icon by replacing the image with an icon wrapper
    if (container) {
        const iconWrapper = document.createElement('div');
        iconWrapper.className = 'category-icon-wrapper';
        const icon = document.createElement('i');
        icon.className = `fas ${getCategoryImage(categoryName).replace('icon:', '')}`;
        iconWrapper.appendChild(icon);
        container.appendChild(iconWrapper);
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['streams-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['streams-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-compact-header']} */ ;
/** @type {__VLS_StyleScopedClasses['meta-item']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['play-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['expand-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-chevron-down']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-play']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-chevron-down']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-chevron-down']} */ ;
/** @type {__VLS_StyleScopedClasses['rotated']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['test-tooltip-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['test-tooltip-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['play-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['expand-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['play-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['expand-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-stream']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-list']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-compact-header']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-container']} */ ;
/** @type {__VLS_StyleScopedClasses['category-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['meta-item']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-list']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-compact-header']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['category-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fab-text']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "streams-container" },
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else if (__VLS_ctx.streams.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-data-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "action-buttons" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.handleBack) },
        ...{ class: "btn btn-primary back-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-arrow-left" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(__VLS_ctx.isLoading))
                    return;
                if (!(__VLS_ctx.streams.length === 0))
                    return;
                __VLS_ctx.forceOfflineRecording(Number(__VLS_ctx.streamerId));
            } },
        ...{ class: "btn btn-warning" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-record-vinyl" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streams-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "streams-summary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "stream-count" },
    });
    (__VLS_ctx.streams.length);
    if (__VLS_ctx.hasLiveStreams) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "live-indicator" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.handleBack) },
        ...{ class: "btn btn-secondary back-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-arrow-left" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    if (!__VLS_ctx.hasLiveStreams) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.streams.length === 0))
                        return;
                    if (!(!__VLS_ctx.hasLiveStreams))
                        return;
                    __VLS_ctx.forceOfflineRecording(Number(__VLS_ctx.streamerId));
                } },
            ...{ class: "btn btn-warning" },
            disabled: (__VLS_ctx.isStartingOfflineRecording),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-record-vinyl" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.isStartingOfflineRecording ? 'Starting Recording...' : 'Force Recording (Offline)');
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.confirmDeleteAllStreams) },
        ...{ class: "btn btn-danger delete-all-btn" },
        disabled: (__VLS_ctx.deletingAllStreams || __VLS_ctx.streams.length === 0),
        title: (`Delete all ${__VLS_ctx.streams.length} streams`),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-trash-alt" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.deletingAllStreams ? 'Deleting All...' : `Delete All (${__VLS_ctx.streams.length})`);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stream-list" },
    });
    for (const [stream] of __VLS_getVForSourceType((__VLS_ctx.streams))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (stream.id),
            ...{ class: "stream-card" },
            ...{ class: ({ 'expanded': __VLS_ctx.expandedStreams[stream.id] }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.streams.length === 0))
                        return;
                    __VLS_ctx.toggleStreamExpansion(stream.id);
                } },
            ...{ class: "stream-compact-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-thumbnail" },
        });
        if (stream.category_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-image-container" },
            });
            if (__VLS_ctx.getCategoryImageSrc(stream.category_name).startsWith('icon:')) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "category-icon-wrapper" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: (`fas ${__VLS_ctx.getCategoryImageSrc(stream.category_name).replace('icon:', '')}`) },
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                    ...{ onError: (...[$event]) => {
                            if (!!(__VLS_ctx.isLoading))
                                return;
                            if (!!(__VLS_ctx.streams.length === 0))
                                return;
                            if (!(stream.category_name))
                                return;
                            if (!!(__VLS_ctx.getCategoryImageSrc(stream.category_name).startsWith('icon:')))
                                return;
                            __VLS_ctx.handleImageError($event, stream.category_name);
                        } },
                    src: (__VLS_ctx.getCategoryImageSrc(stream.category_name)),
                    alt: (stream.category_name),
                    loading: "lazy",
                    ...{ class: "category-image" },
                });
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-placeholder" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-video" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-badges" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "status-badge" },
            ...{ class: ({ 'live': !stream.ended_at }) },
        });
        (!stream.ended_at ? 'LIVE' : 'ENDED');
        if (!stream.ended_at) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "recording-badge" },
                ...{ class: (__VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId)) ? 'recording' : 'not-recording') },
            });
            (__VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId)) ? 'REC' : 'OFF');
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
            ...{ class: "stream-title" },
        });
        (stream.title || __VLS_ctx.formatDate(stream.started_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-meta" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "meta-item duration-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-clock" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.calculateDuration(stream.started_at, stream.ended_at));
        if (stream.category_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "meta-item category-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-gamepad" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (stream.category_name);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-actions" },
        });
        if (stream.ended_at) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.isLoading))
                            return;
                        if (!!(__VLS_ctx.streams.length === 0))
                            return;
                        if (!(stream.ended_at))
                            return;
                        __VLS_ctx.watchVideo(stream);
                    } },
                ...{ class: "action-btn play-btn" },
                'data-tooltip': "Play Video",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-play" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.streams.length === 0))
                        return;
                    __VLS_ctx.confirmDeleteStream(stream);
                } },
            ...{ class: "action-btn delete-btn" },
            disabled: (__VLS_ctx.deletingStreamId === stream.id || (!stream.ended_at && __VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId)))),
            'data-tooltip': "Delete Stream",
        });
        if (__VLS_ctx.deletingStreamId === stream.id) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-spinner fa-spin" },
            });
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-trash" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(__VLS_ctx.streams.length === 0))
                        return;
                    __VLS_ctx.toggleStreamExpansion(stream.id);
                } },
            ...{ class: "action-btn expand-btn" },
            'data-tooltip': (__VLS_ctx.expandedStreams[stream.id] ? 'Collapse Details' : 'Show Details'),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-chevron-down" },
            ...{ class: ({ 'rotated': __VLS_ctx.expandedStreams[stream.id] }) },
        });
        if (__VLS_ctx.expandedStreams[stream.id]) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stream-expanded-content" },
            });
            if (stream.events && stream.events.length > 0) {
                /** @type {[typeof CategoryTimeline, ]} */ ;
                // @ts-ignore
                const __VLS_0 = __VLS_asFunctionalComponent(CategoryTimeline, new CategoryTimeline({
                    events: (stream.events),
                    streamStarted: (stream.started_at),
                    streamEnded: (stream.ended_at),
                }));
                const __VLS_1 = __VLS_0({
                    events: (stream.events),
                    streamStarted: (stream.started_at),
                    streamEnded: (stream.ended_at),
                }, ...__VLS_functionalComponentArgsRest(__VLS_0));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stream-details" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "detail-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "value" },
            });
            (__VLS_ctx.formatDate(stream.started_at));
            if (stream.ended_at) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "detail-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "value" },
                });
                (__VLS_ctx.formatDate(stream.ended_at));
            }
            if (stream.title) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "detail-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "value" },
                });
                (stream.title);
            }
            if (stream.category_name) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "detail-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "value" },
                });
                (stream.category_name);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stream-full-actions" },
            });
            if (!stream.ended_at) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "recording-controls" },
                });
                if (!__VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(__VLS_ctx.isLoading))
                                    return;
                                if (!!(__VLS_ctx.streams.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedStreams[stream.id]))
                                    return;
                                if (!(!stream.ended_at))
                                    return;
                                if (!(!__VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId))))
                                    return;
                                __VLS_ctx.startRecording(Number(__VLS_ctx.streamerId));
                            } },
                        ...{ class: "btn btn-success" },
                        disabled: (__VLS_ctx.isStartingRecording),
                    });
                    (__VLS_ctx.isStartingRecording ? 'Starting...' : 'Force Record');
                }
                else {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(__VLS_ctx.isLoading))
                                    return;
                                if (!!(__VLS_ctx.streams.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedStreams[stream.id]))
                                    return;
                                if (!(!stream.ended_at))
                                    return;
                                if (!!(!__VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId))))
                                    return;
                                __VLS_ctx.stopRecording(Number(__VLS_ctx.streamerId));
                            } },
                        ...{ class: "btn btn-danger" },
                        disabled: (__VLS_ctx.isStoppingRecording),
                    });
                    (__VLS_ctx.isStoppingRecording ? 'Stopping...' : 'Stop Recording');
                }
            }
            if (stream.ended_at) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(__VLS_ctx.isLoading))
                                return;
                            if (!!(__VLS_ctx.streams.length === 0))
                                return;
                            if (!(__VLS_ctx.expandedStreams[stream.id]))
                                return;
                            if (!(stream.ended_at))
                                return;
                            __VLS_ctx.watchVideo(stream);
                        } },
                    ...{ class: "btn btn-primary" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: "fas fa-play" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.isLoading))
                            return;
                        if (!!(__VLS_ctx.streams.length === 0))
                            return;
                        if (!(__VLS_ctx.expandedStreams[stream.id]))
                            return;
                        __VLS_ctx.confirmDeleteStream(stream);
                    } },
                ...{ class: "btn btn-danger" },
                disabled: (__VLS_ctx.deletingStreamId === stream.id || (!stream.ended_at && __VLS_ctx.isStreamRecording(Number(__VLS_ctx.streamerId)))),
            });
            if (__VLS_ctx.deletingStreamId === stream.id) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: "fas fa-spinner fa-spin" },
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: "fas fa-trash-alt" },
                });
            }
        }
    }
}
if (__VLS_ctx.showDeleteModal) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.cancelDelete) },
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "warning-text" },
    });
    if (__VLS_ctx.streamToDelete) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stream-stream" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.formatDate(__VLS_ctx.streamToDelete.started_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.streamToDelete.title || '-');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.streamToDelete.category_name || '-');
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cancelDelete) },
        ...{ class: "btn btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.deleteStream) },
        ...{ class: "btn btn-danger" },
        disabled: (__VLS_ctx.deletingStreamId !== null),
    });
    if (__VLS_ctx.deletingStreamId !== null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "loader" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    }
}
if (__VLS_ctx.showDeleteAllModal) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.cancelDeleteAll) },
        ...{ class: "modal-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.streams.length);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "warning-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cancelDeleteAll) },
        ...{ class: "btn btn-secondary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.deleteAllStreams) },
        ...{ class: "btn btn-danger" },
        disabled: (__VLS_ctx.deletingAllStreams),
    });
    if (__VLS_ctx.deletingAllStreams) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "loader" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    }
}
if (__VLS_ctx.streams.length > 10 && !__VLS_ctx.deletingAllStreams) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.confirmDeleteAllStreams) },
        ...{ class: "floating-delete-btn" },
        title: (`Delete all ${__VLS_ctx.streams.length} streams`),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-trash-alt" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "fab-text" },
    });
    (__VLS_ctx.streams.length);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ class: "action-btn test-tooltip-btn" },
    'data-tooltip': "Test Tooltip Works!",
    ...{ style: {} },
});
/** @type {__VLS_StyleScopedClasses['streams-container']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-container']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-arrow-left']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-record-vinyl']} */ ;
/** @type {__VLS_StyleScopedClasses['streams-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streams-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-count']} */ ;
/** @type {__VLS_StyleScopedClasses['live-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['back-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-arrow-left']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-record-vinyl']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-all-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-list']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-card']} */ ;
/** @type {__VLS_StyleScopedClasses['expanded']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-compact-header']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-thumbnail']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-container']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image']} */ ;
/** @type {__VLS_StyleScopedClasses['category-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-video']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-info']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['live']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['meta-item']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-item']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-clock']} */ ;
/** @type {__VLS_StyleScopedClasses['meta-item']} */ ;
/** @type {__VLS_StyleScopedClasses['category-item']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-gamepad']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['play-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-play']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['expand-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-chevron-down']} */ ;
/** @type {__VLS_StyleScopedClasses['rotated']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-expanded-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-details']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-row']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-full-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['recording-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-success']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-play']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['warning-text']} */ ;
/** @type {__VLS_StyleScopedClasses['stream-stream']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['warning-text']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['floating-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['fab-text']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['test-tooltip-btn']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            CategoryTimeline: CategoryTimeline,
            streamerId: streamerId,
            streams: streams,
            isLoading: isLoading,
            isStartingRecording: isStartingRecording,
            isStoppingRecording: isStoppingRecording,
            isStartingOfflineRecording: isStartingOfflineRecording,
            showDeleteModal: showDeleteModal,
            streamToDelete: streamToDelete,
            deletingStreamId: deletingStreamId,
            showDeleteAllModal: showDeleteAllModal,
            deletingAllStreams: deletingAllStreams,
            expandedStreams: expandedStreams,
            hasLiveStreams: hasLiveStreams,
            getCategoryImageSrc: getCategoryImageSrc,
            formatDate: formatDate,
            calculateDuration: calculateDuration,
            handleBack: handleBack,
            watchVideo: watchVideo,
            isStreamRecording: isStreamRecording,
            startRecording: startRecording,
            forceOfflineRecording: forceOfflineRecording,
            stopRecording: stopRecording,
            toggleStreamExpansion: toggleStreamExpansion,
            confirmDeleteStream: confirmDeleteStream,
            cancelDelete: cancelDelete,
            deleteStream: deleteStream,
            confirmDeleteAllStreams: confirmDeleteAllStreams,
            cancelDeleteAll: cancelDeleteAll,
            deleteAllStreams: deleteAllStreams,
            handleImageError: handleImageError,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
