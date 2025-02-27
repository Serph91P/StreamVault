<template>
  <div class="categories-container">
    <h2 class="categories-title">Spiele/Kategorien</h2>
    
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
    </div
