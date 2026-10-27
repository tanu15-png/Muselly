"""Evidence-based visual and cultural analytics; no provider calls."""
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import labeled_answers, source_hash
from .auth import AuthUser, get_current_user
from .database import get_db
from .models import CulturalExposure, CulturalEvent, CulturalFeedback, TasteAnalysisRun, TasteTest
from .onboarding import images_for
from .qloo import normalized

router = APIRouter(prefix='/api/onboarding/culture', tags=['Cultural analytics'])


def category(item):
    return item.get('domain') or item.get('type', '').removeprefix('urn:entity:')


def timestamp(value):
    try:
        date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError):
        return None


@router.get('/analytics')
def analytics(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(TasteTest, user.id)
    images = list(images_for(db, user))
    run = db.scalar(select(TasteAnalysisRun).where(TasteAnalysisRun.user_id == user.id,
        TasteAnalysisRun.status == 'succeeded').order_by(TasteAnalysisRun.created_at.desc(), TasteAnalysisRun.id.desc()).limit(1))
    observations = []
    if run:
        sources = {str(row['id']): row for row in run.sources.get('images', [])}
        valid = {str(image.id) for image in images if str(image.id) in sources and
                 timestamp(sources[str(image.id)].get('updated_at')) == timestamp(image.updated_at)}
        observations = [row for row in (run.result or {}).get('images', []) if row['image_id'] in valid]
    def visual_counts(field):
        groups = {}
        for row in observations:
            for label in row.get(field, []):
                key = normalized(label)
                if not key:
                    continue
                group = groups.setdefault(key, {'label': label.strip(), 'image_ids': set()})
                group['image_ids'].add(row['image_id'])
        return sorted([{'label': value['label'], 'count': len(value['image_ids']),
                        'image_ids': sorted(value['image_ids'])} for value in groups.values()],
                      key=lambda row: (-row['count'], row['label']))
    rows = list(db.scalars(select(CulturalFeedback).where(CulturalFeedback.user_id == user.id)))
    exposures = list(db.scalars(select(CulturalExposure).where(CulturalExposure.user_id == user.id)))
    events = list(db.scalars(select(CulturalEvent).where(CulturalEvent.user_id == user.id)
                          .order_by(CulturalEvent.created_at, CulturalEvent.id)))
    totals = {'shown': len({str(row.entity_id) for row in exposures}), 'liked': 0, 'disliked': 0,
              'known': 0, 'fashion': 0, 'rated': 0}
    domains = {key: {'id': key, 'shown': 0, 'liked': 0, 'disliked': 0, 'known': 0, 'fashion': 0, 'rated': 0}
               for key in ('artist', 'movie', 'tv_show', 'book')}
    for key, domain in domains.items():
        domain['shown'] = len({str(row.entity_id) for row in exposures if category(row.entity) == key})
    themes, fashion_themes = Counter(), Counter()
    fashion_entities = []
    for row in rows:
        domain = domains.get(category(row.entity))
        for key, yes in [('liked', row.preference == 'like'), ('disliked', row.preference == 'dislike'),
                         ('known', row.preference == 'known'), ('fashion', row.fashion_inspiration),
                         ('rated', row.preference in ('like', 'dislike'))]:
            totals[key] += bool(yes)
            if domain:
                domain[key] += bool(yes)
        tags = {tag['name'] for tag in row.entity.get('tags', []) if isinstance(tag, dict) and isinstance(tag.get('name'), str)}
        if row.preference == 'like':
            themes.update(tags)
        if row.fashion_inspiration:
            fashion_themes.update(tags)
            # Deleted/replaced images cease to be evidence, even in older saves.
            current_ids = {str(image.id) for image in images}
            linked = [value for value in (row.reference_image_ids or []) if value in current_ids]
            evidence = [item for item in observations if item['image_id'] in linked]
            fashion_entities.append({**row.entity, 'preference': row.preference, 'reference_image_ids': linked, 'fashion_note': row.fashion_note or '',
                'colors': sorted({value for item in evidence for value in item.get('colors', [])}),
                'patterns': sorted({value for item in evidence for value in item.get('patterns', [])})})
    undone = {row.data.get('target_id') for row in events if row.action == 'undo'}
    daily = {}
    for row in events:
        if row.action in ('shown', 'skip', 'undo', 'edit') or str(row.id) in undone:
            continue
        day = row.created_at.date().isoformat()  # Stored UTC; explicitly labelled in the UI.
        point = daily.setdefault(day, {'date': day, 'like': 0, 'dislike': 0, 'known': 0, 'fashion': 0})
        if row.action in point:
            point[row.action] += 1
    for domain in domains.values():
        domain['like_rate'] = round(domain['liked'] / domain['rated'] * 100) if domain['rated'] else None
    stated = {row['question_id']: [*filter(lambda value: value != 'Other', row['choices']),
                                  *([row['other']] if row['other'] else [])]
              for row in labeled_answers(profile.answers if profile else {})}
    tag_counts = lambda counts: [{'label': label, 'count': count} for label, count in counts.most_common(12)]
    return {'visual': {'analyzed_images': len(observations), 'saved_images': len(images),
                       'stale': bool(run and run.source_hash != source_hash(profile, images)),
                       'colors': visual_counts('colors'), 'patterns': visual_counts('patterns'),
                       'aesthetics': visual_counts('possible_aesthetics'), 'stated_colors': stated.get('q10', [])},
            'cultural': {'totals': totals, 'domains': list(domains.values()), 'themes': tag_counts(themes),
                         'history': sorted(daily.values(), key=lambda point: point['date'])[-14:],
                         'sessions': len({row.session_id for row in exposures}),
                         'history_started_at': min((row.created_at for row in exposures), default=None)},
            'combined': {'fashion_entities': fashion_entities, 'fashion_themes': tag_counts(fashion_themes),
                         'source': 'Explicit fashion saves + observed reference attributes; no inferred causal link'},
            'retrieved_at': datetime.now(timezone.utc)}
