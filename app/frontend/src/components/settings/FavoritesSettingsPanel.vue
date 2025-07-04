<template>
  <div>
    <h3>Favorite Categories</h3>
    
    <!-- Filter und Suche - Verbessert für Mobile -->
    <div class="filter-container">
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
      <div v-if="isLoading" class="loading">
        <div class="spinner"></div>
        <p>Loading categories...</p>
      </div>
      <template v-else>
        <div v-if="filteredCategories.length === 0" class="no-categories">
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
                      :fill="category.is_favorite ? '#FFD700' : 'currentColor'" 
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
import { ref, computed, onMounted, watch } from 'vue';
import { useCategoryImages } from '@/composables/useCategoryImages';

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
const { getCategoryImage, preloadCategoryImages } = useCategoryImages();

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
  
  console.log(`Filtered categories: ${result.length}`); // Debug log
  return result;
});

// Methods
const fetchCategories = async () => {
  isLoading.value = true;
  error.value = null;
  
  try {
    console.log('Fetching categories...');
    const response = await fetch('/api/categories');
    if (!response.ok) {
      throw new Error('Failed to fetch categories');
    }
    
    const data = await response.json();
    
    // Wichtig: Die API gibt die Kategorien in einem "categories"-Feld zurück
    if (data.categories && Array.isArray(data.categories)) {
      console.log(`Received ${data.categories.length} categories from API`);
      categories.value = data.categories;
      
      // Preload category images for all categories
      const categoryNames = data.categories
        .map((cat: any) => cat.name)
        .filter((name: string | null): name is string => Boolean(name));
      
      if (categoryNames.length > 0) {
        preloadCategoryImages(categoryNames);
      }
    } else {
      console.error('Unexpected API response format:', data);
      throw new Error('Unexpected API response format');
    }
  } catch (err: any) {
    error.value = err.message || 'An error occurred while fetching categories';
    console.error('Error fetching categories:', err);
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
  } catch (err: any) {
    error.value = err.message;
    console.error('Error toggling favorite status:', err);
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

// Debug-Output
watch(categories, (newCategories) => {
  if (newCategories.length > 0) {
    console.log('First category example:', newCategories[0]);
  }
}, { immediate: true, deep: true });
</script>

<style scoped>
.filter-container {
  background-color: #18181b;
  border-radius: 6px;
  border: 1px solid #2a2a2d;
  margin-bottom: 24px;
  overflow: hidden;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
}

.search-box {
  flex: 1;
  min-width: 200px;
}

.filter-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Responsive Anpassungen */
@media (max-width: 640px) {
  .filter-row {
    flex-direction: column;
  }
  
  .search-box, .filter-buttons {
    width: 100%;
  }
  
  .filter-buttons {
    justify-content: space-between;
    margin-top: 8px;
  }
  
  .filter-buttons .btn {
    flex: 1;
    padding: 10px 8px;
  }
  
  .button-text {
    display: none; /* Nur Icons auf Mobilgeräten */
  }
  
  .button-icon {
    margin-right: 0;
    font-size: 1.2rem;
  }
}

@media (min-width: 641px) {
  .button-icon {
    margin-right: 6px;
  }
}

.categories-grid {
  width: 100%;
  display: block;
}

.loading, .no-categories {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  text-align: center;
  color: #9e9e9e;
  background-color: #18181b;
  border-radius: 6px;
  min-height: 200px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(66, 184, 131, 0.1);
  border-top-color: #42b883;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-message {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  padding: 16px;
  border-radius: 6px;
  margin-bottom: 16px;
}

/* Card transition animations */
.category-cards-enter-active,
.category-cards-leave-active {
  transition: all 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

.category-cards-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.category-cards-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.category-cards-move {
  transition: transform 0.5s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

/* Category grid with improved responsiveness - matched to StreamerList */
.category-cards {
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)) !important;
  gap: 20px;
  padding: 8px;
  width: 100%;
  min-height: 200px; /* Debug: ensure container has height */
}

/* Small screens: 1 card per row */
@media (max-width: 640px) {
  .category-cards {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

/* Medium screens: 2-3 cards per row */
@media (min-width: 641px) and (max-width: 1023px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 20px;
  }
}

/* Large screens: 3-4 cards per row */
@media (min-width: 1024px) and (max-width: 1439px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 24px;
  }
}

/* Extra large screens: 4+ cards per row */
@media (min-width: 1440px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 24px;
  }
}

.category-card {
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  overflow: hidden;
  transition: all 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color, #2d2d35);
  margin-bottom: 0;
  box-shadow: none;
}

.category-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  border-color: rgba(66, 184, 131, 0.5);
}

.category-card.is-favorite {
  border-color: rgba(255, 215, 0, 0.5);
  box-shadow: none;
}

.category-card.is-favorite:hover {
  box-shadow: 0 2px 8px rgba(255, 215, 0, 0.15);
}

/* Left border indicator with more subtle styling */
.category-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background-color: transparent;
  transition: background-color 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

.category-card:hover::before {
  background-color: var(--primary-color, #42b883);
}

.category-card.is-favorite::before {
  background-color: var(--highlight-color, #FFD700);
  animation: subtle-pulse 2s infinite;
}

@keyframes subtle-pulse {
  0% {
    opacity: 0.7;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.7;
  }
}

.category-image-wrapper {
  width: 100%;
  aspect-ratio: 3/4;
  background-color: #18181b;
  display: flex;
  justify-content: center;
  align-items: center;
}

.category-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #18181b;
  color: #9e9e9e;
}

.category-icon {
  font-size: 2rem;
  color: #9146FF;
  opacity: 0.7;
}

.category-image-placeholder .category-icon {
  font-size: 2.5rem;
}

.category-content {
  padding: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.category-name {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary, #efeff1);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.category-meta {
  font-size: 0.8rem;
  color: #9e9e9e;
  margin: 4px 0;
}

.category-actions {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--border-color, #2d2d35);
}

.category-stats {
  font-size: 0.75rem;
  color: var(--text-secondary, #9e9e9e);
}

.btn-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 0.8rem;
  background-color: transparent;
  color: #9e9e9e;
  border: 1px solid #2a2a2d;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon:hover {
  background-color: #18181b;
  color: #efeff1;
  transform: translateY(-1px);
}

.btn-icon.is-favorite {
  color: #FFD700;
  border-color: rgba(255, 215, 0, 0.5);
}

.star-icon {
  transition: transform 0.2s ease;
}

.btn-icon:hover .star-icon {
  transform: scale(1.2);
}

@media (max-width: 480px) {
  .button-label {
    display: none;
  }
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 0.875rem;
  line-height: 1.5;
}

.btn-primary {
  background-color: #42b883;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #3ca978;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(66, 184, 131, 0.25);
}

.btn-secondary {
  background-color: rgba(255, 255, 255, 0.1);
  color: #efeff1;
  border: 1px solid #2a2a2d;
}

.btn-secondary:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.form-control {
  width: 100%;
  box-sizing: border-box;
  background: #121214;
  border: 1px solid #2a2a2d;
  color: #efeff1;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.form-control:focus {
  border-color: #42b883;
  outline: none;
  box-shadow: 0 0 0 3px rgba(66, 184, 131, 0.1);
}
</style>
