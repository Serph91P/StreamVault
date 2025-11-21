<template>
  <div>
    
    <!-- Filter und Suche - Verbessert für Mobile -->
    <div class="filter-container settings-section settings-section--surface">
      <div class="filter-row">
        <div class="search-box">
          <input 
            v-model="searchQuery" 
            placeholder="Search for game..." 
            class="form-control"
          />
        </div>
        <div class="filter-buttons">
          <button 
            @click="toggleFavoritesFilter" 
            class="btn" 
            :class="{ 'btn-primary': showFavoritesOnly, 'btn-secondary': !showFavoritesOnly }"
          >
            <span class="button-icon">{{ showFavoritesOnly ? '★' : '☆' }}</span>
            <span class="button-text">{{ showFavoritesOnly ? 'Show All' : 'Favorites Only' }}</span>
          </button>
          <button @click="fetchCategories" class="btn btn-secondary">
            <span class="button-icon">↻</span>
            <span class="button-text">Refresh</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Fehleranzeige -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
    
    <!-- Kategorie-Liste -->
    <div class="categories-grid">
      <div v-if="isLoading" class="loading settings-section settings-section--surface">
        <div class="spinner"></div>
        <p>Loading categories...</p>
      </div>
      <template v-else>
        <div v-if="filteredCategories.length === 0" class="no-categories settings-section settings-section--surface">
          <p v-if="showFavoritesOnly">You haven't marked any categories as favorites yet.</p>
          <p v-else-if="searchQuery">No categories found containing "{{ searchQuery }}".</p>
          <p v-else>
            No categories found. Categories are created when streamers change games during streams.<br>
            This happens automatically when a streamer changes their game on Twitch.
          </p>
        </div>
          <!-- Category Cards Grid -->
        <TransitionGroup v-else name="category-cards" tag="div" class="category-cards">
          <div 
            v-for="category in filteredCategories" 
            :key="category.id"
            class="category-card"
            :class="{ 'is-favorite': category.is_favorite }"
          >
            <div class="category-image-wrapper">
              <img 
                v-if="!getCategoryImage(category.name).startsWith('icon:')" 
                :src="getCategoryImage(category.name)" 
                alt="Game box art"
                class="category-image"
                loading="lazy"
                @error="handleImageError"
              />
              <div v-else class="category-image-placeholder">
                <i 
                  :class="getCategoryImage(category.name).replace('icon:', '')"
                  class="category-icon"
                ></i>
              </div>
            </div>
            <div class="category-content">
              <h4 class="category-name">{{ category.name }}</h4>
              <div class="category-meta">
                <span class="category-date" v-if="category.last_seen">Last seen: {{ new Date(category.last_seen).toLocaleDateString() }}</span>
              </div>
              <div class="category-actions">
                <div class="category-stats">
                  <span>{{ category.stream_count || 0 }} streams</span>
                </div>
                <button 
                  @click="toggleFavorite(category)"
                  class="btn-icon"
                  :class="{'is-favorite': category.is_favorite}"
                  :title="category.is_favorite ? 'Remove from favorites' : 'Add to favorites'"
                >
                  <svg viewBox="0 0 24 24" width="18" height="18" class="star-icon">
                    <path 
                      :fill="category.is_favorite ? 'var(--warning-color)' : 'currentColor'" 
                      d="M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z"
                    />
                  </svg>
                  <span class="button-label">{{ category.is_favorite ? 'Unfavorite' : 'Favorite' }}</span>                </button>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useCategoryImages } from '@/composables/useCategoryImages';
import { useToast } from '@/composables/useToast';
import { IMAGE_LOADING } from '@/config/constants';

interface Category {
  id: string;
  twitch_id: string;
  name: string;
  box_art_url: string | null;
  is_favorite: boolean;
  first_seen?: string;
  last_seen?: string;
  stream_count?: number;
}

// State variables
const searchQuery = ref('');
const showFavoritesOnly = ref(false);
const categories = ref<Category[]>([]);
const isLoading = ref(true);
const error = ref<string | null>(null);
const imageErrors = ref<Set<string>>(new Set());

// Use category images composable
const { getCategoryImage, preloadCategoryImages, refreshImages, clearCache } = useCategoryImages();
const toast = useToast();

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
    result = result.filter(category => 
      category.name.toLowerCase().includes(query)
    );
  }
  
   // Debug log
  return result;
});

// Methods
const fetchCategories = async () => {
  isLoading.value = true;
  error.value = null;
  
  try {
    const response = await fetch('/api/categories', {
      credentials: 'include' // CRITICAL: Required to send session cookie
    });
    
    if (!response.ok) {
      // Check for specific HTTP error codes
      if (response.status === 500) {
        throw new Error('Server error - please check application logs');
      } else if (response.status === 404) {
        // Categories endpoint not found
        categories.value = [];
        return;
      } else {
        throw new Error(`Failed to fetch categories (HTTP ${response.status})`);
      }
    }
    
    const data = await response.json();
    
    // Handle different response formats
    if (data.categories && Array.isArray(data.categories)) {
      categories.value = data.categories;
      
      // Don't preload all images immediately - let them lazy load with intersection observer
      // Only preload visible categories (configurable count)
      const visibleCategoryNames = data.categories
        .slice(0, IMAGE_LOADING.VISIBLE_CATEGORIES_PRELOAD_COUNT)
        .map((cat: any) => cat.name)
        .filter((name: string | null): name is string => Boolean(name));
      
      if (visibleCategoryNames.length > 0) {
        // Use nextTick to defer image loading until after DOM update
        // This is more reliable than setTimeout and respects Vue's rendering lifecycle
        nextTick(() => {
          // Error handling for image preloading to prevent unhandled promise rejections
          try {
            preloadCategoryImages(visibleCategoryNames);
          } catch (err) {
            console.warn('Failed to preload category images:', err);
            // Non-critical error - images will still lazy load when visible
          }
        });
      }
    } else if (Array.isArray(data)) {
      // Direct array response
      categories.value = data;
    } else {
      // Unexpected format but no categories found
      console.warn('Unexpected API response format:', data);
      categories.value = [];
    }
  } catch (err: any) {
    // More user-friendly error messages
    if (err.message.includes('Server error')) {
      error.value = 'Server error - please try again later or check if the application is properly configured';
    } else if (err.message.includes('Failed to fetch')) {
      error.value = 'Network error - please check your connection and try again';
    } else {
      error.value = err.message || 'An error occurred while loading categories';
    }
    
    console.error('Error fetching categories:', err);
    // Don't clear categories array on error - keep error visible to user
    // categories.value = []; // Removed to maintain error visibility
  } finally {
    isLoading.value = false;
  }
};

const toggleFavoritesFilter = () => {
  showFavoritesOnly.value = !showFavoritesOnly.value;
};

const toggleFavorite = async (category: Category) => {
  try {
    // Basierend auf der API-Route aus categories.py
    const endpoint = category.is_favorite 
      ? `/api/categories/favorites/${category.id}`  // DELETE für Entfernen
      : `/api/categories/favorites`;               // POST für Hinzufügen
    
    const method = category.is_favorite ? 'DELETE' : 'POST';
    const body = !category.is_favorite ? JSON.stringify({ category_id: category.id }) : undefined;
    
    const response = await fetch(endpoint, {
      method,
      credentials: 'include', // CRITICAL: Required to send session cookie
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
    
    // Show success toast
    toast.success(
      category.is_favorite 
        ? `Added "${category.name}" to favorites` 
        : `Removed "${category.name}" from favorites`
    );
  } catch (err: any) {
    error.value = err.message;
    console.error('Error toggling favorite status:', err);
    toast.error('Failed to update favorite status');
  }
};

const formatImageUrl = (url: string | null, width: number, height: number): string => {
  if (!url) return '';
  
  // Handle Twitch-Format mit Platzhaltern
  if (url.includes('{width}') && url.includes('{height}')) {
    return url
      .replace('{width}', width.toString())
      .replace('{height}', height.toString());
  }
  
  return url;
};

const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement;
  if (img.src && !imageErrors.value.has(img.src)) {
    console.error(`Failed to load image: ${img.src}`);
    imageErrors.value.add(img.src);
    
    // Platzhalter für fehlerhafte Bilder
    img.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNDQiIGhlaWdodD0iMTkyIiBmaWxsPSJub25lIiB2aWV3Qm94PSIwIDAgMTQ0IDE5MiI+PHJlY3Qgd2lkdGg9IjE0NCIgaGVpZ2h0PSIxOTIiIGZpbGw9IiMyZDJkMzUiLz48dGV4dCB4PSI3MiIgeT0iOTYiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNiIgZmlsbD0iI2VmZWZmMSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+';
  }
};

// Initialize component
onMounted(() => {
  fetchCategories();
});
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// FAVORITES SETTINGS PANEL - Game Categories with Twitch Box Art
// ============================================================================

// ============================================================================
// FILTER SECTION
// ============================================================================

.filter-container {
  margin-bottom: v.$spacing-4;
}

.filter-row {
  display: flex;
  gap: v.$spacing-3;
  align-items: center;
  flex-wrap: wrap;
  
  @include m.respond-below('sm') {
    flex-direction: column;
    align-items: stretch;
  }
}

.search-box {
  flex: 1;
  min-width: 200px;
  
  @include m.respond-below('sm') {
    width: 100%;
  }
}

.filter-buttons {
  display: flex;
  gap: v.$spacing-2;
  
  @include m.respond-below('sm') {
    width: 100%;
    
    .btn {
      flex: 1;
    }
  }
}

.button-icon {
  margin-right: v.$spacing-2;
}

// ============================================================================
// CATEGORIES GRID - Twitch Box Art Format (285x380 aspect ratio)
// ============================================================================

.categories-grid {
  margin-top: v.$spacing-4;
}

.category-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));  // Optimal size for card proportions
  gap: v.$spacing-4;  // Consistent spacing
  width: 100%;  // Force full width
  
  @include m.respond-below('lg') {  // < 1024px
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: v.$spacing-3;
  }
  
  @include m.respond-below('md') {  // < 768px (tablet)
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: v.$spacing-3;
  }
  
  @include m.respond-below('sm') {  // < 640px (mobile)
    grid-template-columns: repeat(2, 1fr);  // Always 2 columns on mobile
    gap: v.$spacing-2;
  }
}

.category-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all v.$duration-200 v.$ease-out;
  display: flex;
  flex-direction: column;
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    border-color: var(--primary-color);
    
    [data-theme="light"] & {
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }
  }
  
  &.is-favorite {
    border-color: var(--warning-color);
    border-width: 2px;
  }
}

// ============================================================================
// CATEGORY IMAGE - Twitch Box Art (3:4 aspect ratio)
// ============================================================================

.category-image-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4; // Twitch box art ratio (285x380)
  background: var(--background-darker);
  overflow: hidden;
}

.category-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.category-image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--background-darker) 0%, var(--background-card) 100%);
  
  .category-icon {
    font-size: 3rem;
    color: var(--text-secondary);
    opacity: 0.5;
  }
}

// ============================================================================
// CATEGORY CONTENT - Title, Meta, Actions
// ============================================================================

.category-content {
  padding: v.$spacing-3;
  display: flex;
  flex-direction: column;
  gap: v.$spacing-2;
  flex: 1;
}

.category-name {
  font-size: v.$text-sm;
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;
  
  // Clamp to 2 lines
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 2.6em; // Reserve space for 2 lines
}

.category-meta {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-1;
  font-size: v.$text-xs;
  color: var(--text-secondary);
}

.category-date {
  display: block;
}

// ============================================================================
// CATEGORY ACTIONS - Stats + Favorite Button
// ============================================================================

.category-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: v.$spacing-2;
  border-top: 1px solid var(--border-color);
}

.category-stats {
  font-size: v.$text-xs;
  color: var(--text-secondary);
  font-weight: v.$font-medium;
}

.btn-icon {
  display: inline-flex;
  align-items: center;
  gap: v.$spacing-1;
  padding: v.$spacing-1 v.$spacing-2;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  color: var(--text-secondary);
  font-size: v.$text-xs;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  
  &:hover {
    background: var(--background-hover);
    border-color: var(--warning-color);
    color: var(--warning-color);
    transform: scale(1.05);
  }
  
  &.is-favorite {
    background: rgba(255, 165, 0, 0.1);
    border-color: var(--warning-color);
    color: var(--warning-color);
    
    &:hover {
      background: rgba(255, 165, 0, 0.2);
    }
  }
  
  .star-icon {
    flex-shrink: 0;
  }
  
  .button-label {
    @include m.respond-below('sm') {
      display: none; // Hide text on mobile, keep icon only
    }
  }
}

// ============================================================================
// LOADING & EMPTY STATES
// ============================================================================

.loading,
.no-categories {
  text-align: center;
  padding: v.$spacing-8 v.$spacing-4;
  
  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid var(--border-color);
    border-top-color: var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto v.$spacing-4;
  }
  
  p {
    color: var(--text-secondary);
    font-size: v.$text-base;
    line-height: 1.6;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

// ============================================================================
// TRANSITION ANIMATIONS
// ============================================================================

.category-cards-enter-active,
.category-cards-leave-active {
  transition: all v.$duration-300 v.$ease-out;
}

.category-cards-enter-from {
  opacity: 0;
  transform: scale(0.9);
}

.category-cards-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.category-cards-move {
  transition: transform v.$duration-300 v.$ease-out;
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .form-actions {
    flex-direction: column;
    
    .btn {
      width: 100%;
    }
  }
}
</style>
