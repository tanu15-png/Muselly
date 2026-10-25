"""Resumable Qloo decks. Only explicit batch requests call the provider."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db
from .models import CulturalSession, CulturalExposure, CulturalEvent, CulturalFeedback, UserProfile, InspirationImage
from .onboarding import locked_profile

router = APIRouter(prefix='/api/onboarding/culture/sessions', tags=['Discovery sessions'])


def current_session(db, user):
    return db.scalar(select(CulturalSession).where(CulturalSession.user_id == user.id)
                     .order_by(CulturalSession.created_at.desc(), CulturalSession.id.desc()).limit(1))


def reviewed_ids(db, user):
    return {str(row.entity_id) for row in db.scalars(select(CulturalFeedback).where(
        CulturalFeedback.user_id == user.id)) if row.preference or row.fashion_inspiration}


def seen_ids(db, user):
    return {str(value) for value in db.scalars(select(CulturalExposure.entity_id)
                                             .where(CulturalExposure.user_id == user.id))}


def interleave(domains):
    items, seen = [], set()
    for index in range(max([len(d['items']) for d in domains] or [0])):
        for domain in domains:
            for item in domain['items'][index:index + 1]:
                if item['entity_id'] not in seen:
                    seen.add(item['entity_id'])
                    items.append(dict(item, domain=domain['id']))
    return items


def mixed_queue(items, anchor=None):
    groups = [{'id': kind, 'items': [item for item in items if item.get('domain') == kind]}
              for kind in ('artist', 'movie', 'tv_show', 'book')]
    mixed = interleave(groups)
    selected = next((item for item in mixed if item['entity_id'] == str(anchor)), None)
    return [selected, *[item for item in mixed if item != selected]] if selected else mixed


def create_session(db, user, sources, fingerprint, result):
    domains = result.get('domains', [])
    hidden = seen_ids(db, user) | reviewed_ids(db, user)
    session = CulturalSession(id=uuid4(), user_id=user.id, data={
        'offered': {item['entity_id']: item for item in interleave(domains)},
        'queue': [item for item in interleave(domains) if item['entity_id'] not in hidden],
        'sources': sources, 'fingerprint': fingerprint, 'domains': domains,
        'offsets': {d['id']: d.get('next_offset', 8) for d in domains},
        'exhausted': {d['id']: d.get('exhausted', False) for d in domains},
        'choices_since_refresh': 0, 'batch_times': [], 'fetching_since': None,
    })
    db.add(session)
    db.flush()
    return session


def session_view(db, user, session=None):
    session = session or current_session(db, user)
    if not session:
        return None
    data = session.data
    hidden = reviewed_ids(db, user)
    return {'id': session.id, 'queue': [item for item in data.get('queue', []) if item['entity_id'] not in hidden],
            'domains': [{k: v for k, v in domain.items() if k != 'items'} for domain in data.get('domains', [])],
            'has_more': any(not value for value in data.get('exhausted', {}).values()),
            'choices_since_refresh': data.get('choices_since_refresh', 0),
            'fetching': bool(data.get('fetching_since') and
                datetime.fromisoformat(data['fetching_since']) > datetime.now(timezone.utc) - timedelta(minutes=2)),
            'created_at': session.created_at}


def owned(db, user, session_id):
    session = db.get(CulturalSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, 'Discovery session not found.')
    return session


def queued(session, entity_id):
    item = next((item for item in session.data.get('queue', []) if item['entity_id'] == str(entity_id)), None)
    if not item:
        raise HTTPException(404, 'This card is no longer in your discovery queue.')
    return item


def expose(db, user, session, item):
    existing = db.scalar(select(CulturalExposure).where(CulturalExposure.session_id == session.id,
                                                       CulturalExposure.entity_id == UUID(item['entity_id'])))
    if not existing:
        db.add(CulturalExposure(id=uuid4(), user_id=user.id, session_id=session.id,
                                entity_id=UUID(item['entity_id']), entity=item))


@router.post('/{session_id}/shown/{entity_id}')
def shown(session_id: UUID, entity_id: UUID, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    locked_profile(db, user)
    session = owned(db, user, session_id)
    expose(db, user, session, queued(session, entity_id))
    db.commit()
    return {'saved': True}


@router.post('/{session_id}/batch')
def next_batch(session_id: UUID, request: Request, category: Literal['artist', 'movie', 'tv_show', 'book'] | None = None,
               anchor: UUID | None = None,
               retry: bool = False,
               user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from .culture import inputs, discover, view
    locked_profile(db, user)
    session = owned(db, user, session_id)
    data = session.data
    data = {**data, 'offered': {**data.get('offered', {}), **{item['entity_id']: item for item in data.get('queue', [])}}}
    now = datetime.now(timezone.utc)
    if data.get('fetching_since') and datetime.fromisoformat(data['fetching_since']) > now - timedelta(minutes=2):
        raise HTTPException(409, 'The next discoveries are already loading.')
    times = [value for value in data.get('batch_times', []) if datetime.fromisoformat(value) > now - timedelta(minutes=1)]
    if len(times) >= 6:
        raise HTTPException(429, 'Pause a moment before loading more discoveries.', headers={'Retry-After': '60'})
    sources, fingerprint = inputs(db, user, request.app.state.settings)
    changed = fingerprint != data['fingerprint'] and (data.get('choices_since_refresh', 0) >= 5 or not data.get('queue'))
    if not changed and not retry and sum(not category or item['domain'] == category for item in data.get('queue', [])) > 6:
        return view(db, user, request.app.state.settings)
    if changed:
        sources['excluded_ids'] = sorted(seen_ids(db, user))[-100:]
        retained = data.get('queue', [])[:4]
        selected = next((item for item in data.get('queue', []) if item['entity_id'] == str(anchor)), None)
        if selected and selected not in retained:
            retained = [*retained, selected]
        data = {**data, 'sources': sources, 'fingerprint': fingerprint, 'offsets': {},
                'exhausted': {kind: False for kind in ('artist', 'movie', 'tv_show', 'book')}, 'choices_since_refresh': 0,
                'queue': retained}
    categories = [kind for kind, exhausted in data.get('exhausted', {}).items() if not exhausted and (not category or kind == category)]
    if retry:
        failed = {domain['id'] for domain in data.get('domains', []) if domain['status'] == 'unavailable'}
        categories = [kind for kind in categories if kind in failed]
    if not categories:
        return view(db, user, request.app.state.settings)
    session.data = {**data, 'fetching_since': now.isoformat(), 'batch_times': [*times, now.isoformat()]}
    db.commit()
    try:
        result = discover(request.app.state.qloo, request.app.state.settings, data['sources'],
                          offsets=data.get('offsets'), categories=categories, include_themes=False)
    except HTTPException:
        locked_profile(db, user)
        db.refresh(session)
        session.data = {**session.data, 'fetching_since': None}
        db.commit()
        raise
    # Feedback can arrive while the network call is in flight. Merge into the
    # current queue, never overwrite those committed choices with an old copy.
    locked_profile(db, user)
    db.refresh(session)
    current = session.data
    queue = current.get('queue', [])
    hidden = seen_ids(db, user) | reviewed_ids(db, user) | {item['entity_id'] for item in queue}
    new = [item for item in interleave(result.get('domains', [])) if item['entity_id'] not in hidden]
    offsets, exhausted = dict(current.get('offsets', {})), dict(current.get('exhausted', {}))
    domains = {d['id']: d for d in current.get('domains', [])}
    for domain in result.get('domains', []):
        domains[domain['id']] = domain
        if domain['status'] == 'ready':
            offsets[domain['id']] = domain['next_offset']
            exhausted[domain['id']] = domain['exhausted'] or domain['next_offset'] >= 480
    session.data = {**current, 'queue': mixed_queue([*queue, *new], anchor), 'domains': list(domains.values()),
                    'offered': {**current.get('offered', {}), **{item['entity_id']: item for item in queue},
                                **{item['entity_id']: item for item in interleave(result.get('domains', []))}},
                    'offsets': offsets, 'exhausted': exhausted, 'fetching_since': None}
    db.commit()
    return view(db, user, request.app.state.settings)


class Choice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: UUID
    action: Literal['like', 'dislike', 'known', 'fashion', 'skip']
    reference_image_ids: list[UUID] | None = Field(default=None, max_length=20)


def choice_data(row):
    return {'preference': row.preference if row else None, 'fashion_inspiration': bool(row.fashion_inspiration) if row else False,
            'reference_image_ids': list(row.reference_image_ids or []) if row else []}


def confirmed_references(db, user, ids):
    """Only the customer's own, currently saved images can establish a link."""
    unique = list(dict.fromkeys(ids))
    owned_ids = set(db.scalars(select(InspirationImage.id).where(
        InspirationImage.user_id == user.id, InspirationImage.id.in_(unique))))
    if not unique or set(unique) != owned_ids:
        raise HTTPException(422, 'Choose reference images from your current inspiration library.')
    return [str(value) for value in unique]


@router.post('/{session_id}/choices/{entity_id}')
def choose(session_id: UUID, entity_id: UUID, payload: Choice, request: Request,
           user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from .culture import view
    locked_profile(db, user)
    session = owned(db, user, session_id)
    event = db.get(CulturalEvent, payload.event_id)
    if event:
        if event.user_id != user.id or event.session_id != session.id or event.entity_id != entity_id or event.action != payload.action:
            raise HTTPException(409, 'This action identifier has already been used.')
        return {**view(db, user, request.app.state.settings), 'event_id': event.id}
    item = queued(session, entity_id)
    expose(db, user, session, item)
    row = db.get(CulturalFeedback, (user.id, entity_id))
    before = choice_data(row)
    after = dict(before)
    if payload.action in ('like', 'dislike', 'known'):
        after['preference'] = payload.action
        if payload.action != 'like':
            after['fashion_inspiration'] = False
    elif payload.action == 'fashion':
        after['fashion_inspiration'] = True
        if payload.reference_image_ids is not None:
            after['reference_image_ids'] = confirmed_references(db, user, payload.reference_image_ids)
        if after['preference'] in ('dislike', 'known'):
            after['preference'] = None
    if payload.action != 'skip':
        if not row:
            row = CulturalFeedback(user_id=user.id, entity_id=entity_id, entity=item)
            db.add(row)
        row.entity = item
        row.preference, row.fashion_inspiration = after['preference'], after['fashion_inspiration']
        row.reference_image_ids = after.get('reference_image_ids', []) if after['fashion_inspiration'] else []
    db.add(CulturalEvent(id=payload.event_id, user_id=user.id, session_id=session.id, entity_id=entity_id,
                        action=payload.action, created_at=datetime.now(timezone.utc), data={'before': before, 'after': after, 'entity': item}))
    session.data = {**session.data, 'queue': [i for i in session.data['queue'] if i['entity_id'] != str(entity_id)],
                    'choices_since_refresh': session.data.get('choices_since_refresh', 0) + (payload.action != 'skip')}
    db.commit()
    return {**view(db, user, request.app.state.settings), 'event_id': payload.event_id}


class Undo(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: UUID


@router.post('/{session_id}/undo/{target_id}')
def undo(session_id: UUID, target_id: UUID, payload: Undo, request: Request,
         user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from .culture import view
    locked_profile(db, user)
    session = owned(db, user, session_id)
    existing = db.get(CulturalEvent, payload.event_id)
    if existing:
        if existing.user_id != user.id or existing.session_id != session.id or existing.data.get('target_id') != str(target_id):
            raise HTTPException(409, 'This action identifier has already been used.')
        return view(db, user, request.app.state.settings)
    event = db.get(CulturalEvent, target_id)
    if not event or event.user_id != user.id or event.session_id != session.id or event.action == 'undo':
        raise HTTPException(404, 'Saved action not found.')
    newest = db.scalar(select(CulturalEvent).where(CulturalEvent.user_id == user.id)
                        .order_by(CulturalEvent.created_at.desc(), CulturalEvent.id.desc()).limit(1))
    if not newest or newest.id != event.id:
        raise HTTPException(409, 'Only your most recent choice can be undone.')
    row = db.get(CulturalFeedback, (user.id, event.entity_id))
    if row:
        row.preference = event.data['before']['preference']
        row.fashion_inspiration = event.data['before']['fashion_inspiration']
        row.reference_image_ids = event.data['before'].get('reference_image_ids', [])
    queue = [item for item in session.data['queue'] if item['entity_id'] != str(event.entity_id)]
    session.data = {**session.data, 'queue': [event.data['entity'], *queue]}
    db.add(CulturalEvent(id=payload.event_id, user_id=user.id, session_id=session.id, entity_id=event.entity_id,
                        action='undo', created_at=datetime.now(timezone.utc), data={'target_id': str(target_id), 'entity': event.data['entity'],
                                            'before': event.data['after'], 'after': event.data['before']}))
    db.commit()
    return view(db, user, request.app.state.settings)


class SyncAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: UUID
    entity_id: UUID
    action: Literal['shown', 'like', 'dislike', 'known', 'fashion', 'skip', 'undo']
    target_id: UUID | None = None
    reference_image_ids: list[UUID] | None = Field(default=None, max_length=20)


class SyncBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actions: list[SyncAction] = Field(min_length=1, max_length=50)


@router.post('/{session_id}/sync')
def sync_choices(session_id: UUID, payload: SyncBatch,
                 user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """One short transaction for a local outbox; no profile reconstruction or Qloo."""
    # The session's foreign keys already guarantee a profile exists. Acquire
    # the same owner lock as other mutations without an upsert/profile read.
    db.execute(select(UserProfile.id).where(UserProfile.id == user.id).with_for_update())
    session = owned(db, user, session_id)
    data = session.data
    offered = {**data.get('offered', {}), **{item['entity_id']: item for item in data.get('queue', [])}}
    # Older sessions did not retain an offered catalog.
    for domain in data.get('domains', []):
        for item in domain.get('items', []):
            offered.setdefault(item['entity_id'], dict(item, domain=domain['id']))
    ids = {action.entity_id for action in payload.actions}
    event_ids = {action.event_id for action in payload.actions} | {a.target_id for a in payload.actions if a.target_id}
    events = {row.id: row for row in db.scalars(select(CulturalEvent).where(CulturalEvent.id.in_(event_ids)))}
    rows = {row.entity_id: row for row in db.scalars(select(CulturalFeedback).where(
        CulturalFeedback.user_id == user.id, CulturalFeedback.entity_id.in_(ids)))}
    exposed = set(db.scalars(select(CulturalExposure.entity_id).where(
        CulturalExposure.session_id == session.id, CulturalExposure.entity_id.in_(ids))))
    latest = {}
    undo_entities = {a.entity_id for a in payload.actions if a.action == 'undo'}
    if undo_entities:
        for row in db.scalars(select(CulturalEvent).where(CulturalEvent.user_id == user.id,
                CulturalEvent.entity_id.in_(undo_entities), CulturalEvent.action != 'shown')
                .order_by(CulturalEvent.created_at.desc(), CulturalEvent.id.desc())):
            latest.setdefault(row.entity_id, row)
    queue = list(data.get('queue', []))
    choices = data.get('choices_since_refresh', 0)
    acked = []
    for action in payload.actions:
        existing = events.get(action.event_id)
        if existing:
            if (existing.user_id != user.id or existing.session_id != session.id or existing.entity_id != action.entity_id
                    or existing.action != action.action or existing.data.get('target_id') != (str(action.target_id) if action.target_id else None)
                    or existing.data.get('reference_image_ids') != ([str(value) for value in action.reference_image_ids] if action.reference_image_ids is not None else None)):
                raise HTTPException(409, 'This action identifier has already been used.')
            acked.append(str(action.event_id))
            continue
        item = offered.get(str(action.entity_id))
        if not item:
            raise HTTPException(404, 'This discovery was not offered in your session.')
        row = rows.get(action.entity_id)
        before = choice_data(row)
        after = dict(before)
        if action.action == 'undo':
            target = events.get(action.target_id)
            if (not target or target.user_id != user.id or target.session_id != session.id
                    or target.entity_id != action.entity_id or target.action in ('shown', 'undo')
                    or latest.get(action.entity_id) is not target):
                raise HTTPException(409, 'This choice has changed elsewhere. Sync needs attention.')
            after = dict(target.data['before'])
            queue = [item, *[other for other in queue if other['entity_id'] != str(action.entity_id)]]
            choices = max(0, choices - (target.action != 'skip'))
        elif action.action in ('like', 'dislike', 'known'):
            after['preference'] = action.action
            if action.action != 'like':
                after['fashion_inspiration'] = False
        elif action.action == 'fashion':
            after['fashion_inspiration'] = True
            if action.reference_image_ids is not None:
                after['reference_image_ids'] = confirmed_references(db, user, action.reference_image_ids)
            if after['preference'] in ('known', 'dislike'):
                after['preference'] = None
        if action.action not in ('shown', 'skip', 'undo'):
            queue = [other for other in queue if other['entity_id'] != str(action.entity_id)]
            choices += 1
        elif action.action == 'skip':
            queue = [other for other in queue if other['entity_id'] != str(action.entity_id)]
        if action.action not in ('shown', 'skip'):
            if not row:
                row = CulturalFeedback(user_id=user.id, entity_id=action.entity_id, entity=item)
                rows[action.entity_id] = row
                db.add(row)
            row.preference, row.fashion_inspiration, row.entity = after['preference'], after['fashion_inspiration'], item
            row.reference_image_ids = after.get('reference_image_ids', []) if after['fashion_inspiration'] else []
        if action.entity_id not in exposed:
            exposed.add(action.entity_id)
            db.add(CulturalExposure(id=uuid4(), user_id=user.id, session_id=session.id, entity_id=action.entity_id,
                                    entity=item, created_at=datetime.now(timezone.utc)))
        event = CulturalEvent(id=action.event_id, user_id=user.id, session_id=session.id, entity_id=action.entity_id,
                              action=action.action, created_at=datetime.now(timezone.utc), data={
                                  'before': before, 'after': after, 'entity': item,
                                  **({'reference_image_ids': [str(value) for value in action.reference_image_ids]} if action.reference_image_ids is not None else {}),
                                  **({'target_id': str(action.target_id)} if action.target_id else {})})
        db.add(event)
        events[action.event_id] = event
        if action.action != 'shown':
            latest[action.entity_id] = event
        acked.append(str(action.event_id))
    session.data = {**data, 'queue': queue, 'offered': offered, 'choices_since_refresh': choices}
    db.commit()
    return {'acked': acked, 'session_id': str(session.id), 'choices_since_refresh': choices}
