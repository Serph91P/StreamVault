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
        Lade Kategorien...
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
            <h4>{{ category.name }}</h4>
            <div class="category-actions">
              <button 
                v-if="!category.is_favorite" 
                @click="addFavorite(category.id)"
                class="btn btn-sm btn-outline-primary"
              >
                Mark as Favorite
              </button>
              <button 
                v-else 
                @click="removeFavorite(category.id)"
                class="btn btn-sm btn-outline-danger"
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

.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

@media (min-width: 768px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}

@media (min-width: 1200px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
}

.category-card {
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid var(--border-color);
}

.category-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.category-card.is-favorite {
  border: 2px solid var(--primary-color);
}

.category-image {
  height: 180px;
  overflow: hidden;
}

.category-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-details {
  padding: var(--spacing-md);
}

.category-details h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.category-actions {
  margin-top: var(--spacing-sm);
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
}

.btn-outline-primary:hover {
  background-color: var(--primary-color);
  color: white;
}

.btn-outline-danger {
  background: transparent;
  border: 1px solid var(--danger-color);
  color: var(--danger-color);
}

.btn-outline-danger:hover {
  background-color: var(--danger-color);
  color: white;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}
</style>
