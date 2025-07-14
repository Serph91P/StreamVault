import { ref, onMounted, computed } from 'vue';
const subscriptions = ref([]);
const streamers = ref([]);
const streamerMap = ref({});
const loadingResubscribe = ref(false);
const loading = ref(false);
// Create a computed map of twitch_id to streamer object for easier lookup
const twitchIdToStreamerMap = computed(() => {
    const map = {};
    streamers.value.forEach(streamer => {
        map[streamer.twitch_id] = streamer;
    });
    return map;
});
function formatEventType(type) {
    switch (type) {
        case 'stream.online':
            return 'Stream Start';
        case 'stream.offline':
            return 'Stream End';
        case 'channel.update':
            return 'Channel Update';
        default:
            return type;
    }
}
function getStreamerName(twitchId) {
    if (!twitchId)
        return 'Unknown';
    // Use the computed map for faster lookup
    const streamer = twitchIdToStreamerMap.value[twitchId];
    if (streamer) {
        return streamer.username;
    }
    // Log this issue for debugging
    console.log(`Could not find streamer for ID: ${twitchId}`);
    console.log("Available streamers:", streamers.value);
    // Return a formatted version of the ID as fallback
    return `Unknown (${twitchId})`;
}
async function loadStreamers() {
    try {
        const response = await fetch('/api/streamers');
        const data = await response.json();
        if (Array.isArray(data)) {
            // If the API returns an array directly
            streamers.value = data;
        }
        else if (data.streamers && Array.isArray(data.streamers)) {
            // If the API returns {streamers: [...]}
            streamers.value = data.streamers;
        }
        else {
            console.error('Unexpected streamer data format:', data);
            streamers.value = [];
        }
        console.log("Loaded streamers:", streamers.value);
        // Create a map for easier lookup
        streamers.value.forEach(streamer => {
            streamerMap.value[streamer.twitch_id] = streamer;
        });
        // Force a reactive update if needed
        if (subscriptions.value.length > 0) {
            subscriptions.value = [...subscriptions.value];
        }
    }
    catch (error) {
        console.error('Failed to load streamers:', error);
    }
}
async function loadSubscriptions() {
    loading.value = true;
    try {
        const response = await fetch('/api/streamers/subscriptions');
        const data = await response.json();
        subscriptions.value = data.subscriptions;
        // Load streamers after subscriptions
        await loadStreamers();
    }
    catch (error) {
        console.error('Failed to load subscriptions:', error);
    }
    finally {
        loading.value = false;
    }
}
async function resubscribeAll() {
    loadingResubscribe.value = true;
    try {
        const response = await fetch('/api/streamers/resubscribe-all', {
            method: 'POST',
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server response:', errorText);
            throw new Error(`Failed to resubscribe: ${response.status}`);
        }
        const data = await response.json();
        alert(`Success: ${data.message}`);
        await loadSubscriptions();
    }
    catch (error) {
        console.error('Failed to resubscribe all:', error.message);
        alert(`Error: ${error.message}`);
    }
    finally {
        loadingResubscribe.value = false;
    }
}
async function deleteSubscription(id) {
    try {
        const response = await fetch(`/api/streamers/subscriptions/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok)
            throw new Error('Failed to delete subscription');
        subscriptions.value = subscriptions.value.filter(sub => sub.id !== id);
    }
    catch (error) {
        console.error('Failed to delete subscription:', error);
    }
}
async function deleteAllSubscriptions() {
    if (!confirm('Are you sure you want to delete all subscriptions?'))
        return;
    loading.value = true;
    try {
        const response = await fetch('/api/streamers/subscriptions', {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server response:', errorText);
            throw new Error(`Failed to delete subscriptions: ${response.status}`);
        }
        const data = await response.json();
        console.log('Deleted subscriptions:', data);
        alert('All subscriptions successfully deleted!');
        subscriptions.value = [];
        await loadSubscriptions();
    }
    catch (error) {
        console.error('Failed to delete all subscriptions:', error.message);
        alert(`Error: ${error.message}`);
    }
    finally {
        loading.value = false;
    }
}
onMounted(loadSubscriptions);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "subscriptions-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "subscriptions-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.loadSubscriptions) },
    disabled: (__VLS_ctx.loading),
    ...{ class: "btn btn-primary" },
});
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
(__VLS_ctx.loading ? 'Loading...' : 'Refresh Subscriptions');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.deleteAllSubscriptions) },
    disabled: (__VLS_ctx.loading || !__VLS_ctx.subscriptions.length),
    ...{ class: "btn btn-danger" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.resubscribeAll) },
    ...{ class: "btn btn-success" },
    disabled: (__VLS_ctx.loadingResubscribe),
});
if (__VLS_ctx.loadingResubscribe) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "loader" },
    });
}
(__VLS_ctx.loadingResubscribe ? 'Resubscribing...' : 'Resubscribe All Streamers');
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else if (__VLS_ctx.subscriptions.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({
        ...{ class: "streamer-table" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
    for (const [sub] of __VLS_getVForSourceType((__VLS_ctx.subscriptions))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
            key: (sub.id),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
            'data-label': "Streamer",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "streamer-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "streamer-name" },
        });
        (__VLS_ctx.getStreamerName(sub.condition?.broadcaster_user_id));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
            'data-label': "Type",
        });
        (__VLS_ctx.formatEventType(sub.type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
            'data-label': "Status",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "status-badge" },
            ...{ class: (sub.status) },
        });
        (sub.status);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
            'data-label': "Created At",
        });
        (new Date(sub.created_at).toLocaleString());
        __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({
            'data-label': "Actions",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!(__VLS_ctx.subscriptions.length))
                        return;
                    __VLS_ctx.deleteSubscription(sub.id);
                } },
            ...{ class: "btn btn-danger" },
            disabled: (__VLS_ctx.loading),
        });
    }
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.loadSubscriptions) },
        ...{ class: "btn btn-primary" },
    });
}
/** @type {__VLS_StyleScopedClasses['subscriptions-view']} */ ;
/** @type {__VLS_StyleScopedClasses['subscriptions-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['description']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-success']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-state']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-table']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['streamer-name']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            subscriptions: subscriptions,
            loadingResubscribe: loadingResubscribe,
            loading: loading,
            formatEventType: formatEventType,
            getStreamerName: getStreamerName,
            loadSubscriptions: loadSubscriptions,
            resubscribeAll: resubscribeAll,
            deleteSubscription: deleteSubscription,
            deleteAllSubscriptions: deleteAllSubscriptions,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
