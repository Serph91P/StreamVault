import { ref, onMounted, computed } from 'vue';
import type { FilenamePreset } from '@/types/recording';
import { FILENAME_PRESETS as STATIC_FILENAME_PRESETS } from '@/types/recording';

interface FilenamePresetsResponse {
  status: string;
  data: FilenamePreset[];
}

export function useFilenamePresets() {
  const presetsRef = ref<FilenamePreset[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  // Computed property that returns the actual array value
  const presets = computed(() => presetsRef.value);

  const loadPresets = async () => {
    isLoading.value = true;
    error.value = null;
    
    try {
      const response = await fetch('/api/recording/filename-presets');
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: FilenamePresetsResponse = await response.json();
      
      if (data.status === 'success') {
        presetsRef.value = data.data;
      } else {
        throw new Error('Failed to load filename presets');
      }
    } catch (err) {
      console.error('Error loading filename presets:', err);
      error.value = err instanceof Error ? err.message : 'Unknown error';
      
      // Fallback to static presets if API fails
      presetsRef.value = [...STATIC_FILENAME_PRESETS];
    } finally {
      isLoading.value = false;
    }
  };

  onMounted(() => {
    loadPresets();
  });

  return {
    presets,
    isLoading,
    error,
    loadPresets
  };
}
