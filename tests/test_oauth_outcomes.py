"""OAuth adapters retain public outcomes without leaking provider/import errors."""

from types import SimpleNamespace

import pytest

from app.services.api.twitch_oauth_service import TwitchOAuthService


@pytest.mark.asyncio
async def test_oauth_user_validation_errors_are_private_and_invalid_stays_absent(
    caplog,
):
    class API:
        async def validate_token(self, token):
            if token == "missing":
                return None
            raise ValueError("fixture-private-validation-material")

    service = TwitchOAuthService(twitch_api=API())
    try:
        assert await service.get_user_followed_channels("missing") is None
        assert await service.get_user_followed_channels("error") is None
        assert "fixture-private-validation-material" not in caplog.text
        assert service._supervisor.task_names == ()
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_oauth_import_outcomes_keep_input_identity_but_never_raw_internal_error(
    caplog,
):
    received = []

    class Importer:
        async def add_streamer(self, username, display_name):
            received.append((username, display_name))
            if username == "existing":
                return SimpleNamespace(id=0)
            if username == "absent":
                return None
            if username == "broken":
                raise RuntimeError("fixture-private-import-material")
            return SimpleNamespace(id=42)

    service = TwitchOAuthService(Importer())
    selection = [
        {"login": name, "display_name": name.title()}
        for name in ("new", "existing", "absent", "broken")
    ]
    selection.append({"unrelated": "fixture-private-input-material"})
    try:
        result = await service.import_followed_streamers(selection)
        assert result["imported"] == [
            {"username": "new", "display_name": "New", "id": 42}
        ]
        assert result["already_exists"] == [
            {"username": "existing", "display_name": "Existing"}
        ]
        assert result["failed"] == [
            {"streamer": selection[2], "reason": "Failed to add streamer"},
            {"streamer": selection[3], "reason": "Failed to add streamer"},
            {"streamer": selection[4], "reason": "Missing username"},
        ]
        assert received == [
            (name, name.title()) for name in ("new", "existing", "absent", "broken")
        ]
        assert "fixture-private-import-material" not in str(result)
        assert "fixture-private-import-material" not in caplog.text
        assert "fixture-private-input-material" not in caplog.text
    finally:
        await service.close()
