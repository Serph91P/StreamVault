import { ref, Ref } from 'vue';
import type { 
  RecordingSettings, 
  StreamerRecordingSettings, 
  ActiveRecording,
  CleanupPolicy
} from '@/types/recording';
import { CleanupPolicyType } from '@/types/recording';

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
          use_category_as_chapter_title: data.use_category_as_chapter_title,
          cleanup_policy: data.cleanup_policy // Add cleanup policy
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
          use_category_as_chapter_title: newSettings.use_category_as_chapter_title,
          cleanup_policy: newSettings.cleanup_policy // Add new cleanup policy field
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
          use_category_as_chapter_title: data.use_category_as_chapter_title,
          cleanup_policy: data.cleanup_policy // Include cleanup policy in response
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
      const index = streamerSettings.value.findIndex((s: StreamerRecordingSettings) => s.streamer_id === streamerId);
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

  const fetchActiveRecordings = async () => {
    try {
      isLoading.value = true;
      const response = await fetch('/api/recording/active');
      
      if (!response.ok) {
        throw new Error(`Failed to fetch active recordings: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Fetched active recordings:', data);
      
      // Ensure we validate and normalize the response
      if (Array.isArray(data)) {
        activeRecordings.value = data.map(rec => ({
          ...rec,
          streamer_id: parseInt(rec.streamer_id.toString()) // Ensure consistent type
        }));
      } else {
        console.error('Invalid active recordings response:', data);
        activeRecordings.value = [];
      }
    } catch (err: unknown) {
      console.error('Error fetching active recordings:', err);
      error.value = err instanceof Error ? err.message : String(err);
      activeRecordings.value = []; // Reset on error
    } finally {
      isLoading.value = false;
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

  const cleanupOldRecordings = async (streamerId: number): Promise<boolean> => {
    try {
      isLoading.value = true;
      
      const response = await fetch(`/api/recording/cleanup/${streamerId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error(`Failed to cleanup old recordings: ${response.statusText}`);
      }
      
      const data = await response.json();
      return true;
    } catch (err) {
      console.error('Error cleaning up recordings:', err);
      error.value = err instanceof Error ? err.message : String(err);
      return false;
    } finally {
      isLoading.value = false;
    }
  };  // New functions for advanced cleanup policies
  const getDefaultCleanupPolicy = (): CleanupPolicy => {
    return {
      type: CleanupPolicyType.COUNT,
      threshold: 10,
      preserve_favorites: true,
      preserve_categories: [],
      delete_silently: false
    };
  };

  const updateCleanupPolicy = async (policy: CleanupPolicy): Promise<boolean> => {
    try {
      isLoading.value = true;
      
      if (!settings.value) {
        await fetchSettings();
      }
      
      if (settings.value) {
        const updatedSettings = { ...settings.value, cleanup_policy: policy };
        await updateSettings(updatedSettings);
        return true;
      }
      
      return false;
    } catch (err) {
      console.error('Error updating cleanup policy:', err);
      error.value = err instanceof Error ? err.message : String(err);
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  const updateStreamerCleanupPolicy = async (
    streamerId: number, 
    policy: CleanupPolicy
  ): Promise<boolean> => {
    try {
      isLoading.value = true;
      
      const response = await fetch(`/api/recording/streamers/${streamerId}/cleanup-policy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(policy)
      });
      
      if (!response.ok) {
        throw new Error('Failed to update streamer cleanup policy');
      }
      
      // Update local cache
      await fetchStreamerSettings();
      
      return true;
    } catch (err) {
      console.error('Error updating streamer cleanup policy:', err);
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  const runCustomCleanup = async (
    streamerId: number,
    customPolicy?: CleanupPolicy
  ): Promise<{ deletedCount: number, deletedPaths: string[] }> => {
    try {
      isLoading.value = true;
      
      const url = customPolicy 
        ? `/api/recording/cleanup/${streamerId}/custom` 
        : `/api/recording/cleanup/${streamerId}`;
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: customPolicy ? JSON.stringify(customPolicy) : undefined
      });
      
      if (!response.ok) {
        throw new Error(`Failed to run cleanup: ${response.statusText}`);
      }
      
      const data = await response.json();
      return {
        deletedCount: data.deleted_count || 0,
        deletedPaths: data.deleted_paths || []
      };
    } catch (err) {
      console.error('Error running custom cleanup:', err);
      error.value = err instanceof Error ? err.message : String(err);
      return { deletedCount: 0, deletedPaths: [] };
    } finally {
      isLoading.value = false;
    }
  };

  const getStreamerStorageUsage = async (streamerId: number): Promise<{ 
    totalSize: number, 
    recordingCount: number,
    oldestRecording: string,
    newestRecording: string 
  }> => {
    try {
      isLoading.value = true;
      
      const response = await fetch(`/api/recording/storage/${streamerId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to get storage usage: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (err) {
      console.error('Error getting streamer storage usage:', err);
      error.value = err instanceof Error ? err.message : String(err);
      return { 
        totalSize: 0, 
        recordingCount: 0,
        oldestRecording: '',
        newestRecording: ''
      };
    } finally {
      isLoading.value = false;
    }
  };

  const getAvailableCategories = async (): Promise<{id: number; name: string}[]> => {
    try {
      const response = await fetch('/api/categories');
      if (!response.ok) {
        throw new Error('Failed to fetch categories');
      }
      const data = await response.json();
      
      // Extract the id and name from each category 
      return data.categories.map((category: any) => ({
        id: category.id,
        name: category.name
      }));
    } catch (err) {
      console.error('Error fetching categories:', err);
      return [];
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
    cleanupOldRecordings,
    getDefaultCleanupPolicy,
    updateCleanupPolicy,
    updateStreamerCleanupPolicy,
    runCustomCleanup,
    getStreamerStorageUsage,
    getAvailableCategories
  }
}