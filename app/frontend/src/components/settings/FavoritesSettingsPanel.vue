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
    
    <!-- Kategorie-Liste -->
    <div class="categories-grid">
      <div v-if="isLoading" class="loading">
        Lade Kategorien...
      </div>
      <template v-else>
        <div v-if="filteredCategories.length === 0" class="no-categories">
          <p v-if="showFavoritesOnly">You haven't marked any categories as favorites yet.</p>
          <p v-else-if="searchQuery">No categories found containing "{{ searchQuery }}".</p>
          <p v-else>No categories found. When streamers use new categories, they will appear here.</p>
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
    console.log("Fetching categories...");
    const response = await fetch('/api/categories');
    
    if (!response.ok) {
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
  margin-bottom: 20px;
}

.search-box {
  flex: 1;
  max-width: 300px;
}

.filter-buttons {
  display: flex;
  gap: 10px;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.category-card {
  background-color: #1f1f23;
  border-radius: 8px;
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.category-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.category-card.is-favorite {
  border: 2px solid #9146FF;
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
  padding: 15px;
}

.category-details h4 {
  margin: 0 0 10px 0;
  font-size: 1rem;
}

.category-actions {
  margin-top: 10px;
}

.loading, .no-categories {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  color: #aaa;
  text-align: center;
}
</style>
