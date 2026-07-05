#!/usr/bin/env python3
"""
Tests for realtime WebSocket event replay support.
"""

import asyncio
from typing import cast

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.services.communication.websocket_manager import ConnectionManager


class _FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.client = "test-client"
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def test_replayable_events_receive_monotonic_ids_and_can_be_queried_since():
    async def run_test():
        manager = ConnectionManager(event_log_size=10)

        await manager.send_notification({"type": "streamer.added", "data": {"id": 1}})
        await manager.send_notification({"type": "streamer.removed", "data": {"id": 2}})

        first_batch = await manager.get_events_since(0)
        second_batch = await manager.get_events_since(1)
        replay_state = await manager.get_replay_state()

        assert [event["event_id"] for event in first_batch] == [1, 2]
        assert [event["event_id"] for event in second_batch] == [2]
        assert first_batch[0]["type"] == "streamer.added"
        assert first_batch[1]["data"] == {"id": 2}
        assert replay_state == {
            "latest_event_id": 2,
            "oldest_event_id": 1,
            "retained_events": 2,
            "max_retained_events": 10,
        }

    asyncio.run(run_test())


def test_live_notifications_include_the_replay_cursor():
    async def run_test():
        manager = ConnectionManager(event_log_size=10)
        websocket = _FakeWebSocket()
        manager.active_connections[id(websocket)] = cast(WebSocket, websocket)

        await manager.send_notification({"type": "streamer.added", "data": {"id": 1}})

        assert len(websocket.messages) == 1
        assert websocket.messages[0]["type"] == "streamer.added"
        assert websocket.messages[0]["data"] == {"id": 1}
        assert websocket.messages[0]["event_id"] == 1
        assert "timestamp" in websocket.messages[0]

    asyncio.run(run_test())


def test_replay_log_is_bounded_to_recent_events():
    async def run_test():
        manager = ConnectionManager(event_log_size=2)

        await manager.send_notification({"type": "event.one", "data": {}})
        await manager.send_notification({"type": "event.two", "data": {}})
        await manager.send_notification({"type": "event.three", "data": {}})

        events = await manager.get_events_since(0)
        replay_state = await manager.get_replay_state()

        assert [event["event_id"] for event in events] == [2, 3]
        assert replay_state["oldest_event_id"] == 2
        assert replay_state["latest_event_id"] == 3
        assert replay_state["retained_events"] == 2
        assert replay_state["max_retained_events"] == 2

    asyncio.run(run_test())


def test_connection_status_is_not_replayed():
    async def run_test():
        manager = ConnectionManager(event_log_size=10)

        await manager.send_notification({"type": "connection.status", "data": {}})

        assert await manager.get_events_since(0) == []
        assert await manager.get_replay_state() == {
            "latest_event_id": 0,
            "oldest_event_id": None,
            "retained_events": 0,
            "max_retained_events": 10,
        }

    asyncio.run(run_test())
