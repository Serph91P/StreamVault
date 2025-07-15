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
            console.log('🔌 WebSocket already connected, skipping...');
            return;
        }
        // Clean up existing connection
        if (ws) {
            ws.close();
        }
        ws = new WebSocket(wsUrl);
        ws.onopen = () => {
            connectionStatus.value = 'connected';
            console.log('WebSocket connected');
        };
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('🔌 WebSocket raw message received:', event.data);
                console.log('🔌 WebSocket parsed message:', data);
                // Special handling for connection status messages
                if (data?.type === 'connection.status') {
                    // Only update status, don't create notification
                    console.log('⚡ WebSocket connection status message received, updating status only');
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
                        console.log('🔄 Duplicate message detected, ignoring:', data.type);
                        return;
                    }
                    console.log('✅ Message type accepted:', data.type);
                    console.log('📨 Adding message to messages array:', data);
                    console.log('📊 Messages array before push:', messages.value.length);
                    // Ensure test_id is present for test notifications
                    if (data.type === 'channel.update' && data.data?.username === 'TestUser' && !data.data.test_id) {
                        data.data.test_id = `test_${Date.now()}`;
                    }
                    // Create a new array reference to trigger reactivity
                    const newMessages = [...messages.value, data];
                    messages.value = newMessages;
                    console.log('📊 Messages array after push:', messages.value.length);
                    console.log('📋 Current messages array:', messages.value);
                    console.log('🎯 Latest message:', messages.value[messages.value.length - 1]);
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
            console.log('WebSocket disconnected, attempting reconnect...');
            // Clear existing timer
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            // Use exponential backoff for reconnection attempts
            const backoffDelay = Math.min(5000 * Math.pow(1.5, Math.floor(Math.random() * 3)), 30000);
            console.log(`WebSocket will attempt reconnection in ${backoffDelay / 1000} seconds`);
            // Only reconnect if we're not unmounting
            reconnectTimer = window.setTimeout(() => {
                if (connectionStatus.value === 'disconnected') {
                    console.log('WebSocket attempting reconnection now');
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
