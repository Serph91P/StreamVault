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

/* Optimiertes Grid mit besserer Responsivität für Twitch-Kategorie-Karten */
.categories-grid {
  display: grid;
  /* Setze autofit für automatische Spalten-Berechnung und Responsivität */
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px; /* Kleinerer Abstand für mehr Karten pro Zeile */
  margin-top: var(--spacing-md);
}

/* Progressive bessere Größen für größere Bildschirme */
@media (min-width: 450px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  }
}

@media (min-width: 576px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }
}

@media (min-width: 768px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 16px;
  }
}

@media (min-width: 992px) {
  .categories-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }
}

@media (min-width: 1200px) {
  .categories-grid {
    gap: 20px;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  }
}

.category-card {
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  overflow: hidden;
  transition: transform 0.2s var(--vue-ease), box-shadow 0.2s var(--vue-ease), border-color 0.2s var(--vue-ease);
  border: 1px solid var(--border-color);
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.category-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.4);
}

.category-card.is-favorite {
  border: 2px solid var(--primary-color);
}

.category-card.is-favorite::after {
  content: "★";
  position: absolute;
  top: 4px;
  right: 4px;
  color: var(--primary-color);
  font-size: 1rem;
  filter: drop-shadow(0 0 2px rgba(0,0,0,0.5));
  z-index: 1;
}

/* Korrektes Bildverhältnis für Twitch-Kategorie-Box-Art (285:380 = 3:4) */
.category-image {
  width: 100%;
  height: 0;
  padding-bottom: 133.33%; /* Exaktes 3:4 Verhältnis (380/285 * 100) */
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
  padding: var(--spacing-xs);
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.category-title {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 0.85rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.2;
  height: 2rem;
}

.category-actions {
  margin-top: auto;
  padding-top: var(--spacing-xs);
  width: 100%;
}

.favorite-btn {
  width: 100%;
  padding: 0.3rem 0.4rem;
  white-space: nowrap;
  font-size: 0.75rem;
}

.loading, .no-categories {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--spacing-lg);
  color: var(--text-secondary);
  text-align: center;
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  min-height: 150px;
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

/* Verbesserte Button-Klassen für kleinere Karten */
.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
  line-height: 1.2;
}

/* Verbessertes Styling für kleine Bildschirme (unter 400px) */
@media (max-width: 400px) {
  .category-title {
    font-size: 0.8rem;
    height: 1.9rem;
  }
  
  .favorite-btn {
    padding: 0.25rem 0.3rem;
    font-size: 0.7rem;
  }
}
</style>
