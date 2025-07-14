import { ref } from 'vue';
export function useNotificationSettings() {
    const settings = ref(null);
    const streamerSettings = ref([]);
    const fetchSettings = async () => {
        try {
            const response = await fetch('/api/settings');
            if (!response.ok)
                throw new Error(`HTTP error! status: ${response.status}`);
            settings.value = await response.json();
        }
        catch (error) {
            console.error('Failed to fetch settings:', error);
        }
    };
    const updateSettings = async (newSettings) => {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update settings');
        }
        settings.value = await response.json();
    };
    const getStreamerSettings = async () => {
        try {
            const response = await fetch('/api/settings/streamer');
            if (!response.ok)
                throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            streamerSettings.value = data;
            return data;
        }
        catch (error) {
            console.error('Failed to fetch streamer settings:', error);
            return [];
        }
    };
    const updateStreamerSettings = async (streamerId, settings) => {
        const response = await fetch(`/api/settings/streamer/${streamerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            console.error("Error updating settings:", errorData);
            throw new Error(errorData?.detail || `Failed to update settings for streamer ${streamerId}`);
        }
        return await response.json();
    };
    return {
        settings,
        streamerSettings,
        fetchSettings,
        updateSettings,
        getStreamerSettings,
        updateStreamerSettings
    };
}
