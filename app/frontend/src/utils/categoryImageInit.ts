/**
 * Global category images initialization
 * Category images are loaded on-demand when streamers play them
 */
import { useCategoryImages } from '@/composables/useCategoryImages'

let preloadInitialized = false

export async function initializeCategoryImages() {
  if (preloadInitialized) return
  
  try {
    console.log('🎮 Category image system initialized (on-demand loading only)')
    
    // No preloading - images will be loaded on-demand when streamers play categories
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
