import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
const emit = defineEmits(['streamers-imported']);
const route = useRoute();
const router = useRouter();
// State
const channels = ref([]);
const selectedStreamers = ref([]);
const accessToken = ref(null);
const error = ref(null);
const loading = ref(false);
const loadingMessage = ref('Loading...');
const searchQuery = ref('');
const importing = ref(false);
const importResults = ref(null);
const callbackUrl = ref(null);
// Computed
const isAuthenticated = computed(() => !!accessToken.value);
const filteredChannels = computed(() => {
    if (!searchQuery.value)
        return channels.value;
    const query = searchQuery.value.toLowerCase();
    return channels.value.filter(channel => channel.login.toLowerCase().includes(query) ||
        channel.display_name.toLowerCase().includes(query));
});
// Methods
async function fetchCallbackUrl() {
    try {
        const response = await fetch('/api/twitch/callback-url');
        if (response.ok) {
            const data = await response.json();
            callbackUrl.value = data.url;
        }
    }
    catch (err) {
        console.error('Failed to fetch callback URL:', err);
        // We don't set an error as this is not critical
    }
}
function isSelected(channel) {
    return selectedStreamers.value.some(s => s.id === channel.id);
}
function toggleSelection(channel) {
    const index = selectedStreamers.value.findIndex(s => s.id === channel.id);
    if (index === -1) {
        selectedStreamers.value.push(channel);
    }
    else {
        selectedStreamers.value.splice(index, 1);
    }
}
function selectAll() {
    selectedStreamers.value = [...filteredChannels.value];
}
function deselectAll() {
    selectedStreamers.value = [];
}
async function startTwitchAuth() {
    try {
        loading.value = true;
        loadingMessage.value = 'Connecting to Twitch...';
        const response = await fetch('/api/twitch/auth-url');
        const data = await response.json();
        window.location.href = data.auth_url;
    }
    catch (err) {
        error.value = err.message || 'Failed to start Twitch authentication';
        loading.value = false;
    }
}
async function loadFollowedChannels(token) {
    try {
        loading.value = true;
        loadingMessage.value = 'Loading channels you follow...';
        const response = await fetch(`/api/twitch/followed-channels?access_token=${token}`);
        if (!response.ok) {
            throw new Error('Failed to load followed channels');
        }
        const data = await response.json();
        channels.value = data.channels || [];
    }
    catch (err) {
        error.value = err.message || 'Failed to load followed channels';
    }
    finally {
        loading.value = false;
    }
}
async function importSelected() {
    if (selectedStreamers.value.length === 0)
        return;
    try {
        importing.value = true;
        loading.value = true;
        loadingMessage.value = 'Importing selected streamers...';
        const response = await fetch('/api/twitch/import-streamers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(selectedStreamers.value)
        });
        if (!response.ok) {
            throw new Error('Failed to import streamers');
        }
        const results = await response.json();
        importResults.value = results;
        // Emit an event if the import was successful
        if (results.added > 0) {
            emit('streamers-imported');
        }
    }
    catch (err) {
        error.value = err.message || 'Failed to import streamers';
    }
    finally {
        loading.value = false;
        importing.value = false;
    }
}
function resetImport() {
    importResults.value = null;
    selectedStreamers.value = [];
}
function dismissError() {
    error.value = null;
}
// Lifecycle
onMounted(async () => {
    // Fetch callback URL
    await fetchCallbackUrl();
    // Check if we've returned from Twitch auth
    const tokenParam = route.query.token;
    const errorParam = route.query.error;
    if (errorParam) {
        if (errorParam === 'redirect_mismatch') {
            error.value = 'redirect_mismatch: The Redirect URL in your Twitch Developer Dashboard does not match your StreamVault configuration.';
        }
        else {
            error.value = errorParam === 'auth_failed'
                ? 'Authentication failed. Please try again.'
                : errorParam;
        }
    }
    if (tokenParam) {
        accessToken.value = tokenParam;
        // Clear the token from URL for security
        router.replace({ query: {} });
        // Load followed channels
        await loadFollowedChannels(tokenParam);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['btn-twitch']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-twitch']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-twitch']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-twitch']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-container']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['selected']} */ ;
/** @type {__VLS_StyleScopedClasses['selection-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['failure-list']} */ ;
/** @type {__VLS_StyleScopedClasses['failure-list']} */ ;
/** @type {__VLS_StyleScopedClasses['failure-list']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "twitch-import-container" },
});
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
    if (__VLS_ctx.error.includes('redirect_mismatch')) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "callback-url-hint" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        if (__VLS_ctx.callbackUrl) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "callback-url" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            (__VLS_ctx.callbackUrl);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        }
    }
}
if (!__VLS_ctx.isAuthenticated && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "auth-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setup-hint" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    if (__VLS_ctx.callbackUrl) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "callback-url" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
        (__VLS_ctx.callbackUrl);
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.startTwitchAuth) },
        ...{ class: "btn btn-twitch" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        viewBox: "0 0 24 24",
        width: "16",
        height: "16",
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
        fill: "white",
        d: "M11.64 5.93H13.07V10.21H11.64M15.57 5.93H17V10.21H15.57M7 2L3.43 5.57V18.43H7.71V22L11.29 18.43H14.14L20.57 12V2M19.14 11.29L16.29 14.14H13.43L10.93 16.64V14.14H7.71V3.43H19.14Z",
    });
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.loadingMessage);
}
if (__VLS_ctx.isAuthenticated && !__VLS_ctx.importing) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "selection-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "filter-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "search-box" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "text",
        value: (__VLS_ctx.searchQuery),
        placeholder: "Search streamers...",
        ...{ class: "form-control" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "filter-buttons" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.selectAll) },
        ...{ class: "btn btn-secondary" },
        disabled: (__VLS_ctx.filteredChannels.length === 0),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.deselectAll) },
        ...{ class: "btn btn-secondary" },
        disabled: (__VLS_ctx.selectedStreamers.length === 0),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.importSelected) },
        ...{ class: "btn btn-primary" },
        disabled: (__VLS_ctx.selectedStreamers.length === 0),
    });
    (__VLS_ctx.selectedStreamers.length);
    if (__VLS_ctx.channels.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-data-container" },
        });
    }
    else if (__VLS_ctx.filteredChannels.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-data-container" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "channels-grid" },
        });
        for (const [channel] of __VLS_getVForSourceType((__VLS_ctx.filteredChannels))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.isAuthenticated && !__VLS_ctx.importing))
                            return;
                        if (!!(__VLS_ctx.channels.length === 0))
                            return;
                        if (!!(__VLS_ctx.filteredChannels.length === 0))
                            return;
                        __VLS_ctx.toggleSelection(channel);
                    } },
                key: (channel.id),
                ...{ class: "channel-card" },
                ...{ class: ({ selected: __VLS_ctx.isSelected(channel) }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "channel-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "channel-name" },
            });
            (channel.display_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "channel-login" },
            });
            (channel.login);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "selection-indicator" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
                viewBox: "0 0 24 24",
                width: "16",
                height: "16",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
                fill: "currentColor",
                d: "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
            });
        }
    }
}
if (__VLS_ctx.importResults) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "import-results content-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "results-summary" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-value" },
    });
    (__VLS_ctx.importResults.total);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-value success" },
    });
    (__VLS_ctx.importResults.added);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-value info" },
    });
    (__VLS_ctx.importResults.skipped);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "result-value error" },
    });
    (__VLS_ctx.importResults.failed);
    if (__VLS_ctx.importResults.failures && __VLS_ctx.importResults.failures.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "failure-list" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
        for (const [failure, index] of __VLS_getVForSourceType((__VLS_ctx.importResults.failures))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                key: (index),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (failure.username);
            (failure.reason);
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.resetImport) },
        ...{ class: "btn btn-primary" },
    });
}
/** @type {__VLS_StyleScopedClasses['twitch-import-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['callback-url-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['callback-url']} */ ;
/** @type {__VLS_StyleScopedClasses['auth-section']} */ ;
/** @type {__VLS_StyleScopedClasses['setup-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['callback-url']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-twitch']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['selection-section']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-container']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-container']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data-container']} */ ;
/** @type {__VLS_StyleScopedClasses['channels-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-card']} */ ;
/** @type {__VLS_StyleScopedClasses['selected']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-content']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-name']} */ ;
/** @type {__VLS_StyleScopedClasses['channel-login']} */ ;
/** @type {__VLS_StyleScopedClasses['selection-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['import-results']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['results-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-label']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-label']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['success']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-label']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-label']} */ ;
/** @type {__VLS_StyleScopedClasses['result-value']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['failure-list']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            channels: channels,
            selectedStreamers: selectedStreamers,
            error: error,
            loading: loading,
            loadingMessage: loadingMessage,
            searchQuery: searchQuery,
            importing: importing,
            importResults: importResults,
            callbackUrl: callbackUrl,
            isAuthenticated: isAuthenticated,
            filteredChannels: filteredChannels,
            isSelected: isSelected,
            toggleSelection: toggleSelection,
            selectAll: selectAll,
            deselectAll: deselectAll,
            startTwitchAuth: startTwitchAuth,
            importSelected: importSelected,
            resetImport: resetImport,
        };
    },
    emits: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    emits: {},
});
; /* PartiallyEnd: #4569/main.vue */
