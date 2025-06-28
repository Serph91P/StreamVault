import { ref, onMounted } from 'vue';
import type { FilenamePreset } from '@/types/recording';

interface FilenamePresetsResponse {
  status: string;
  data: FilenamePreset[];
}

export function useFilenamePresets() {
  const presets = ref<FilenamePreset[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

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
        presets.value = data.data;
      } else {
        throw new Error('Failed to load filename presets');
      }
    } catch (err) {
      console.error('Error loading filename presets:', err);
      error.value = err instanceof Error ? err.message : 'Unknown error';
      
      // Fallback to static presets if API fails
      const { FILENAME_PRESETS } = await import('@/types/recording');
      presets.value = FILENAME_PRESETS;
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
