<template>
  <div>
    <h3>Favorite Categories</h3>
    
    <!-- Filter und Suche -->
    <div class="filter-container">
      <div class="search-box">
        <input 
          v-model="searchQuery" 
          placeholder="Search for game..." 
          class="form-control"
        />
      </div>
      <div class="filter-buttons">
        <button 
          @click="showFavoritesOnly = !showFavoritesOnly" 
          class="btn" 
          :class="{ 'btn-primary': showFavoritesOnly, 'btn-secondary': !showFavoritesOnly }"
        >
          {{ showFavoritesOnly ? 'Show All' : 'Favorites Only' }}
        </button>
        <button @click="fetchCategories" class="btn btn-secondary">
          Refresh Categories
        </button>
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
        <div v-else class="category-cards">
          <div 
            v-for="category in filteredCategories" 
            :key="category.id"
            class="category-card"
            :class="{ 'is-favorite': category.is_favorite }"
          >
            <div class="category-image-wrapper">
              <img 
                v-if="category.box_art_url" 
                :src="formatImageUrl(category.box_art_url, 144, 192)" 
                alt="Game box art"
                class="category-image"
                loading="lazy"
              />
              <div v-else class="category-image-placeholder">
                <span>No image</span>
              </div>
            </div>
            <div class="category-content">
              <h4 class="category-name">{{ category.name }}</h4>
              <div class="category-meta">
                <span>{{ category.stream_count || 0 }} recorded streams</span>
              </div>
              <div class="category-actions">
                <button 
                  @click="toggleFavorite(category)"
                  class="btn-icon"
                  :title="category.is_favorite ? 'Remove from favorites' : 'Add to favorites'"
                >
                  <svg viewBox="0 0 24 24" width="18" height="18" class="star-icon">
                    <path 
                      :fill="category.is_favorite ? '#FFD700' : 'currentColor'" 
                      d="M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z"
                    />
                  </svg>
                  {{ category.is_favorite ? 'Unfavorite' : 'Favorite' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

interface Category {
  id: string;
  name: string;
  box_art_url: string | null;
  is_favorite: boolean;
  stream_count?: number;
}

// State variables
const searchQuery = ref('');
const showFavoritesOnly = ref(false);
const categories = ref<Category[]>([]);
const isLoading = ref(true);
const error = ref<string | null>(null);

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
    categories.value = data;
  } catch (err: any) {
    error.value = err.message || 'An error occurred while fetching categories';
    console.error('Error fetching categories:', err);
  } finally {
    isLoading.value = false;
  }
};

const toggleFavorite = async (category: Category) => {
  try {
    const response = await fetch(`/api/categories/${category.id}/favorite`, {
      method: category.is_favorite ? 'DELETE' : 'PUT',
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

const formatImageUrl = (url: string, width: number, height: number): string => {
  return url
    .replace('{width}', width.toString())
    .replace('{height}', height.toString());
};

// Initialize component
onMounted(() => {
  fetchCategories();
});
</script>

<style scoped>
.filter-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background-color: var(--background-darker, #18181b);
  border-radius: var(--border-radius, 6px);
  border: 1px solid var(--border-color, #2a2a2d);
}

@media (min-width: 768px) {
  .filter-container {
    flex-direction: row;
    align-items: center;
  }
  
  .search-box {
    flex: 1;
  }
}

.filter-buttons {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.categories-grid {
  position: relative;
  min-height: 200px;
}

.loading, .no-categories {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-secondary, #9e9e9e);
  background-color: var(--background-darker, #18181b);
  border-radius: var(--border-radius, 6px);
  min-height: 200px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
  border-top-color: var(--primary-color, #42b883);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-md);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-message {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  color: var(--danger-color, #ef4444);
  padding: var(--spacing-md);
  border-radius: var(--border-radius, 6px);
  margin-bottom: var(--spacing-md);
}

/* Category grid with improved responsiveness */
.category-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--spacing-md);
}

/* Small screens: 1-2 cards per row */
@media (min-width: 480px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}

/* Medium screens: 3-4 cards per row */
@media (min-width: 768px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
}

/* Large screens: 5-6 cards per row */
@media (min-width: 1200px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}

/* Extra large screens */
@media (min-width: 1600px) {
  .category-cards {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
}

.category-card {
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 6px);
  overflow: hidden;
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.1));
  transition: all 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
  border: 1px solid var(--border-color, #2a2a2d);
  display: flex;
  flex-direction: column;
}

.category-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md, 0 4px 6px rgba(0, 0, 0, 0.1));
  border-color: var(--primary-color-muted, rgba(66, 184, 131, 0.5));
}

.category-card.is-favorite {
  border-color: rgba(255, 215, 0, 0.5);
}

.category-image-wrapper {
  width: 100%;
  aspect-ratio: 3/4;
  background-color: var(--background-darker);
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
  background-color: var(--background-darker);
  color: var(--text-secondary);
}

.category-content {
  padding: var(--spacing-sm);
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
  -webkit-box-orient: vertical;
}

.category-meta {
  font-size: 0.8rem;
  color: var(--text-secondary, #9e9e9e);
  margin: var(--spacing-xs) 0;
}

.category-actions {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  padding-top: var(--spacing-sm);
}

.btn-icon {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.8rem;
  background-color: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm, 4px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon:hover {
  background-color: var(--background-darker);
  color: var(--text-primary);
}

.category-card.is-favorite .btn-icon {
  color: #FFD700;
  border-color: rgba(255, 215, 0, 0.5);
}

.star-icon {
  transition: transform 0.2s ease;
}

.btn-icon:hover .star-icon {
  transform: scale(1.2);
}
</style>
