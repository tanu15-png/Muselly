import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.outfits import save_feedback, OutfitFeedback, feedback_context, saved


def test_votes_persist_are_scoped_and_can_be_changed_or_cleared():
    engine = create_engine('sqlite://')
    owner, other, outfit = uuid4(), uuid4(), uuid4()
    with Session(engine) as db:
        db.execute(text('CREATE TABLE muselly_outfits (id TEXT PRIMARY KEY, user_id TEXT, payload TEXT, created_at TEXT)'))
        db.execute(text('CREATE TABLE muselly_outfit_limits (user_id TEXT, day TEXT, daily INTEGER, total INTEGER)'))
        db.execute(text('INSERT INTO muselly_outfits VALUES (:id,:u,:p, :t)'),
                   {'id': str(outfit), 'u': str(owner), 'p': json.dumps({'description': 'Pink top, navy trousers', 'brief': 'Office'}), 't': '2026'})
        db.commit()
        user = SimpleNamespace(id=owner)
        save_feedback(outfit, OutfitFeedback(choice='like', reason='color'), user, db)
        assert saved(user, db)['outfits'][0]['feedback'] == {'choice': 'like', 'reason': 'color'}
        assert feedback_context(db, str(owner))[0]['description'] == 'Pink top, navy trousers'
        assert feedback_context(db, str(other)) == []
        with pytest.raises(HTTPException) as error:
            save_feedback(outfit, OutfitFeedback(choice='dislike'), SimpleNamespace(id=other), db)
        assert error.value.status_code == 404
        save_feedback(outfit, OutfitFeedback(choice='dislike', reason='shape'), user, db)
        assert len(feedback_context(db, str(owner))) == 1
        assert feedback_context(db, str(owner))[0]['reason'] == 'shape'
        save_feedback(outfit, OutfitFeedback(choice='clear'), user, db)
        assert feedback_context(db, str(owner)) == []
        assert saved(user, db)['outfits'][0]['feedback'] is None
