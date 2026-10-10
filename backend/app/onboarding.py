"""Authenticated onboarding. No image analysis or inferred profile attributes."""
import base64
import binascii
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from uuid import UUID, uuid4
import warnings

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db
from .models import InspirationImage, TasteTest, UserProfile

QUESTIONS = json.loads((Path(__file__).resolve().parents[2] / 'shared/taste-questions.json').read_text())
BY_ID = {q['id']: q for q in QUESTIONS}
BUCKET = 'muselly-inspirations'
LIMIT = 10 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000
router = APIRouter(prefix='/api/onboarding', tags=['Taste test'])


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    choices: list[str] = Field(default_factory=list, max_length=20)
    other: str = Field(default='', max_length=300)
    text: list[str] = Field(default_factory=list, max_length=30)
    location: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def text_limits(self):
        self.text = list(dict.fromkeys(t.strip() for t in self.text if t.strip()))
        if any(len(t) > 100 for t in self.text):
            raise ValueError('Keep each name under 100 characters.')
        return self


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answers: dict[str, Answer] = Field(default_factory=dict)
    position: int = Field(default=0, ge=0, le=len(QUESTIONS))

    @model_validator(mode='after')
    def validate_answers(self):
        for key, answer in self.answers.items():
            q = BY_ID.get(key)
            if not q:
                raise ValueError('Unknown question.')
            allowed = {o['id'] for o in q['options']}
            if set(answer.choices) - allowed or len(answer.choices) != len(set(answer.choices)):
                raise ValueError(f'{key}: choose valid, unique options.')
            maximum = q.get('max', len(allowed)) if q['multi'] else 1
            if len(answer.choices) > maximum:
                raise ValueError(f'{key}: choose at most {maximum}.')
            if key == 'q15' and 'none' in answer.choices and len(answer.choices) > 1:
                raise ValueError('No strong dislikes cannot be combined with other dislikes.')
            if answer.other and 'other' not in answer.choices:
                raise ValueError(f'{key}: select Other before adding a custom answer.')
            if answer.location and key != 'q20':
                raise ValueError('Location is only supported for q20.')
            if answer.text and key not in ('q7', 'q8'):
                raise ValueError('Free-text names are only supported for music and inspirations.')
        return self


def required_errors(answers):
    errors = []
    for q in QUESTIONS:
        a = answers.get(q['id'], {})
        if (not q['optional'] and not a.get('choices')) or ('other' in a.get('choices', []) and not a.get('other', '').strip()):
            errors.append(q['id'])
    return errors


def locked_profile(db, user):
    """Serialize mutations per user, including first-draft creation and upload caps."""
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(UserProfile).values(id=user.id, email=user.email, display_name=user.display_name)
               .on_conflict_do_nothing(index_elements=[UserProfile.id]))
    db.execute(select(UserProfile).where(UserProfile.id == user.id).with_for_update())
    profile = db.get(TasteTest, user.id)
    if not profile:
        profile = TasteTest(user_id=user.id, answers={}, position=0)
        db.add(profile)
        db.flush()
    return profile


def images_for(db, user):
    return db.scalars(select(InspirationImage).where(InspirationImage.user_id == user.id).order_by(InspirationImage.created_at, InspirationImage.id)).all()


def image_data(image):
    return {key: getattr(image, key) for key in ('id', 'filename', 'content_type', 'size', 'width', 'height', 'created_at', 'updated_at')}


def profile_data(db, user, profile):
    return {'answers': profile.answers if profile else {}, 'position': profile.position if profile else 0,
            'completed_at': profile.completed_at if profile else None,
            'created_at': profile.created_at if profile else None, 'updated_at': profile.updated_at if profile else None,
            'images': [image_data(i) for i in images_for(db, user)]}


def storage(request, method, path, **kwargs):
    settings = request.app.state.settings
    key = settings.supabase_secret_key or settings.supabase_service_role_key
    if not key:
        raise HTTPException(503, 'Image storage is not configured. Please try again after setup.')
    if key.startswith('sb_publishable_') or key == settings.supabase_publishable_key:
        raise HTTPException(503, 'Private image storage needs the backend secret key, not the public key.')
    # Legacy anon keys are JWTs too; never mistake one for a service role.
    parts = key.split('.')
    if len(parts) == 3 and not key.startswith('sb_secret_'):
        try:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            raise HTTPException(503, 'The backend storage key is invalid. Configure a Supabase secret key.') from None
        if not isinstance(payload, dict) or payload.get('role') != 'service_role':
            raise HTTPException(503, 'Private image storage needs a secret or service_role key. The configured key is public/anon.')
    storage_headers = {'apikey': key}
    if not key.startswith('sb_secret_'):
        storage_headers['Authorization'] = f'Bearer {key}'
    try:
        response = request.app.state.storage_client.request(method,
            f'{settings.supabase_url.rstrip("/")}/storage/v1/{path}',
            headers={**storage_headers, **kwargs.pop('headers', {})},
            timeout=60, **kwargs)
    except httpx.RequestError:
        raise HTTPException(503, 'Image storage could not be reached. Please retry.') from None
    if response.is_error:
        raise HTTPException(503, 'Unable to save or retrieve this image. Please retry.')
    return response


@router.get('')
def get_draft(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_data(db, user, db.get(TasteTest, user.id))


@router.put('')
def save_draft(draft: Draft, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = locked_profile(db, user)
    answers = {key: value.model_dump() for key, value in draft.answers.items()}
    profile.answers, profile.position = answers, draft.position
    if profile.completed_at and required_errors(answers):
        profile.completed_at = None
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    return profile_data(db, user, profile)


@router.post('/complete')
def complete(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = locked_profile(db, user)
    errors = required_errors(profile.answers)
    if errors:
        raise HTTPException(422, f'Please finish the required answers: {", ".join(errors)}.')
    images = images_for(db, user)
    if not 5 <= len(images) <= 10:
        raise HTTPException(422, 'Upload between 5 and 10 images before finishing.')
    # Confirm durable objects still exist without downloading their contents.
    for image in images:
        storage(request, 'HEAD', f'object/authenticated/{BUCKET}/{image.storage_path}')
    profile.completed_at = profile.completed_at or datetime.now(timezone.utc)
    profile.position = len(QUESTIONS)
    db.commit()
    return profile_data(db, user, profile)


def verified_image(data, content_type, filename):
    if content_type not in ('image/jpeg', 'image/png', 'image/webp') or Path(filename).suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise HTTPException(422, 'Choose a JPG, JPEG, PNG, or WebP image.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if Image.MIME.get(image.format) != content_type or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Invalid or animated image.')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                image.load()
                width, height = image.size
                # Re-encode to remove EXIF/GPS and non-image payloads.
                output = BytesIO()
                image.convert('RGB' if content_type == 'image/jpeg' else 'RGBA').save(output,
                    format={'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}[content_type])
                clean = output.getvalue()
                if len(clean) > LIMIT:
                    raise HTTPException(422, 'This image is too large after processing. Choose a smaller image.')
                return clean, width, height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'This image is damaged or too large to decode. Choose another image.') from None


@router.put('/images/{image_id}')
async def upload_image(image_id: UUID, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    filename = request.headers.get('x-filename', 'image.jpg')
    try:
        from urllib.parse import unquote
        filename = Path(unquote(filename)).name[:200]
    except ValueError:
        raise HTTPException(422, 'Invalid filename.') from None
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > LIMIT:
            raise HTTPException(413, 'Each image must be 10 MB or smaller.')
    content_type = request.headers.get('content-type', '').split(';')[0]
    return await run_in_threadpool(persist_image, image_id, request, user, db, bytes(data), content_type, filename)


def persist_image(image_id, request, user, db, data, content_type, filename):
    clean, width, height = verified_image(data, content_type, filename)
    locked_profile(db, user)
    image = db.get(InspirationImage, image_id)
    if image and image.user_id != user.id:
        raise HTTPException(404, 'Image not found.')
    if not image and len(images_for(db, user)) >= 10:
        raise HTTPException(422, 'You can upload up to 10 images.')
    # Stable request ID makes retry idempotent; versioned paths keep replacements
    # from destroying the old file if upload or database persistence fails.
    path = f'{user.id}/{image_id}/{uuid4()}'
    storage(request, 'POST', f'object/{BUCKET}/{path}', content=clean, headers={'Content-Type': content_type})
    old_path = image.storage_path if image else None
    if not image:
        image = InspirationImage(id=image_id, user_id=user.id)
        db.add(image)
    image.storage_path, image.filename, image.content_type = path, filename, content_type
    image.size, image.width, image.height = len(clean), width, height
    image.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage(request, 'DELETE', f'object/{BUCKET}', json={'prefixes': [path]})
        raise
    if old_path:
        # Best effort cleanup: a failure does not turn a committed replacement
        # into an apparent failed upload. Orphans stay private.
        try:
            storage(request, 'DELETE', f'object/{BUCKET}', json={'prefixes': [old_path]})
        except HTTPException:
            pass
    return image_data(image)


def owned_image(db, image_id, user):
    image = db.scalar(select(InspirationImage).where(InspirationImage.id == image_id, InspirationImage.user_id == user.id))
    if not image:
        raise HTTPException(404, 'Image not found.')
    return image


@router.get('/images/{image_id}')
def read_image(image_id: UUID, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    image = owned_image(db, image_id, user)
    result = storage(request, 'GET', f'object/authenticated/{BUCKET}/{image.storage_path}')
    return Response(result.content, media_type=image.content_type, headers={'Cache-Control': 'no-store'})


@router.delete('/images/{image_id}')
def delete_image(image_id: UUID, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = locked_profile(db, user)
    image = owned_image(db, image_id, user)
    storage(request, 'DELETE', f'object/{BUCKET}', json={'prefixes': [image.storage_path]})
    db.delete(image)
    db.flush()
    if len(images_for(db, user)) < 5:
        profile.completed_at = None
    db.commit()
    return {'deleted': str(image_id)}
