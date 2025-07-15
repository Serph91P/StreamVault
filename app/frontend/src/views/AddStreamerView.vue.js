import AddStreamerForm from '@/components/AddStreamerForm.vue';
import TwitchImportForm from '@/components/TwitchImportForm.vue';
import { useRouter } from 'vue-router';
const router = useRouter();
const handleStreamerAdded = () => {
    router.push('/');
};
const handleStreamersImported = () => {
    router.push('/');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "add-streamer-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "add-streamer-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-section" },
});
/** @type {[typeof AddStreamerForm, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(AddStreamerForm, new AddStreamerForm({
    ...{ 'onStreamerAdded': {} },
}));
const __VLS_1 = __VLS_0({
    ...{ 'onStreamerAdded': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_0));
let __VLS_3;
let __VLS_4;
let __VLS_5;
const __VLS_6 = {
    onStreamerAdded: (__VLS_ctx.handleStreamerAdded)
};
var __VLS_2;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-section import-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "import-description" },
});
/** @type {[typeof TwitchImportForm, ]} */ ;
// @ts-ignore
const __VLS_7 = __VLS_asFunctionalComponent(TwitchImportForm, new TwitchImportForm({
    ...{ 'onStreamersImported': {} },
}));
const __VLS_8 = __VLS_7({
    ...{ 'onStreamersImported': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_7));
let __VLS_10;
let __VLS_11;
let __VLS_12;
const __VLS_13 = {
    onStreamersImported: (__VLS_ctx.handleStreamersImported)
};
var __VLS_9;
/** @type {__VLS_StyleScopedClasses['add-streamer-view']} */ ;
/** @type {__VLS_StyleScopedClasses['add-streamer-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['description']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['content-section']} */ ;
/** @type {__VLS_StyleScopedClasses['import-section']} */ ;
/** @type {__VLS_StyleScopedClasses['import-description']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AddStreamerForm: AddStreamerForm,
            TwitchImportForm: TwitchImportForm,
            handleStreamerAdded: handleStreamerAdded,
            handleStreamersImported: handleStreamersImported,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
