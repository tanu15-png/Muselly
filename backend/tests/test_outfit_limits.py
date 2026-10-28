from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.outfits import allowance
from datetime import datetime, timezone


def test_allowance_tracks_daily_and_lifetime():
    engine = create_engine('sqlite://')
    with Session(engine) as db:
        db.execute(text('CREATE TABLE muselly_outfit_limits (user_id TEXT PRIMARY KEY, day TEXT, daily INTEGER, total INTEGER)'))
        assert allowance(db, 'one') == {'daily_remaining': 3, 'total_remaining': 10}
        db.execute(text("INSERT INTO muselly_outfit_limits VALUES ('one', :day, 3, 10)"), {'day': datetime.now(timezone.utc).date().isoformat()})
        assert allowance(db, 'one') == {'daily_remaining': 0, 'total_remaining': 0}
        db.execute(text("UPDATE muselly_outfit_limits SET day='2000-01-01'"))
        assert allowance(db, 'one') == {'daily_remaining': 3, 'total_remaining': 0}
        assert allowance(db, 'other')['total_remaining'] == 10
