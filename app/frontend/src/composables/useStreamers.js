import { ref } from 'vue';
export function useStreamers() {
    const streamers = ref([]);
    const isLoading = ref(false);
    const updateStreamer = async (streamerId, updateData) => {
        const index = streamers.value.findIndex(s => s.id === streamerId);
        if (index !== -1) {
            streamers.value[index] = {
                ...streamers.value[index],
                ...updateData
            };
        }
        else {
            console.warn('useStreamers: Streamer not found:', streamerId);
        }
    };
    const fetchStreamers = async () => {
        isLoading.value = true;
        try {
            const response = await fetch('/api/streamers');
            if (!response.ok)
                throw new Error('Failed to fetch streamers');
            const data = await response.json();
            streamers.value = data.streamers || [];
        }
        catch (error) {
            console.error('Error fetching streamers:', error);
        }
        finally {
            isLoading.value = false;
        }
    };
    const deleteStreamer = async (streamerId) => {
        const response = await fetch(`/api/streamers/${streamerId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            streamers.value = streamers.value.filter(s => s.id !== streamerId);
            return true;
        }
        return false;
    };
    return {
        streamers,
        isLoading,
        updateStreamer,
        fetchStreamers,
        deleteStreamer
    };
}
