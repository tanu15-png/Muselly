"""Read-only, owner-scoped dashboard counts. Never calls a model or Qloo."""
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db
from .enrichment import dismissed_for, latest_run, snapshot
from .models import ProductFeedback, SavedProduct

router = APIRouter(prefix='/api/onboarding', tags=['Taste analytics'])


@router.get('/analytics')
def analytics(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    feedback = dict(db.execute(select(ProductFeedback.kind, func.count()).where(
        ProductFeedback.user_id == user.id).group_by(ProductFeedback.kind)).all())
    saved = db.scalar(select(func.count()).select_from(SavedProduct).where(SavedProduct.user_id == user.id))
    last_feedback = db.scalar(select(func.max(ProductFeedback.updated_at)).where(ProductFeedback.user_id == user.id))
    run = latest_run(db, user, succeeded=True)
    qloo = {'status': 'not_generated', 'stale': False, 'brands': [], 'inputs': [], 'input_counts': {},
            'unresolved_count': 0, 'completed_at': None}
    if run:
        _, fingerprint = snapshot(db, user, request.app.state.settings)
        result = run.result or {}
        hidden = dismissed_for(db, user)
        # Count distinct resolved interests, not duplicate questionnaire entries.
        inputs, seen = [], set()
        for resolution in result.get('resolutions', []):
            if resolution.get('status') != 'resolved':
                continue
            match = resolution.get('match') or {}
            identity = match.get('entity_id') or match.get('tag_id')
            key = identity or (resolution.get('kind'), resolution.get('input', '').casefold())
            if key in seen:
                continue
            seen.add(key)
            inputs.append({'kind': resolution.get('kind', 'other'), 'label': resolution.get('input', '')})
        qloo = {'status': 'saved', 'stale': run.source_hash != fingerprint,
                'brands': [{'name': a['name'], 'entity_id': a['entity_id'], 'rank': a['rank']}
                           for a in result.get('affinities', []) if a['entity_id'] not in hidden],
                'inputs': inputs, 'input_counts': dict(Counter(row['kind'] for row in inputs)),
                'unresolved_count': sum(r.get('status') != 'resolved' for r in result.get('resolutions', [])),
                'completed_at': run.completed_at}
    return {'qloo': qloo, 'shopping': {'feedback_counts': feedback, 'refined_products': sum(feedback.values()),
                                     'saved_products': saved, 'last_feedback_at': last_feedback},
            'retrieved_at': datetime.now(timezone.utc)}
