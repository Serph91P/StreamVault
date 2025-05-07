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
        
        <div 
          v-for="category in filteredCategories" 
          :key="category.id" 
          class="category-card"
          :class="{ 'is-favorite': category.is_favorite }"
        >
          <div class="category-image">
            <img 
              :src="category.box_art_url ?? ''" 
              :alt="category.name"
              @error="setDefaultImage($event)"
            />
          </div>
          <div class="category-details">
            <h4 class="category-title">{{ category.name }}</h4>
            <div class="category-actions">
              <button 
                v-if="!category.is_favorite" 
                @click="addFavorite(category.id)"
                class="btn btn-sm btn-outline-primary favorite-btn"
              >
                Mark as Favorite
              </button>
              <button 
                v-else 
                @click="removeFavorite(category.id)"
                class="btn btn-sm btn-outline-danger favorite-btn"
              >
                Remove Favorite
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Category } from '@/types/settings'

// State
const categories = ref<Category[]>([])
const isLoading = ref(true)
const searchQuery = ref('')
const showFavoritesOnly = ref(false)
const error = ref<string | null>(null)

// Computed
const filteredCategories = computed(() => {
  let result = categories.value

  // Filter nach Favoriten, falls aktiviert
  if (showFavoritesOnly.value) {
    result = result.filter(cat => cat.is_favorite)
  }

  // Filter nach Suchtext
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase().trim()
    result = result.filter(cat => 
      cat.name.toLowerCase().includes(query)
    )
  }

  return result
})

// Methoden
const fetchCategories = async () => {
  try {
    isLoading.value = true;
    error.value = null;
    console.log("Fetching categories...");
    
    const response = await fetch('/api/categories');
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`HTTP error! status: ${response.status}, details: ${errorText}`);
      error.value = `Fehler beim Laden: ${response.status}`;
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log("Categories fetched:", data);
    categories.value = data.categories || [];
    
    if (categories.value.length === 0) {
      console.log("No categories found in the response");
    }
  } catch (error) {
    console.error('Error fetching categories:', error);
  } finally {
    isLoading.value = false;
  }
};

const addFavorite = async (categoryId: number) => {
  try {
    const response = await fetch('/api/categories/favorites', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ category_id: categoryId }),
    })
    
    if (!response.ok) {
      throw new Error('Failed to add favorite')
    }
    
    const updatedCategory = await response.json()
    
    // Update local state
    const index = categories.value.findIndex(cat => cat.id === categoryId)
    if (index !== -1) {
      categories.value[index].is_favorite = true
    }
  } catch (error) {
    console.error('Error adding favorite:', error)
  }
}

const removeFavorite = async (categoryId: number) => {
  try {
    const response = await fetch(`/api/categories/favorites/${categoryId}`, {
      method: 'DELETE',
    })
    
    if (!response.ok) {
      throw new Error('Failed to remove favorite')
    }
    
    // Update local state
    const index = categories.value.findIndex(cat => cat.id === categoryId)
    if (index !== -1) {
      categories.value[index].is_favorite = false
    }
  } catch (error) {
    console.error('Error removing favorite:', error)
  }
}

const setDefaultImage = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = '/assets/default-game-box.png'
}

// Lifecycle
onMounted(() => {
  fetchCategories()
})
</script>

<style scoped>
.filter-container {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.search-box {
  flex: 1;
  max-width: 300px;
}

@media (max-width: 768px) {
  .filter-container {
    flex-direction: column;
  }
  
  .search-box {
    max-width: 100%;
    margin-bottom: var(--spacing-sm);
  }
  
  .filter-buttons {
    display: flex;
    gap: var(--spacing-sm);
    width: 100%;
  }
  
  .filter-buttons button {
    flex: 1;
  }
}

.filter-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

/* Optimized grid with more appropriate columns and better responsiveness */
.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-lg);
  margin-top: var(--spacing-lg);
}

@media (min-width: 576px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}

@media (min-width: 992px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}

@media (min-width: 1400px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  }
}

/* Improved category card styling */
.category-card {
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  overflow: hidden;
  transition: all 0.3s var(--vue-ease);
  border: 1px solid var(--border-color);
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.category-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-md);
  border-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.4);
}

.category-card.is-favorite {
  border: 2px solid var(--primary-color);
}

.category-card.is-favorite::after {
  content: "★";
  position: absolute;
  top: 10px;
  right: 10px;
  color: var(--primary-color);
  font-size: 1.25rem;
  filter: drop-shadow(0 0 2px rgba(0,0,0,0.5));
}

/* Optimized image container for Twitch's 285x380 box art */
.category-image {
  width: 100%;
  height: 0;
  padding-bottom: 133.33%; /* Maintains 3:4 aspect ratio (285:380) */
  position: relative;
  overflow: hidden;
}

.category-image img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.category-card:hover .category-image img {
  transform: scale(1.05);
}

.category-details {
  padding: var(--spacing-md);
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.category-title {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 1rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  height: 2.5rem;
}

.category-actions {
  margin-top: auto;
  padding-top: var(--spacing-md);
  width: 100%;
}

.favorite-btn {
  width: 100%;
  padding: 0.4rem 0.75rem;
  white-space: nowrap;
}

.loading, .no-categories {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
  text-align: center;
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  min-height: 200px;
}

.loading .spinner {
  margin-bottom: var(--spacing-md);
}

.error-message {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.2);
  color: var(--danger-color);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  margin-bottom: var(--spacing-md);
  text-align: center;
}

.btn-outline-primary {
  background: transparent;
  border: 1px solid var(--primary-color);
  color: var(--primary-color);
  transition: all 0.2s var(--vue-ease);
}

.btn-outline-primary:hover {
  background-color: var(--primary-color);
  color: white;
}

.btn-outline-danger {
  background: transparent;
  border: 1px solid var(--danger-color);
  color: var(--danger-color);
  transition: all 0.2s var(--vue-ease);
}

.btn-outline-danger:hover {
  background-color: var(--danger-color);
  color: white;
}
</style>
