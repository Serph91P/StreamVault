/**
 * Global category images initialization
 * This preloads category images for the most common Twitch categories
 */
import { useCategoryImages } from '@/composables/useCategoryImages'

// Most popular Twitch categories that should be preloaded
const POPULAR_CATEGORIES = [
  'Just Chatting',
  'League of Legends', 
  'Valorant',
  'Grand Theft Auto V',
  'Minecraft',
  'Counter-Strike 2',
  'Fortnite',
  'World of Warcraft',
  'Apex Legends',
  'Call of Duty: Modern Warfare III',
  'Dota 2',
  'Overwatch 2',
  'Hearthstone',
  'Rocket League',
  'Among Us',
  'Fall Guys',
  'Dead by Daylight',
  'The Sims 4',
  'Chess',
  'Music'
]

let preloadInitialized = false

export async function initializeCategoryImages() {
  if (preloadInitialized) return
  
  try {
    const { preloadCategoryImages, getCacheStatus } = useCategoryImages()
    
    console.log('🎮 Initializing category images...')
    
    // Check current cache status
    const cacheStatus = await getCacheStatus()
    if (cacheStatus) {
      console.log(`📊 Category cache status: ${cacheStatus.cached_categories} cached, ${cacheStatus.failed_downloads} failed`)
    }
    
    // Preload popular categories
    await preloadCategoryImages(POPULAR_CATEGORIES)
    console.log(`🚀 Started preloading ${POPULAR_CATEGORIES.length} popular categories`)
    
    preloadInitialized = true
  } catch (error) {
    console.warn('⚠️ Failed to initialize category images:', error)
  }
}

export async function preloadCategoriesFromStreams(streams: any[]) {
  try {
    const { preloadCategoryImages } = useCategoryImages()
    
    // Extract unique category names from streams
    const categoryNames = streams
      .map(stream => stream.category_name)
      .filter(Boolean)
      .filter((name, index, self) => self.indexOf(name) === index) // Remove duplicates
    
    if (categoryNames.length > 0) {
      await preloadCategoryImages(categoryNames)
      console.log(`🎯 Preloaded ${categoryNames.length} categories from streams`)
    }
  } catch (error) {
    console.warn('⚠️ Failed to preload categories from streams:', error)
  }
}
