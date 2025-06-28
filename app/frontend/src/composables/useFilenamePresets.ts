import { ref, onMounted, reactive } from 'vue';
import type { FilenamePreset } from '@/types/recording';
import { FILENAME_PRESETS as STATIC_FILENAME_PRESETS } from '@/types/recording';

interface FilenamePresetsResponse {
  status: string;
  data: FilenamePreset[];
}

export function useFilenamePresets() {
  const presets = reactive<FilenamePreset[]>([]);
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
        // Clear and populate the reactive array
        presets.splice(0, presets.length, ...data.data);
      } else {
        throw new Error('Failed to load filename presets');
      }
    } catch (err) {
      console.error('Error loading filename presets:', err);
      error.value = err instanceof Error ? err.message : 'Unknown error';
      
      // Fallback to static presets if API fails
      presets.splice(0, presets.length, ...STATIC_FILENAME_PRESETS);
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
