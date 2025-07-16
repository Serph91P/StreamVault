import { ref, onMounted, onUnmounted } from 'vue';
export function useWebSocket() {
    const messages = ref([]);
    const connectionStatus = ref('disconnected');
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    let ws = null;
    let reconnectTimer = null;
    const connect = () => {
        // Prevent multiple connections
        if (ws && ws.readyState === WebSocket.OPEN) {
            return;
        }
        // Clean up existing connection
        if (ws) {
            ws.close();
        }
        ws = new WebSocket(wsUrl);
        ws.onopen = () => {
            connectionStatus.value = 'connected';
        };
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Special handling for connection status messages
                if (data?.type === 'connection.status') {
                    // Only update status, don't create notification
                    connectionStatus.value = data?.data?.status || 'connected';
                    return;
                }
                // Process all other notification types
                if (data && data.type) {
                    // Check if this is a duplicate message (by comparing with the last message)
                    const isDuplicate = messages.value.length > 0 &&
                        data.type === messages.value[messages.value.length - 1].type &&
                        JSON.stringify(data.data) === JSON.stringify(messages.value[messages.value.length - 1].data);
                    if (isDuplicate) {
                        return;
                    }
                    // Ensure test_id is present for test notifications
                    if (data.type === 'channel.update' && data.data?.username === 'TestUser' && !data.data.test_id) {
                        data.data.test_id = `test_${Date.now()}`;
                    }
                    // Create a new array reference to trigger reactivity
                    const newMessages = [...messages.value, data];
                    messages.value = newMessages;
                }
                else {
                    console.warn('❌ Message type not recognized or data invalid:', data?.type, 'Full data:', data);
                }
            }
            catch (e) {
                console.error('💥 Error parsing WebSocket message:', e);
            }
        };
        ws.onclose = (event) => {
            connectionStatus.value = 'disconnected';
            console.log('WebSocket disconnected with code:', event.code, 'reason:', event.reason);
            // Clear existing timer
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            // Use exponential backoff for reconnection attempts
            const backoffDelay = Math.min(5000 * Math.pow(1.5, Math.floor(Math.random() * 3)), 30000);
            // Only reconnect if we're not unmounting
            reconnectTimer = window.setTimeout(() => {
                if (connectionStatus.value === 'disconnected') {
                    connect();
                }
            }, backoffDelay);
        };
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    };
    onMounted(() => {
        connect();
    });
    onUnmounted(() => {
        connectionStatus.value = 'disconnected';
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        if (ws) {
            ws.close();
            ws = null;
        }
    });
    return {
        messages,
        connectionStatus
    };
}
