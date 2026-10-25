"""Explicit, owner-scoped cultural discovery. GET never calls Qloo."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from time import monotonic
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db
from .enrichment import snapshot
from .models import CulturalDiscoveryRun, CulturalFeedback
from .onboarding import locked_profile, required_errors
from .qloo import entity, normalized

router = APIRouter(prefix='/api/onboarding/culture', tags=['Cultural discovery'])
VERSION = 'culture-v2'
DOMAINS = {'artist': 'Music', 'movie': 'Films', 'tv_show': 'Shows', 'book': 'Books'}


def preferences(db, user):
    return list(db.scalars(select(CulturalFeedback).where(CulturalFeedback.user_id == user.id)
                           .order_by(CulturalFeedback.updated_at.desc(), CulturalFeedback.entity_id)))


def inputs(db, user, settings):
    base, fingerprint = snapshot(db, user, settings)
    # Explicit cultural interests first; shopping feedback is irrelevant here.
    signals = [s for s in base['signals'] if s['question_id'] != 'product_feedback']
    signals.sort(key=lambda s: s['kind'] == 'brand')
    visual = [s for s in base['visual_signals'] if s['category'] == 'aesthetic'][:4]
    for value in visual:
        signals.append({'question_id': 'reference_images', 'kind': 'tag',
                        'input': value['original_labels'][0], 'source': 'image',
                        'evidence_image_ids': value['evidence_image_ids']})
    rows = preferences(db, user)
    feedback = [{'entity_id': str(r.entity_id), 'preference': r.preference,
                 'fashion_inspiration': r.fashion_inspiration, 'entity': r.entity} for r in rows]
    sources = {'version': VERSION, 'signals': signals, 'visual_signals': base['visual_signals'],
               'analysis_stale': base['analysis_stale'], 'feedback': feedback,
               'image_analysis_status': 'missing' if not base['analysis_id'] else 'stale' if base['analysis_stale'] else 'current'}
    digest = hashlib.sha256(json.dumps([VERSION, fingerprint, feedback], sort_keys=True).encode()).hexdigest()
    return sources, digest


def latest(db, user, succeeded=False):
    query = select(CulturalDiscoveryRun).where(CulturalDiscoveryRun.user_id == user.id)
    if succeeded:
        query = query.where(CulturalDiscoveryRun.status == 'succeeded')
    return db.scalar(query.order_by(CulturalDiscoveryRun.created_at.desc(), CulturalDiscoveryRun.id.desc()).limit(1))


def serialize(run, fingerprint):
    return {'id': run.id, 'status': run.status, 'stale': run.source_hash != fingerprint,
            'sources': run.sources, 'result': run.result, 'error': run.error,
            'created_at': run.created_at, 'completed_at': run.completed_at}


def view(db, user, settings):
    sources, fingerprint = inputs(db, user, settings)
    run = latest(db, user)
    data = serialize(run, fingerprint) if run else {'status': 'not_generated', 'result': None}
    if run and run.status != 'succeeded':
        previous = latest(db, user, True)
        data['previous_successful'] = serialize(previous, fingerprint) if previous else None
    data['feedback'] = sources['feedback']
    data['analytics'] = {'liked': sum(r['preference'] == 'like' for r in sources['feedback']),
                         'fashion_inspirations': sum(r['fashion_inspiration'] for r in sources['feedback']),
                         'dismissed': sum(r['preference'] == 'dislike' for r in sources['feedback'])}
    from .discovery import session_view
    data['session'] = session_view(db, user)
    return data


def artwork(item):
    value = (item.get('properties') or {}).get('image')
    url = value.get('url') if isinstance(value, dict) else value
    if isinstance(url, str) and len(url) <= 2048:
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname and '.' in parsed.hostname and not parsed.username:
            return url
    return None


def discover(provider, settings, sources, refresh=False, *, offsets=None, categories=None, include_themes=True):
    deadline = monotonic() + 32
    resolutions = []
    # Reserve room for image-derived tags instead of silently dropping them.
    chosen = [s for s in sources['signals'] if s.get('source') != 'image'][:16]
    chosen += [s for s in sources['signals'] if s.get('source') == 'image'][:4]
    for signal in chosen:
        try:
            resolution = provider.resolve(settings, signal, deadline, refresh=refresh)
        except HTTPException as failure:
            resolution = {**signal, 'status': 'unavailable', 'candidates': [], 'error_code': failure.status_code}
        if signal.get('source') == 'image' and resolution['status'] == 'resolved':
            tag = resolution['match'].get('tag_id', '')
            if not any(part in tag.split(':') for part in ('fashion', 'aesthetic', 'aesthetics', 'style')):
                resolution = {**signal, 'status': 'unsupported', 'candidates': []}
        resolutions.append(resolution)
    for signal in sources['signals']:
        if signal not in chosen:
            resolutions.append({**signal, 'status': 'deferred', 'candidates': []})
    ids = {r['match']['entity_id'] for r in resolutions if r['status'] == 'resolved' and 'entity_id' in r['match']}
    tags = {r['match']['tag_id'] for r in resolutions if r['status'] == 'resolved' and 'tag_id' in r['match']}
    excluded = set()
    positive = []
    for row in sources['feedback']:
        if row['preference'] in ('dislike', 'known'):
            excluded.add(row['entity_id'])
        elif row['preference'] == 'like' or row['fashion_inspiration']:
            positive.append(row['entity_id'])
    ids = set([*positive[:12], *sorted(ids)[:12]])
    ids -= excluded
    if not ids and not tags:
        if any(row['status'] == 'unavailable' for row in resolutions):
            raise HTTPException(503, 'Qloo could not resolve your interests right now. Please retry.')
        return {'resolutions': resolutions, 'domains': [], 'themes': [], 'outcome': 'no-supported-signals'}
    params = {'take': 8}
    if ids:
        params['signal.interests.entities'] = ','.join(sorted(ids))
    if tags:
        params['signal.interests.tags'] = ','.join(sorted(tags))
    excluded.update(sources.get('excluded_ids', [])[:100])
    if excluded or ids:
        params['filter.exclude.entities'] = ','.join(sorted(excluded | ids)[:100])
    def category_result(kind):
        label = DOMAINS[kind]
        offset = (offsets or {}).get(kind, 0)
        try:
            values = provider.get(settings, '/v2/insights', {**params, 'filter.type': f'urn:entity:{kind}', 'offset': offset},
                                  deadline=monotonic() + (60 if kind == 'artist' else 32),
                                  timeout_seconds=25 if kind == 'artist' else 12, ttl=900, refresh=refresh)
            items, seen = [], ids | excluded
            for rank, raw in enumerate(values, 1):
                item = entity(raw)
                if item['entity_id'] in seen:
                    continue
                seen.add(item['entity_id'])
                tags = [{'tag_id': str(t.get('tag_id') or t.get('id')), 'name': t['name']}
                        for t in raw.get('tags', []) if isinstance(t, dict) and isinstance(t.get('name'), str)
                        and len(t['name']) <= 100 and str(t.get('tag_id') or t.get('id') or '').startswith('urn:tag:')][:16]
                items.append({**item, 'rank': offset + rank, 'image': artwork(raw), 'source': 'qloo', 'tags': tags})
            return {'id': kind, 'label': label, 'status': 'ready', 'items': items,
                    'offset': offset, 'next_offset': offset + len(values), 'exhausted': len(values) < 8,
                    'received_count': len(values), 'excluded_count': len(values) - len(items)}
        except HTTPException as failure:
            return {'id': kind, 'label': label, 'status': 'unavailable', 'items': [],
                    'offset': offset, 'next_offset': offset, 'exhausted': False,
                    'error_code': failure.status_code, 'error': failure.detail}
    requested = [kind for kind in DOMAINS if not categories or kind in categories]
    with ThreadPoolExecutor(max_workers=4) as pool:
        domains = list(pool.map(category_result, requested))
    errors = [domain for domain in domains if domain['status'] == 'unavailable']
    if len(errors) == len(domains):
        raise HTTPException(errors[0]['error_code'], errors[0]['error'])
    themes = []
    try:
        values = provider.get(settings, '/v2/insights', {**params, 'filter.type': 'urn:tag',
            'filter.parents.types': 'urn:entity:movie,urn:entity:tv_show',
            'filter.tag.types': 'urn:tag:keyword:media'}, deadline=monotonic() + 12, ttl=900, refresh=refresh) if include_themes else []
        themes = [{'tag_id': t['id'], 'name': t['name']} for t in values[:6]]
    except HTTPException:
        pass  # Entity discoveries remain usable when tag analysis is unavailable.
    return {'resolutions': resolutions, 'domains': domains, 'themes': themes,
            'outcome': 'partial' if errors else 'discovered',
            'input_counts': dict(Counter('images' if r.get('source') == 'image' else 'questionnaire'
                for r in resolutions if r['status'] == 'resolved'))}


@router.get('')
def get_culture(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return view(db, user, request.app.state.settings)


@router.post('')
def generate(request: Request, force: bool = False, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = locked_profile(db, user)
    if not profile.completed_at or required_errors(profile.answers):
        raise HTTPException(422, 'Finish your taste test first.')
    settings = request.app.state.settings
    sources, fingerprint = inputs(db, user, settings)
    now = datetime.now(timezone.utc)
    if db.scalar(select(CulturalDiscoveryRun.id).where(CulturalDiscoveryRun.user_id == user.id,
            CulturalDiscoveryRun.status == 'running', CulturalDiscoveryRun.created_at > now - timedelta(minutes=2))):
        raise HTTPException(409, 'Discoveries are updating. Check again shortly.')
    cached = latest(db, user, True)
    if cached and cached.source_hash == fingerprint and not force and (cached.result or {}).get('outcome') != 'partial':
        from .discovery import current_session, create_session
        if not current_session(db, user):
            create_session(db, user, cached.sources, fingerprint, cached.result)
            db.commit()
        return view(db, user, settings)
    if not settings.qloo_api_key:
        raise HTTPException(503, 'Cultural discovery is unavailable. Check the Qloo configuration.')
    recent = db.scalars(select(CulturalDiscoveryRun.id).where(CulturalDiscoveryRun.user_id == user.id,
                        CulturalDiscoveryRun.created_at > now - timedelta(minutes=1))).all()
    if len(recent) >= 3:
        raise HTTPException(429, 'Please wait a minute before refreshing again.')
    run = CulturalDiscoveryRun(id=uuid4(), user_id=user.id, source_hash=fingerprint,
                               sources=sources, status='running', created_at=now)
    db.add(run)
    db.commit()
    try:
        result = discover(request.app.state.qloo, settings, sources, refresh=force)
    except HTTPException as failure:
        run.status, run.error, run.completed_at = 'failed', failure.detail, datetime.now(timezone.utc)
        db.commit()
        raise
    run.status, run.result, run.completed_at = 'succeeded', result, datetime.now(timezone.utc)
    db.commit()
    from .discovery import create_session
    create_session(db, user, sources, fingerprint, result)
    db.commit()
    return view(db, user, settings)


class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preference: Literal['like', 'dislike', 'known'] | None = None
    fashion_inspiration: bool = False
    reference_image_ids: list[UUID] | None = Field(default=None, max_length=20)


@router.put('/feedback/{entity_id}')
def feedback(entity_id: UUID, payload: Feedback, request: Request,
             user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    locked_profile(db, user)
    existing = db.get(CulturalFeedback, (user.id, entity_id))
    found = existing.entity if existing else None
    if not found:
        for run in db.scalars(select(CulturalDiscoveryRun).where(CulturalDiscoveryRun.user_id == user.id,
                                                                   CulturalDiscoveryRun.status == 'succeeded')):
            found = next((item for domain in (run.result or {}).get('domains', [])
                          for item in domain['items'] if item['entity_id'] == str(entity_id)), None)
            if found:
                break
    if not found:
        raise HTTPException(404, 'Discovery not found in your profile.')
    if not existing:
        existing = CulturalFeedback(user_id=user.id, entity_id=entity_id, entity=found)
        db.add(existing)
    before = {'preference': existing.preference, 'fashion_inspiration': bool(existing.fashion_inspiration)}
    existing.preference = payload.preference
    existing.fashion_inspiration = payload.fashion_inspiration if payload.preference not in ('dislike', 'known') else False
    if payload.reference_image_ids is not None:
        from .discovery import confirmed_references
        existing.reference_image_ids = confirmed_references(db, user, payload.reference_image_ids)
    if not existing.fashion_inspiration:
        existing.reference_image_ids = []
    from .models import CulturalEvent
    db.add(CulturalEvent(id=uuid4(), user_id=user.id, entity_id=entity_id, action='edit', created_at=datetime.now(timezone.utc), data={'before': before, 'after': {'preference': existing.preference, 'fashion_inspiration': existing.fashion_inspiration}, 'entity': found}))
    db.commit()
    return view(db, user, request.app.state.settings)
