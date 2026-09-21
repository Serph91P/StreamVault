"""Credential-free policy for the single authenticated Twitch recording slot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable


class AuthDecisionKind(str, Enum):
    KEEP = "keep"
    PROMOTE = "promote"
    HANDOFF = "handoff"
    BLOCKED = "blocked"
    IDLE = "idle"


@dataclass(frozen=True)
class AuthCandidate:
    channel_key: str
    recording_id: int
    priority: int
    started_at: datetime
    authenticated: bool = False
    anonymous_available: bool = True
    purpose: str = "RECORDING"
    eligible: bool = True


@dataclass(frozen=True)
class AuthDecision:
    kind: AuthDecisionKind
    owner_channel_key: str | None
    requested_channel_key: str | None = None
    displaced_channel_key: str | None = None
    pending_handoff: bool = False
    reason: str | None = None


class TwitchAuthScheduler:
    """Make a deterministic, side-effect-free arbitration decision.

    Stable ordering without an owner is priority descending, start time
    ascending, recording id ascending, then channel key. Equal priority never
    displaces an existing owner. Live playback is deliberately non-preemptible.
    """

    def decide(self, candidates: Iterable[AuthCandidate]) -> AuthDecision:
        active = tuple(candidate for candidate in candidates if candidate.eligible)
        owners = tuple(candidate for candidate in active if candidate.authenticated)
        if len(owners) > 1:
            return AuthDecision(
                kind=AuthDecisionKind.BLOCKED,
                owner_channel_key=None,
                reason="multiple_authenticated_owners",
            )

        ranked = sorted(
            active,
            key=lambda candidate: (
                -candidate.priority,
                candidate.started_at,
                candidate.recording_id,
                candidate.channel_key,
            ),
        )
        if not ranked:
            return AuthDecision(AuthDecisionKind.IDLE, None)

        requested = ranked[0]
        if not owners:
            return AuthDecision(
                kind=AuthDecisionKind.PROMOTE,
                owner_channel_key=requested.channel_key,
                requested_channel_key=requested.channel_key,
                reason="highest_priority_eligible_recording",
            )

        owner = owners[0]
        if requested.channel_key == owner.channel_key or (
            requested.priority <= owner.priority
        ):
            return AuthDecision(AuthDecisionKind.KEEP, owner.channel_key)

        if owner.purpose != "RECORDING":
            return AuthDecision(
                AuthDecisionKind.BLOCKED,
                owner.channel_key,
                requested_channel_key=requested.channel_key,
                reason="live_playback_owner_not_preemptible",
            )
        if not owner.anonymous_available:
            return AuthDecision(
                AuthDecisionKind.BLOCKED,
                owner.channel_key,
                requested_channel_key=requested.channel_key,
                reason="owner_anonymous_unavailable",
            )

        return AuthDecision(
            AuthDecisionKind.HANDOFF,
            owner.channel_key,
            requested_channel_key=requested.channel_key,
            displaced_channel_key=owner.channel_key,
            pending_handoff=True,
            reason="higher_priority_recording",
        )
