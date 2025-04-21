import { ref, Ref } from 'vue';
import type { 
  RecordingSettings, 
  StreamerRecordingSettings, 
  ActiveRecording 
} from '@/types/recording';

export function useRecordingSettings() {
  const settings: Ref<RecordingSettings | null> = ref(null);
  const streamerSettings: Ref<StreamerRecordingSettings[]> = ref([]);
  const activeRecordings: Ref<ActiveRecording[]> = ref([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const fetchSettings = async (): Promise<void> => {
    try {
      isLoading.value = true;
      error.value = null;
      
      const response = await fetch('/api/recording/settings');
      if (response.ok) {
        const data = await response.json();
        settings.value = {
          enabled: data.enabled,
          output_directory: data.output_directory,
          filename_template: data.filename_template,
          filename_preset: data.filename_preset,
          default_quality: data.default_quality,
          use_chapters: data.use_chapters,
          use_category_as_chapter_title: data.use_category_as_chapter_title
        };
      } else {
        error.value = 'Failed to load settings';
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      isLoading.value = false;
    }
  };

  const updateSettings = async (newSettings: RecordingSettings): Promise<void> => {
    try {
      isLoading.value = true;
      error.value = null;
      
      const response = await fetch('/api/recording/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          enabled: newSettings.enabled,
          output_directory: newSettings.output_directory,
          filename_template: newSettings.filename_template,
          filename_preset: newSettings.filename_preset,
          default_quality: newSettings.default_quality,
          use_chapters: newSettings.use_chapters,
          use_category_as_chapter_title: newSettings.use_category_as_chapter_title
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        settings.value = {
          enabled: data.enabled,
          output_directory: data.output_directory,
          filename_template: data.filename_template,
          filename_preset: data.filename_preset,
          default_quality: data.default_quality,
          use_chapters: data.use_chapters,
          use_category_as_chapter_title: data.use_category_as_chapter_title
        };
      } else {
        error.value = 'Failed to update settings';
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      isLoading.value = false;
    }
  };
  const fetchStreamerSettings = async (): Promise<StreamerRecordingSettings[]> => {
    try {
      isLoading.value = true;
      error.value = null;
      
      console.log("Fetching streamer recording settings...")
      const response = await fetch('/api/recording/streamers');
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Error response:", errorText);
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log("Received streamer settings:", data);
      streamerSettings.value = data;
      return data;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error';
      console.error('Error fetching streamer recording settings:', err);
      return [];
    } finally {
      isLoading.value = false;
    }
  };

  const updateStreamerSettings = async (
    streamerId: number, 
    newSettings: Partial<StreamerRecordingSettings>
  ): Promise<StreamerRecordingSettings> => {
    try {
      isLoading.value = true;
      error.value = null;
      
      const response = await fetch(`/api/recording/streamers/${streamerId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          streamer_id: streamerId,
          ...newSettings
        })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
      }
      
      const updatedSettings = await response.json();
      
      // Update local state
      const index = streamerSettings.value.findIndex(s => s.streamer_id === streamerId);
      if (index !== -1) {
        streamerSettings.value[index] = updatedSettings;
      }
      
      return updatedSettings;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error';
      throw err;
    } finally {
      isLoading.value = false;
    }
  };

  const fetchActiveRecordings = async (): Promise<void> => {
    try {
      const response = await fetch('/api/recording/active');
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      activeRecordings.value = await response.json();
    } catch (err) {
      console.error('Error fetching active recordings:', err);
    }
  };

  const stopRecording = async (streamerId: number): Promise<boolean> => {
    try {
      isLoading.value = true;
      
      const response = await fetch(`/api/recording/stop/${streamerId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      await fetchActiveRecordings();
      return true;
    } catch (err) {
      console.error('Error stopping recording:', err);
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  const testRecording = async (streamerId: number): Promise<boolean> => {
    try {
      isLoading.value = true;
      
      const response = await fetch(`/api/recording/test/${streamerId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      await fetchActiveRecordings();
      return true;
    } catch (err) {
      console.error('Error testing recording:', err);
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    settings,
    streamerSettings,
    activeRecordings,
    isLoading,
    error,
    fetchSettings,
    updateSettings,
    fetchStreamerSettings,
    updateStreamerSettings,
    fetchActiveRecordings,
    stopRecording,
    testRecording
  }
}