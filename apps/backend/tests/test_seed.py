from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AIModel, Camera, Factory, Rule, Zone
from app.seed import seed


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_fresh_seed_includes_the_bean_line_once():
    db = _session()
    seed(db)
    codes = {camera.code for camera in db.query(Camera).all()}
    assert "CAM-BEAN-01" in codes
    assert len(codes) == 5
    bean = db.query(Camera).filter(Camera.code == "CAM-BEAN-01").one()
    assert {zone.zone_type for zone in db.query(Zone).filter(Zone.camera_id == bean.id)} == {
        "GREEN_COFFEE_LINE",
        "ROASTED_COFFEE_LINE",
        "COFFEE_COUNT_LINE",
    }
    events = {rule.event_type for rule in db.query(Rule).filter(Rule.camera_id == bean.id)}
    assert events == {"GREEN_COFFEE_DEFECT_RATE", "ROASTED_COFFEE_DEFECT_RATE"}
    assert db.query(AIModel).filter(AIModel.name == "coffee-line", AIModel.version == "v0-demo").count() == 1
    before = (db.query(Camera).count(), db.query(Zone).count(), db.query(Rule).count(), db.query(AIModel).count())
    seed(db)
    after = (db.query(Camera).count(), db.query(Zone).count(), db.query(Rule).count(), db.query(AIModel).count())
    assert before == after
    db.close()


def test_existing_factory_gains_the_bean_line_without_a_second_copy():
    db = _session()
    db.add(Factory(name="Coffee Factory POC", code="coffee-poc", timezone="Asia/Ho_Chi_Minh"))
    db.commit()
    seed(db)
    cameras = db.query(Camera).all()
    assert [camera.code for camera in cameras] == ["CAM-BEAN-01"]
    assert db.query(Zone).count() == 3
    assert db.query(Rule).count() == 2
    assert db.query(AIModel).filter(AIModel.name == "coffee-line").count() == 1
    seed(db)
    assert db.query(Camera).count() == 1
    assert db.query(Zone).count() == 3
    assert db.query(Rule).count() == 2
    db.close()
