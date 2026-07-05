import { ref, reactive } from 'vue'
import { categoriesApi } from '@/services/api'

// Cache for category images to avoid repeated API calls
const categoryImageCache = reactive<{ [key: string]: string }>({})
const pendingRequests = new Set<string>()
const cacheVersion = ref(0) // Used to force reactivity updates when cache changes

// Helper function to trigger reactivity tracking
function ensureReactivity() {
  // Intentionally access cacheVersion.value to ensure Vue tracks this dependency
  // This makes getCategoryImage reactive to cache updates
  return cacheVersion.value
}

export function useCategoryImages() {
  const getCategoryImage = (categoryName: string): string => {
    if (!categoryName) return '/images/categories/default-category.svg'
    
    // Trigger reactivity tracking - this ensures the component re-renders when cache updates
    ensureReactivity()
    
    // Check if we have it cached
    if (categoryImageCache[categoryName]) {
      return categoryImageCache[categoryName]
    }
    
    // Trigger async fetch if not already pending
    if (!pendingRequests.has(categoryName)) {
      fetchCategoryImage(categoryName)
    }
    
    // Return fallback for now
    return getIconFallback(categoryName)
  }

  const getIconFallback = (categoryName: string): string => {
    const categoryIcons: { [key: string]: string } = {
      'Just Chatting': 'info',
      'League of Legends': 'gamepad',
      'Valorant': 'circle',
      'Minecraft': 'database',
      'Grand Theft Auto V': 'activity',
      'Counter-Strike 2': 'circle',
      'World of Warcraft': 'zap',
      'Fortnite': 'gamepad',
      'Apex Legends': 'star',
      'Call of Duty': 'alert-triangle',
      'Music': 'activity',
      'Art': 'activity',
      'Science & Technology': 'search',
      'Sports': 'activity',
      'Travel & Outdoors': 'activity',
      'Dota 2': 'check-circle',
      'Overwatch 2': 'gamepad',
      'Hearthstone': 'zap',
      'Rocket League': 'activity-side',
      'Among Us': 'user'
    }
    
    return `icon:${categoryIcons[categoryName] || 'gamepad'}`
  }

  const fetchCategoryImage = async (categoryName: string) => {
    if (pendingRequests.has(categoryName)) return
    
    try {
      pendingRequests.add(categoryName)
      
      const data = await categoriesApi.getImage(categoryName)

      // If we got a real image URL (not an icon), cache it
      if (data.image_url && !data.image_url.startsWith('icon:')) {
        categoryImageCache[categoryName] = data.image_url
      } else {
        // Cache the icon fallback too to avoid repeated requests
        categoryImageCache[categoryName] = data.image_url
      }

      // Trigger reactivity update
      cacheVersion.value++
    } catch (error) {
      console.warn(`Failed to fetch category image for ${categoryName}:`, error)
      // Cache the fallback to avoid repeated failed requests
      categoryImageCache[categoryName] = getIconFallback(categoryName)
      cacheVersion.value++
    } finally {
      pendingRequests.delete(categoryName)
    }
  }

  const preloadCategoryImages = async (categoryNames: string[]) => {
    try {
      const data = await categoriesApi.preloadImages(categoryNames)
      console.log('Preloading category images:', data.message)
      return data
    } catch (error) {
      console.warn('Failed to preload category images:', error)
    }
  }

  const getCacheStatus = async () => {
    try {
      return await categoriesApi.getCacheStatus()
    } catch (error) {
      console.warn('Failed to get cache status:', error)
    }
  }

  const refreshImages = async (categoryNames: string[]) => {
    try {
      const data = await categoriesApi.refreshImages(categoryNames)
      console.log('Refreshing category images:', data.message)

      // Clear local cache for these categories to force reload
      categoryNames.forEach(name => {
        if (categoryImageCache[name]) {
          delete categoryImageCache[name]
        }
      })

      return data
    } catch (error) {
      console.warn('Failed to refresh category images:', error)
    }
  }

  const clearCache = () => {
    Object.keys(categoryImageCache).forEach(key => {
      delete categoryImageCache[key]
    })
    cacheVersion.value++
    console.log('Category image cache cleared')
  }

  return {
    getCategoryImage,
    getIconFallback,
    preloadCategoryImages,
    getCacheStatus,
    refreshImages,
    clearCache,
    categoryImageCache,
    cacheVersion
  }
}
