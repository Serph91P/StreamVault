"""Keep persisted Twitch bios intact through repository and HTTP responses."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_image_service, get_streamer_service
from app.database import get_db
from app.models import Streamer
from app.routes.streamers import router
from app.services.streamers.streamer_repository import StreamerRepository


@pytest.mark.parametrize("description", ["Channel bio with games & chat 🎮", "", None])
@pytest.mark.parametrize("is_live", [False, True])
def test_channel_description_survives_list_and_detail_responses(description, is_live):
    streamer = Streamer(
        id=42,
        twitch_id="4242",
        username="example-channel",
        description=description,
        is_live=is_live,
        title="Current stream title",
    )
    db = Mock()

    def query(model):
        result = Mock()
        result.filter.return_value = result
        result.order_by.return_value = result
        result.all.return_value = [streamer] if model is Streamer else []
        result.first.return_value = streamer if model is Streamer else None
        return result

    db.query.side_effect = query
    responses = StreamerRepository(db).get_all_streamers()
    assert len(responses) == 1
    # Verify the schema does not silently discard the persisted description.
    assert responses[0].model_dump().get("description") == description

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_streamer_service] = lambda: SimpleNamespace(
        get_streamers=AsyncMock(return_value=responses)
    )
    app.dependency_overrides[get_image_service] = lambda: SimpleNamespace(
        get_profile_image_url=lambda *_: None
    )

    with TestClient(app) as client:
        listing = client.get("/api/streamers")
        detail = client.get("/api/streamers/streamer/42")

    assert listing.status_code == detail.status_code == 200
    listed = listing.json()["streamers"][0]
    detailed = detail.json()
    assert "description" in listed
    assert listed["description"] == detailed["description"] == description
    expected_title = "Current stream title" if is_live else None
    assert listed["title"] == detailed["title"] == expected_title
