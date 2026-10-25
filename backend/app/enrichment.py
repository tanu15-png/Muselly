"""Versioned, owner-scoped enrichment; reading a profile never calls Qloo."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import labeled_answers, source_hash
from .auth import AuthUser, get_current_user
from .database import get_db
from .models import TasteAffinityDismissal, TasteAnalysisRun, TasteEnrichmentRun, TasteTest, ProductFeedback
from .onboarding import Draft, images_for, locked_profile, required_errors
from .qloo import normalized, RESOLVER_VERSION

router = APIRouter(prefix='/api/onboarding/enrichment', tags=['Taste enrichment'])
PROFILE_VERSION = 'taste-profile-v1'
LEASE = timedelta(minutes=2)


def snapshot(db, user, settings):
    profile = db.get(TasteTest, user.id)
    current_hash = source_hash(profile, images_for(db, user))
    analysis = db.scalar(select(TasteAnalysisRun).where(
        TasteAnalysisRun.user_id == user.id, TasteAnalysisRun.status == 'succeeded')
        .order_by(TasteAnalysisRun.created_at.desc(), TasteAnalysisRun.id.desc()).limit(1))
    rows = labeled_answers(profile.answers if profile else {})
    stated, signals = [], []
    for row in rows:
        values = [v for v in row['choices'] if v != 'Other']
        if row['other']:
            values.append(row['other'])
        values.extend(row['names'])
        if row['location']:
            values.append(row['location'])
        stated.append({'question_id': row['question_id'], 'question': row['question'], 'source': 'questionnaire',
                       'values': [{'original': v, 'normalized': normalized(v)} for v in dict.fromkeys(values)]})
    by_id = {row['question_id']: row for row in rows}
    def add(id, values, kind):
        for value in values:
            if value.strip() and normalized(value) not in ('not sure', 'other'):
                signal = {'question_id': id, 'input': value.strip(), 'kind': kind}
                if signal not in signals:
                    signals.append(signal)
    brands = by_id.get('q13', {})
    add('q13', brands.get('choices', []), 'brand')
    add('q13', brands.get('other', '').split(','), 'brand')
    liked_brands = [r.product.get('brand', '') for r in db.scalars(select(ProductFeedback).where(
        ProductFeedback.user_id == user.id, ProductFeedback.kind == 'more_like_this')
        .order_by(ProductFeedback.updated_at.desc()).limit(5))]
    add('product_feedback', list(dict.fromkeys(liked_brands)), 'brand')
    add('q7', by_id.get('q7', {}).get('names', []), 'artist')
    add('q8', by_id.get('q8', {}).get('names', []), 'inspiration')
    for id in ('q7', 'q14'):
        row = by_id.get(id, {})
        add(id, row.get('choices', []), 'tag')
        add(id, row.get('other', '').split(','), 'tag')
    # Destination choices (q16), photos, demographics, location, and arbitrary
    # questionnaire text are deliberately excluded from outbound Qloo signals.
    analysis_current = analysis is not None and analysis.source_hash == current_hash
    visual_signals = {}
    if analysis_current:
        result = analysis.result or {}
        for signal in result.get('recurring_visual_signals', []):
            key = (signal['category'], normalized(signal['attribute']))
            entry = visual_signals.setdefault(key, {
                'source': 'image', 'category': key[0], 'normalized': key[1],
                'original_labels': [], 'evidence_image_ids': [], 'explanations': [], 'uncertainties': [],
            })
            entry['original_labels'] = list(dict.fromkeys([*entry['original_labels'], signal['attribute']]))
            entry['evidence_image_ids'] = list(dict.fromkeys([*entry['evidence_image_ids'], *signal['evidence_image_ids']]))
            entry['explanations'] = list(dict.fromkeys([*entry['explanations'], signal['explanation']]))
        for entry in visual_signals.values():
            entry['uncertainties'] = list(dict.fromkeys(
                text for image in result.get('images', []) if image['image_id'] in entry['evidence_image_ids']
                for text in image.get('uncertainties', [])))
    sources = {'profile_version': PROFILE_VERSION, 'questionnaire': stated,
               'analysis_id': str(analysis.id) if analysis else None,
               'analysis_stale': bool(analysis and not analysis_current),
               'visual_signals': list(visual_signals.values()),
               'constraints': [row for row in stated if row['question_id'] in ('q1', 'q3', 'q9', 'q10', 'q11', 'q12', 'q15', 'q16', 'q19')],
               'signals': signals, 'provider': 'qloo', 'provider_host': settings.qloo_base_url.rstrip('/')}
    fingerprint = hashlib.sha256(json.dumps({
        'inputs': current_hash, 'analysis_id': sources['analysis_id'], 'profile_version': PROFILE_VERSION,
        'resolver_version': RESOLVER_VERSION, 'host': sources['provider_host'],
        'credential_version': hashlib.sha256(settings.qloo_api_key.encode()).hexdigest(),
        'feedback_brands': sorted(set(normalized(v) for v in liked_brands if v)),
    }, sort_keys=True).encode()).hexdigest()
    return sources, fingerprint


def latest_run(db, user, *, succeeded=False):
    query = select(TasteEnrichmentRun).where(TasteEnrichmentRun.user_id == user.id)
    if succeeded:
        query = query.where(TasteEnrichmentRun.status == 'succeeded')
    return db.scalar(query.order_by(TasteEnrichmentRun.created_at.desc(), TasteEnrichmentRun.id.desc()).limit(1))


def dismissed_for(db, user):
    return {str(row.entity_id): row.name for row in db.scalars(select(TasteAffinityDismissal).where(TasteAffinityDismissal.user_id == user.id))}


def run_data(run, fingerprint, dismissed):
    result = run.result
    if result:
        result = {**result, 'affinities': [a for a in result['affinities'] if a['entity_id'] not in dismissed]}
    return {'id': run.id, 'status': run.status, 'stale': run.source_hash != fingerprint,
            'resolver_version': run.resolver_version, 'sources': run.sources, 'result': result, 'error': run.error,
            'created_at': run.created_at, 'completed_at': run.completed_at,
            'dismissed': [{'entity_id': id, 'name': name} for id, name in dismissed.items()]}


def view(db, user, settings):
    run = latest_run(db, user)
    if not run:
        raise HTTPException(404, 'No enrichment yet. Enrich your saved preferences to discover brand affinities.')
    _, fingerprint = snapshot(db, user, settings)
    dismissed = dismissed_for(db, user)
    data = run_data(run, fingerprint, dismissed)
    if run.status != 'succeeded':
        previous = latest_run(db, user, succeeded=True)
        data['previous_successful'] = run_data(previous, fingerprint, dismissed) if previous else None
    return data


@router.get('')
def get_enrichment(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return view(db, user, request.app.state.settings)


@router.post('')
def enrich(request: Request, force: bool = False, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = request.app.state.settings
    profile = locked_profile(db, user)
    Draft(answers=profile.answers, position=profile.position)
    if not profile.completed_at or required_errors(profile.answers):
        raise HTTPException(422, 'Finish your taste test before enriching your preferences.')
    sources, fingerprint = snapshot(db, user, settings)
    now = datetime.now(timezone.utc)
    running = db.scalar(select(TasteEnrichmentRun).where(
        TasteEnrichmentRun.user_id == user.id, TasteEnrichmentRun.status == 'running',
        TasteEnrichmentRun.created_at > now - LEASE))
    if running:
        raise HTTPException(409, 'Your enrichment is already running. Check its progress in a moment.')
    cached = db.scalar(select(TasteEnrichmentRun).where(
        TasteEnrichmentRun.user_id == user.id, TasteEnrichmentRun.source_hash == fingerprint,
        TasteEnrichmentRun.status == 'succeeded').order_by(TasteEnrichmentRun.created_at.desc()).limit(1))
    if cached and not force:
        return run_data(cached, fingerprint, dismissed_for(db, user))
    # Profiles without supported interests can still save an honest empty result.
    if sources['signals'] and not settings.qloo_api_key:
        raise HTTPException(503, 'Brand enrichment is not configured yet. Add QLOO_API_KEY to backend/.env and restart the backend.')
    recent = db.scalars(select(TasteEnrichmentRun.id).where(
        TasteEnrichmentRun.user_id == user.id, TasteEnrichmentRun.created_at > now - timedelta(minutes=1))).all()
    if len(recent) >= 3:
        raise HTTPException(429, 'Please wait before refreshing your affinities again.', headers={'Retry-After': '60'})
    run = TasteEnrichmentRun(id=uuid4(), user_id=user.id, source_hash=fingerprint, sources=sources,
                             resolver_version=RESOLVER_VERSION, status='running', created_at=now)
    db.add(run)
    db.commit()  # Release profile lock before network requests; edits can continue.
    try:
        result = request.app.state.qloo.enrich(settings, sources['signals'], refresh=force)
    except HTTPException as failure:
        run.status, run.error, run.completed_at = 'failed', failure.detail, datetime.now(timezone.utc)
        db.commit()
        raise
    run.status, run.result, run.completed_at = 'succeeded', result, datetime.now(timezone.utc)
    db.commit()
    db.expire_all()
    _, current = snapshot(db, user, settings)
    return run_data(run, current, dismissed_for(db, user))


class AffinityPreference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dismissed: bool


@router.put('/affinities/{entity_id}')
def set_affinity_preference(entity_id: UUID, preference: AffinityPreference, request: Request,
                            user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    locked_profile(db, user)
    existing = db.get(TasteAffinityDismissal, (user.id, entity_id))
    if preference.dismissed and not existing:
        # Only a brand returned in this owner's saved enrichment may be dismissed.
        found = None
        for run in db.scalars(select(TasteEnrichmentRun).where(
                TasteEnrichmentRun.user_id == user.id, TasteEnrichmentRun.status == 'succeeded')):
            found = next((a for a in run.result['affinities'] if a['entity_id'] == str(entity_id)), None)
            if found:
                break
        if not found:
            raise HTTPException(404, 'This affinity was not found in your saved profile.')
        db.add(TasteAffinityDismissal(user_id=user.id, entity_id=entity_id, name=found['name']))
    elif not preference.dismissed and existing:
        db.delete(existing)
    elif not existing:
        raise HTTPException(404, 'This dismissed affinity was not found in your saved profile.')
    db.commit()
    return view(db, user, request.app.state.settings)
