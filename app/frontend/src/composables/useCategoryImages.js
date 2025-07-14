import { reactive } from 'vue';
// Cache for category images to avoid repeated API calls
const categoryImageCache = reactive({});
const pendingRequests = new Set();
export function useCategoryImages() {
    const getCategoryImage = (categoryName) => {
        if (!categoryName)
            return '/images/categories/default-category.svg';
        // Check if we have it cached
        if (categoryImageCache[categoryName]) {
            return categoryImageCache[categoryName];
        }
        // Trigger async fetch if not already pending
        if (!pendingRequests.has(categoryName)) {
            fetchCategoryImage(categoryName);
        }
        // Return fallback for now
        return getIconFallback(categoryName);
    };
    const getIconFallback = (categoryName) => {
        const categoryIcons = {
            'Just Chatting': 'fa-comments',
            'League of Legends': 'fa-gamepad',
            'Valorant': 'fa-crosshairs',
            'Minecraft': 'fa-cube',
            'Grand Theft Auto V': 'fa-car',
            'Counter-Strike 2': 'fa-bullseye',
            'World of Warcraft': 'fa-magic',
            'Fortnite': 'fa-gamepad',
            'Apex Legends': 'fa-trophy',
            'Call of Duty': 'fa-bomb',
            'Music': 'fa-music',
            'Art': 'fa-palette',
            'Science & Technology': 'fa-microscope',
            'Sports': 'fa-football-ball',
            'Travel & Outdoors': 'fa-mountain',
            'Dota 2': 'fa-shield-alt',
            'Overwatch 2': 'fa-gamepad',
            'Hearthstone': 'fa-magic',
            'Rocket League': 'fa-car-side',
            'Among Us': 'fa-user-astronaut'
        };
        return `icon:${categoryIcons[categoryName] || 'fa-gamepad'}`;
    };
    const fetchCategoryImage = async (categoryName) => {
        if (pendingRequests.has(categoryName))
            return;
        try {
            pendingRequests.add(categoryName);
            const response = await fetch(`/api/categories/image/${encodeURIComponent(categoryName)}`);
            if (response.ok) {
                const data = await response.json();
                // If we got a real image URL (not an icon), cache it
                if (data.image_url && !data.image_url.startsWith('icon:')) {
                    categoryImageCache[categoryName] = data.image_url;
                }
                else {
                    // Cache the icon fallback too to avoid repeated requests
                    categoryImageCache[categoryName] = data.image_url;
                }
            }
        }
        catch (error) {
            console.warn(`Failed to fetch category image for ${categoryName}:`, error);
            // Cache the fallback to avoid repeated failed requests
            categoryImageCache[categoryName] = getIconFallback(categoryName);
        }
        finally {
            pendingRequests.delete(categoryName);
        }
    };
    const preloadCategoryImages = async (categoryNames) => {
        try {
            const response = await fetch('/api/categories/preload-images', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(categoryNames)
            });
            if (response.ok) {
                const data = await response.json();
                console.log('Preloading category images:', data.message);
                return data;
            }
        }
        catch (error) {
            console.warn('Failed to preload category images:', error);
        }
    };
    const getCacheStatus = async () => {
        try {
            const response = await fetch('/api/categories/cache-status');
            if (response.ok) {
                return await response.json();
            }
        }
        catch (error) {
            console.warn('Failed to get cache status:', error);
        }
    };
    const refreshImages = async (categoryNames) => {
        try {
            const response = await fetch('/api/categories/refresh-images', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(categoryNames)
            });
            if (response.ok) {
                const data = await response.json();
                console.log('Refreshing category images:', data.message);
                // Clear local cache for these categories to force reload
                categoryNames.forEach(name => {
                    if (categoryImageCache[name]) {
                        delete categoryImageCache[name];
                    }
                });
                return data;
            }
        }
        catch (error) {
            console.warn('Failed to refresh category images:', error);
        }
    };
    const clearCache = () => {
        Object.keys(categoryImageCache).forEach(key => {
            delete categoryImageCache[key];
        });
        console.log('Category image cache cleared');
    };
    return {
        getCategoryImage,
        getIconFallback,
        preloadCategoryImages,
        getCacheStatus,
        refreshImages,
        clearCache,
        categoryImageCache
    };
}
