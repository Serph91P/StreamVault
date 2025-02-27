<template>
  <div>
    <h3>Favoriten-Kategorien</h3>
    
    <!-- Filter und Suche -->
    <div class="filter-container">
      <div class="search-box">
        <input 
          v-model="searchQuery" 
          placeholder="Spiel suchen..." 
          class="form-control"
          @input="filterCategories"
        />
      </div>
      <div class="filter-buttons">
        <button 
          @click="showFavoritesOnly = !showFavoritesOnly" 
          class="btn" 
          :class="{ 'btn-primary': showFavoritesOnly, 'btn-secondary': !showFavoritesOnly }"
        >
          {{ showFavoritesOnly ? 'Alle anzeigen' : 'Nur Favoriten' }}
        </button>
      </div>
    </div>
    
    <!-- Kategorie-Liste -->
    <div class="categories-grid">
      <div v-if="isLoading" class="loading">
        Lade Kategorien...
      </div>
      <template v-else>
        <div v-if="filteredCategories.length === 0" class="no-categories">
          <p v-if="showFavoritesOnly">Du hast noch keine Kategorien als Favorit markiert.</p>
          <p v-else-if="searchQuery">Keine Kategorien gefunden, die "{{ searchQuery }}" enthalten.</p>
          <p v-else>Keine Kategorien gefunden. Wenn Streamer neue Kategorien verwenden, werden sie hier angezeigt.</p>
        </div>
        
        <div 
          v-for="category in filteredCategories" 
          :key="category.id" 
          class="category-card"
          :class="{ 'is-favorite': category.is_favorite }"
        >
          <div class="category-image">
            <img 
              :src="category.box_art_url" 
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
                Als Favorit markieren
              </button>
              <button 
                v-else 
                @click="removeFavorite(category.id)"
                class="btn btn-sm btn-outline-danger"
              >
                Favorit entfernen
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

interface Category {
  id: number
  twitch_id: string
  name: string
  box_art_url: string | null
  is_favorite: boolean
  first_seen: string
  last_seen: string
}

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
    isLoading.value = true
    const response = await fetch('/api/categories')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    categories.value = data.categories
  } catch (error) {
    console.error('Error fetching categories:', error)
  } finally {
    isLoading.value = false
  }
}

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
