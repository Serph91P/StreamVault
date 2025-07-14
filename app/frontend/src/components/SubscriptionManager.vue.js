import { ref } from 'vue';
const subscriptions = ref([]);
async function loadSubscriptions() {
    const response = await fetch('/api/streamers/subscriptions');
    const data = await response.json();
    subscriptions.value = data.subscriptions;
}
async function deleteSubscription(id) {
    await fetch(`/api/streamers/subscriptions/${id}`, {
        method: 'DELETE'
    });
    await loadSubscriptions();
}
async function deleteAllSubscriptions() {
    if (!confirm('Are you sure you want to delete all subscriptions?'))
        return;
    await fetch('/api/streamers/subscriptions', {
        method: 'DELETE'
    });
    subscriptions.value = [];
}
function formatType(type) {
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
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "subscription-manager" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.loadSubscriptions) },
    ...{ class: "btn btn-primary" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.deleteAllSubscriptions) },
    ...{ class: "btn btn-danger" },
});
if (__VLS_ctx.subscriptions.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "subscription-list" },
    });
    for (const [sub] of __VLS_getVForSourceType((__VLS_ctx.subscriptions))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (sub.id),
            ...{ class: "subscription-item card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "subscription-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.formatType(sub.type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "status-badge" },
            ...{ class: (sub.status) },
        });
        (sub.status);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (new Date(sub.created_at).toLocaleString());
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.subscriptions.length))
                        return;
                    __VLS_ctx.deleteSubscription(sub.id);
                } },
            ...{ class: "btn btn-danger" },
        });
    }
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
}
/** @type {__VLS_StyleScopedClasses['subscription-manager']} */ ;
/** @type {__VLS_StyleScopedClasses['controls']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['subscription-list']} */ ;
/** @type {__VLS_StyleScopedClasses['subscription-item']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['subscription-info']} */ ;
/** @type {__VLS_StyleScopedClasses['status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            subscriptions: subscriptions,
            loadSubscriptions: loadSubscriptions,
            deleteSubscription: deleteSubscription,
            deleteAllSubscriptions: deleteAllSubscriptions,
            formatType: formatType,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
