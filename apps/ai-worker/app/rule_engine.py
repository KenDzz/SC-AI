"""Temporal rule evaluation.

One open incident is created per camera track and rule. Frames only extend that
incident. UNKNOWN PPE never satisfies a PPE rule. Cooldown starts when the
person leaves, after a short grace period for brief occlusion.
"""

from dataclasses import dataclass, field


@dataclass
class Observation:
    track_id: str
    timestamp: float
    inside: bool
    hairnet: str = "UNKNOWN"
    uniform: str = "UNKNOWN"
    confidence: float = 0.0
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    class_name: str = "person"


@dataclass
class RuleConfig:
    id: str
    zone_id: str
    condition_type: str
    event_type: str
    severity: str
    min_duration_s: float
    cooldown_s: float
    grace_s: float


@dataclass
class Action:
    kind: str
    rule_id: str
    zone_id: str
    track_id: str
    event_type: str
    severity: str
    confidence: float
    started_at: float
    ended_at: float | None
    bbox: tuple[float, float, float, float]
    incident_id: str | None = None


@dataclass
class _State:
    phase: str
    started_at: float
    last_true_at: float
    last_bbox: tuple[float, float, float, float]
    last_confidence: float
    cooldown_until: float = 0.0
    incident_id: str | None = None


@dataclass
class RuleEngine:
    _states: dict[tuple[str, str], _State] = field(default_factory=dict)

    def condition_met(self, rule: RuleConfig, obs: Observation) -> bool:
        if obs.class_name != "person" or not obs.inside:
            return False
        if rule.condition_type == "PERSON_INSIDE":
            return True
        if rule.condition_type == "HAIRNET_MISSING":
            return obs.hairnet == "NO"
        if rule.condition_type == "UNIFORM_INCORRECT":
            return obs.uniform == "INCORRECT"
        return False

    def update(self, rule: RuleConfig, obs: Observation) -> list[Action]:
        key = (rule.id, obs.track_id)
        state = self._states.get(key)
        if self.condition_met(rule, obs):
            return self._on_true(rule, key, state, obs)
        return self._on_false(rule, key, state, obs.timestamp)

    def expire_missing(self, rules: dict[str, RuleConfig], now: float, visible_track_ids: set[str]) -> list[Action]:
        actions: list[Action] = []
        for key, state in list(self._states.items()):
            rule_id, track_id = key
            if track_id in visible_track_ids or state.phase not in {"pending", "open"}:
                continue
            rule = rules.get(rule_id)
            if rule is None:
                continue
            if now - state.last_true_at <= rule.grace_s:
                continue
            actions.extend(self._abandon(rule, key, state, now))
        return actions

    def attach_incident(self, rule_id: str, track_id: str, incident_id: str) -> None:
        state = self._states.get((rule_id, track_id))
        if state is not None:
            state.incident_id = incident_id
            state.phase = "open"

    def force_cooldown(self, rule_id: str, track_id: str, until: float) -> None:
        state = self._states.get((rule_id, track_id))
        if state is None:
            self._states[(rule_id, track_id)] = _State(
                phase="cooldown",
                started_at=until,
                last_true_at=until,
                last_bbox=(0, 0, 0, 0),
                last_confidence=0,
                cooldown_until=until,
            )
            return
        state.phase = "cooldown"
        state.cooldown_until = until
        state.incident_id = None

    def _on_true(self, rule: RuleConfig, key: tuple[str, str], state: _State | None, obs: Observation) -> list[Action]:
        if state is not None and state.phase == "cooldown" and obs.timestamp < state.cooldown_until:
            return []
        if state is None or state.phase in {"cooldown", "idle"}:
            state = _State(
                phase="pending",
                started_at=obs.timestamp,
                last_true_at=obs.timestamp,
                last_bbox=obs.bbox,
                last_confidence=obs.confidence,
            )
            self._states[key] = state
        else:
            state.last_true_at = obs.timestamp
            state.last_bbox = obs.bbox
            state.last_confidence = obs.confidence
        if state.phase == "pending" and obs.timestamp - state.started_at >= rule.min_duration_s:
            state.phase = "open"
            return [
                Action(
                    kind="open",
                    rule_id=rule.id,
                    zone_id=rule.zone_id,
                    track_id=obs.track_id,
                    event_type=rule.event_type,
                    severity=rule.severity,
                    confidence=state.last_confidence,
                    started_at=state.started_at,
                    ended_at=None,
                    bbox=state.last_bbox,
                )
            ]
        return []

    def _on_false(self, rule: RuleConfig, key: tuple[str, str], state: _State | None, now: float) -> list[Action]:
        if state is None or state.phase in {"cooldown", "idle"}:
            return []
        if now - state.last_true_at <= rule.grace_s:
            return []
        return self._abandon(rule, key, state, now)

    def _abandon(self, rule: RuleConfig, key: tuple[str, str], state: _State, now: float) -> list[Action]:
        if state.phase == "open" and state.incident_id:
            ended_at = state.last_true_at
            state.phase = "cooldown"
            state.cooldown_until = now + rule.cooldown_s
            incident_id = state.incident_id
            state.incident_id = None
            return [
                Action(
                    kind="close",
                    rule_id=rule.id,
                    zone_id=rule.zone_id,
                    track_id=key[1],
                    event_type=rule.event_type,
                    severity=rule.severity,
                    confidence=state.last_confidence,
                    started_at=state.started_at,
                    ended_at=ended_at,
                    bbox=state.last_bbox,
                    incident_id=incident_id,
                )
            ]
        if state.phase == "open" and not state.incident_id:
            state.phase = "cooldown"
            state.cooldown_until = now + rule.cooldown_s
            return []
        self._states.pop(key, None)
        return []
