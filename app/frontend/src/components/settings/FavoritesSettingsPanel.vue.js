import { ref, computed, onMounted, watch } from 'vue';
import { useCategoryImages } from '@/composables/useCategoryImages';
// State variables
const searchQuery = ref('');
const showFavoritesOnly = ref(false);
const categories = ref([]);
const isLoading = ref(true);
const error = ref(null);
const imageErrors = ref(new Set());
const isDownloadingImages = ref(false);
// Use category images composable
const { getCategoryImage, preloadCategoryImages, refreshImages, clearCache } = useCategoryImages();
// Computed properties
const filteredCategories = computed(() => {
    let result = categories.value;
    // Filter by favorites if enabled
    if (showFavoritesOnly.value) {
        result = result.filter(category => category.is_favorite);
    }
    // Filter by search query
    if (searchQuery.value.trim()) {
        const query = searchQuery.value.toLowerCase();
        result = result.filter(category => category.name.toLowerCase().includes(query));
    }
    // Debug log
    return result;
});
// Methods
const fetchCategories = async () => {
    isLoading.value = true;
    error.value = null;
    try {
        const response = await fetch('/api/categories');
        if (!response.ok) {
            throw new Error('Failed to fetch categories');
        }
        const data = await response.json();
        // Wichtig: Die API gibt die Kategorien in einem "categories"-Feld zurück
        if (data.categories && Array.isArray(data.categories)) {
            categories.value = data.categories;
            // Preload category images for all categories
            const categoryNames = data.categories
                .map((cat) => cat.name)
                .filter((name) => Boolean(name));
            if (categoryNames.length > 0) {
                preloadCategoryImages(categoryNames);
            }
        }
        else {
            console.error('Unexpected API response format:', data);
            throw new Error('Unexpected API response format');
        }
    }
    catch (err) {
        error.value = err.message || 'An error occurred while fetching categories';
        console.error('Error fetching categories:', err);
    }
    finally {
        isLoading.value = false;
    }
};
const toggleFavoritesFilter = () => {
    showFavoritesOnly.value = !showFavoritesOnly.value;
};
const toggleFavorite = async (category) => {
    try {
        // Basierend auf der API-Route aus categories.py
        const endpoint = category.is_favorite
            ? `/api/categories/favorites/${category.id}` // DELETE für Entfernen
            : `/api/categories/favorites`; // POST für Hinzufügen
        const method = category.is_favorite ? 'DELETE' : 'POST';
        const body = !category.is_favorite ? JSON.stringify({ category_id: category.id }) : undefined;
        const response = await fetch(endpoint, {
            method,
            headers: {
                'Content-Type': 'application/json'
            },
            body
        });
        if (!response.ok) {
            throw new Error(`Failed to ${category.is_favorite ? 'remove from' : 'add to'} favorites`);
        }
        // Update the local state
        category.is_favorite = !category.is_favorite;
    }
    catch (err) {
        error.value = err.message;
        console.error('Error toggling favorite status:', err);
    }
};
const formatImageUrl = (url, width, height) => {
    if (!url)
        return '';
    // Handle Twitch-Format mit Platzhaltern
    if (url.includes('{width}') && url.includes('{height}')) {
        return url
            .replace('{width}', width.toString())
            .replace('{height}', height.toString());
    }
    return url;
};
const handleImageError = (event) => {
    const img = event.target;
    if (img.src && !imageErrors.value.has(img.src)) {
        console.error(`Failed to load image: ${img.src}`);
        imageErrors.value.add(img.src);
        // Platzhalter für fehlerhafte Bilder
        img.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNDQiIGhlaWdodD0iMTkyIiBmaWxsPSJub25lIiB2aWV3Qm94PSIwIDAgMTQ0IDE5MiI+PHJlY3Qgd2lkdGg9IjE0NCIgaGVpZ2h0PSIxOTIiIGZpbGw9IiMyZDJkMzUiLz48dGV4dCB4PSI3MiIgeT0iOTYiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNiIgZmlsbD0iI2VmZWZmMSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+';
    }
};
const downloadMissingImages = async () => {
    try {
        isDownloadingImages.value = true;
        error.value = null;
        // Get all category names that don't have proper images (those using icon: fallbacks)
        const categoriesNeedingImages = categories.value.filter(category => {
            const imageUrl = getCategoryImage(category.name);
            return imageUrl.startsWith('icon:') || imageUrl.includes('default-category.svg');
        }).map(category => category.name);
        if (categoriesNeedingImages.length === 0) {
            return;
        }
        // Use the refresh function to force re-download even if images exist but are broken
        const refreshResponse = await refreshImages(categoriesNeedingImages);
        if (!refreshResponse) {
            throw new Error('Failed to start image refresh');
        }
        // Wait a bit for the downloads to complete
        await new Promise(resolve => setTimeout(resolve, 3000));
        // Clear local cache and force reload
        clearCache();
        // Force a re-render to pick up new images  
        await fetchCategories();
        // Preload the new images to update our local cache
        await preloadCategoryImages(categoriesNeedingImages);
    }
    catch (err) {
        error.value = err.message || 'Failed to download category images';
        console.error('Error downloading category images:', err);
    }
    finally {
        isDownloadingImages.value = false;
    }
};
const checkMissingImages = async () => {
    try {
        const response = await fetch('/api/categories/missing-images');
        if (response.ok) {
            const report = await response.json();
            const message = `Images Report:
Total categories: ${report.total_categories}
Have images: ${report.have_images}
Missing images: ${report.missing_images}

Missing categories: ${report.categories_missing_images.join(', ')}`;
            alert(message);
        }
        else {
            throw new Error('Failed to get missing images report');
        }
    }
    catch (err) {
        error.value = err.message || 'Failed to check missing images';
        console.error('Error checking missing images:', err);
    }
};
// Initialize component
onMounted(() => {
    fetchCategories();
});
// Debug-Output
watch(categories, (newCategories) => {
    if (newCategories.length > 0) {
    }
}, { immediate: true, deep: true });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['filter-row']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['button-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['category-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['category-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['category-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['is-favorite']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['is-favorite']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['is-favorite']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['star-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-info']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "search-box" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    placeholder: "Search for game...",
    ...{ class: "form-control" },
});
(__VLS_ctx.searchQuery);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-buttons" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleFavoritesFilter) },
    ...{ class: "btn" },
    ...{ class: ({ 'btn-primary': __VLS_ctx.showFavoritesOnly, 'btn-secondary': !__VLS_ctx.showFavoritesOnly }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-icon" },
});
(__VLS_ctx.showFavoritesOnly ? '★' : '☆');
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-text" },
});
(__VLS_ctx.showFavoritesOnly ? 'Show All' : 'Favorites Only');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.fetchCategories) },
    ...{ class: "btn btn-secondary" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-icon" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.downloadMissingImages) },
    ...{ class: "btn btn-info" },
    disabled: (__VLS_ctx.isDownloadingImages),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-icon" },
});
(__VLS_ctx.isDownloadingImages ? '⏳' : '📥');
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-text" },
});
(__VLS_ctx.isDownloadingImages ? 'Downloading...' : 'Get Images');
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.checkMissingImages) },
    ...{ class: "btn btn-warning" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-icon" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "button-text" },
});
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.error);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "categories-grid" },
});
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    if (__VLS_ctx.filteredCategories.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-categories" },
        });
        if (__VLS_ctx.showFavoritesOnly) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        }
        else if (__VLS_ctx.searchQuery) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (__VLS_ctx.searchQuery);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.br, __VLS_intrinsicElements.br)({});
        }
    }
    else {
        const __VLS_0 = {}.TransitionGroup;
        /** @type {[typeof __VLS_components.TransitionGroup, typeof __VLS_components.TransitionGroup, ]} */ ;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
            name: "category-cards",
            tag: "div",
            ...{ class: "category-cards" },
        }));
        const __VLS_2 = __VLS_1({
            name: "category-cards",
            tag: "div",
            ...{ class: "category-cards" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        __VLS_3.slots.default;
        for (const [category] of __VLS_getVForSourceType((__VLS_ctx.filteredCategories))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (category.id),
                ...{ class: "category-card" },
                ...{ class: ({ 'is-favorite': category.is_favorite }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-image-wrapper" },
            });
            if (!__VLS_ctx.getCategoryImage(category.name).startsWith('icon:')) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                    ...{ onError: (__VLS_ctx.handleImageError) },
                    src: (__VLS_ctx.getCategoryImage(category.name)),
                    alt: "Game box art",
                    ...{ class: "category-image" },
                    loading: "lazy",
                });
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "category-image-placeholder" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: (__VLS_ctx.getCategoryImage(category.name).replace('icon:', '')) },
                    ...{ class: "category-icon" },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
                ...{ class: "category-name" },
            });
            (category.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-meta" },
            });
            if (category.last_seen) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "category-date" },
                });
                (new Date(category.last_seen).toLocaleDateString());
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "category-stats" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (category.stream_count || 0);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.isLoading))
                            return;
                        if (!!(__VLS_ctx.filteredCategories.length === 0))
                            return;
                        __VLS_ctx.toggleFavorite(category);
                    } },
                ...{ class: "btn-icon" },
                ...{ class: ({ 'is-favorite': category.is_favorite }) },
                title: (category.is_favorite ? 'Remove from favorites' : 'Add to favorites'),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
                viewBox: "0 0 24 24",
                width: "18",
                height: "18",
                ...{ class: "star-icon" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
                fill: (category.is_favorite ? '#FFD700' : 'currentColor'),
                d: "M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "button-label" },
            });
            (category.is_favorite ? 'Unfavorite' : 'Favorite');
        }
        var __VLS_3;
    }
}
/** @type {__VLS_StyleScopedClasses['filter-container']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-row']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['form-control']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['button-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['button-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['button-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['button-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-info']} */ ;
/** @type {__VLS_StyleScopedClasses['button-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['button-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['button-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['button-text']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['categories-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['no-categories']} */ ;
/** @type {__VLS_StyleScopedClasses['category-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['category-card']} */ ;
/** @type {__VLS_StyleScopedClasses['is-favorite']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image']} */ ;
/** @type {__VLS_StyleScopedClasses['category-image-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-content']} */ ;
/** @type {__VLS_StyleScopedClasses['category-name']} */ ;
/** @type {__VLS_StyleScopedClasses['category-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['category-date']} */ ;
/** @type {__VLS_StyleScopedClasses['category-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['category-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['is-favorite']} */ ;
/** @type {__VLS_StyleScopedClasses['star-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['button-label']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            searchQuery: searchQuery,
            showFavoritesOnly: showFavoritesOnly,
            isLoading: isLoading,
            error: error,
            isDownloadingImages: isDownloadingImages,
            getCategoryImage: getCategoryImage,
            filteredCategories: filteredCategories,
            fetchCategories: fetchCategories,
            toggleFavoritesFilter: toggleFavoritesFilter,
            toggleFavorite: toggleFavorite,
            handleImageError: handleImageError,
            downloadMissingImages: downloadMissingImages,
            checkMissingImages: checkMissingImages,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
