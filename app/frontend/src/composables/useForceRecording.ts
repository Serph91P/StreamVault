import { ref } from 'vue'
import { recordingApi } from '@/services/api'

export function useForceRecording() {
  // Force Recording State
  const forceRecordingStreamerId = ref<number | null>(null)

  // Force Recording Method
  const forceStartRecording = async (streamerId: number, onSuccess?: (streamerId: number) => void) => {
    try {
      forceRecordingStreamerId.value = streamerId
      
      // First check if streamer is really live via Twitch API
      let isLive = false
      let apiCheckFailed = false
      
      try {
        const checkResponse = await recordingApi.checkStreamerLiveStatus(streamerId)
        isLive = checkResponse?.data?.is_live || false
      } catch (apiError) {
        // If API check fails, mark as failed but don't assume the stream is live
        // This prevents unnecessary recording attempts on definitely offline streams
        apiCheckFailed = true
        console.warn('Live status check failed, API may be temporarily unavailable:', apiError)
      }
      
      if (apiCheckFailed) {
        // When API check fails, let backend handle validation entirely
        // Don't make assumptions about live status
        console.warn('Cannot verify live status due to API failure, proceeding with backend validation')
      } else if (!isLive) {
        // Show user-friendly message but still proceed (backend will validate)
        console.warn('Streamer appears to be offline according to API, but continuing with force recording attempt')
        // Note: Backend will still validate and send appropriate notifications
      }
      
      const response = await recordingApi.forceStartRecording(streamerId)
      
      if (response?.data?.status === 'success') {
        // Success feedback will be sent via WebSocket from backend
        // Call success callback if provided (for local state updates)
        if (onSuccess) {
          onSuccess(streamerId)
        }
        return { success: true }
      }
      
      return { success: false }
    } catch (error: any) {
      console.error('Error force starting recording:', error)
      
      // Let the backend handle error notifications via WebSocket
      // Error messages will be sent as toast notifications
      // Don't show additional UI errors here to avoid double notifications
      return { success: false, error }
    } finally {
      forceRecordingStreamerId.value = null
    }
  }

  return {
    forceRecordingStreamerId,
    forceStartRecording
  }
}
