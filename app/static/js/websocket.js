class StreamerWebSocket {
    constructor(streamerUsername) {
        this.connect(streamerUsername);
    }

    connect(streamerUsername) {
        this.ws = new WebSocket(`ws://${window.location.host}/ws/${streamerUsername}`);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleUpdate(data);
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connect(streamerUsername), 1000);
        };
    }

    handleUpdate(data) {
        if (data.type === 'streamer_update') {
            const streamerData = data.data;
            document.getElementById('stream-status').textContent = 
                streamerData.is_live ? 'Live' : 'Offline';
            document.getElementById('stream-title').textContent = 
                streamerData.stream_title;
            document.getElementById('game-name').textContent = 
                streamerData.game_name;
        }
    }
}
