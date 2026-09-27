from app.rule_engine import Observation, RuleConfig, RuleEngine


def rule(**overrides) -> RuleConfig:
    base = dict(
        id="rule-1",
        zone_id="zone-1",
        condition_type="PERSON_INSIDE",
        event_type="RESTRICTED_AREA_INTRUSION",
        severity="HIGH",
        min_duration_s=2.0,
        cooldown_s=10.0,
        grace_s=1.0,
    )
    base.update(overrides)
    return RuleConfig(**base)


def see(engine, config, t, inside=True, hairnet="YES", uniform="CORRECT", track="7", klass="person"):
    return engine.update(
        config,
        Observation(
            track_id=track,
            timestamp=t,
            inside=inside,
            hairnet=hairnet,
            uniform=uniform,
            confidence=0.9,
            bbox=(0.4, 0.4, 0.5, 0.7),
            class_name=klass,
        ),
    )


def test_duration_opens_one_incident_and_suppresses_duplicates():
    engine = RuleEngine()
    config = rule()
    assert see(engine, config, 0.0) == []
    opened = see(engine, config, 2.0)
    assert len(opened) == 1
    assert opened[0].kind == "open"
    assert opened[0].started_at == 0.0
    engine.attach_incident("rule-1", "7", "inc-1")
    assert see(engine, config, 2.5) == []
    assert see(engine, config, 4.0) == []


def test_brief_loss_does_not_reset_the_timer():
    engine = RuleEngine()
    config = rule()
    see(engine, config, 0.0)
    see(engine, config, 1.0)
    assert see(engine, config, 1.5, inside=False) == []
    opened = see(engine, config, 2.0)
    assert len(opened) == 1
    assert opened[0].kind == "open"


def test_long_gap_resets_pending_duration():
    engine = RuleEngine()
    config = rule(grace_s=0.4)
    see(engine, config, 0.0)
    assert see(engine, config, 0.5, inside=False) == []
    assert see(engine, config, 1.0) == []
    assert see(engine, config, 2.9) == []
    opened = see(engine, config, 3.0)
    assert len(opened) == 1
    assert opened[0].started_at == 1.0


def test_leave_closes_then_cooldown_blocks_reentry():
    engine = RuleEngine()
    config = rule()
    see(engine, config, 0.0)
    see(engine, config, 2.0)
    engine.attach_incident("rule-1", "7", "inc-1")
    see(engine, config, 4.0)
    closed = see(engine, config, 5.5, inside=False)
    assert len(closed) == 1
    assert closed[0].kind == "close"
    assert closed[0].incident_id == "inc-1"
    assert closed[0].ended_at == 4.0
    assert see(engine, config, 6.0) == []
    assert see(engine, config, 16.0) == []
    opened = see(engine, config, 18.0)
    assert len(opened) == 1
    assert opened[0].kind == "open"


def test_unknown_hairnet_does_not_violate():
    engine = RuleEngine()
    config = rule(condition_type="HAIRNET_MISSING", event_type="HAIRNET_VIOLATION")
    assert see(engine, config, 0.0, hairnet="UNKNOWN") == []
    assert see(engine, config, 5.0, hairnet="UNKNOWN") == []
    assert see(engine, config, 0.0, hairnet="YES", track="8") == []
    assert see(engine, config, 3.0, hairnet="YES", track="8") == []


def test_missing_hairnet_opens_after_duration():
    engine = RuleEngine()
    config = rule(condition_type="HAIRNET_MISSING", event_type="HAIRNET_VIOLATION")
    assert see(engine, config, 0.0, hairnet="NO") == []
    opened = see(engine, config, 2.0, hairnet="NO")
    assert len(opened) == 1
    assert opened[0].event_type == "HAIRNET_VIOLATION"


def test_unknown_uniform_does_not_violate_and_incorrect_does():
    engine = RuleEngine()
    config = rule(condition_type="UNIFORM_INCORRECT", event_type="UNIFORM_VIOLATION")
    assert see(engine, config, 0.0, uniform="UNKNOWN") == []
    assert see(engine, config, 4.0, uniform="UNKNOWN") == []
    assert see(engine, config, 0.0, uniform="INCORRECT", track="9") == []
    opened = see(engine, config, 2.0, uniform="INCORRECT", track="9")
    assert len(opened) == 1


def test_forklift_track_does_not_open_person_rule():
    engine = RuleEngine()
    config = rule()
    assert see(engine, config, 0.0, klass="forklift") == []
    assert see(engine, config, 5.0, klass="forklift") == []


def test_missing_track_closes_after_grace():
    engine = RuleEngine()
    config = rule()
    see(engine, config, 0.0)
    see(engine, config, 2.0)
    engine.attach_incident("rule-1", "7", "inc-9")
    assert engine.expire_missing({config.id: config}, 2.5, set()) == []
    closed = engine.expire_missing({config.id: config}, 4.5, set())
    assert len(closed) == 1
    assert closed[0].kind == "close"
