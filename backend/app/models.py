from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid, Integer, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "muselly_user_profiles"

    # Supabase owns auth.users; this is the matching authenticated user ID.
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TasteProfile(Base):
    __tablename__ = "muselly_taste_profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_user_profiles.id", ondelete="CASCADE"), primary_key=True)
    selected_styles: Mapped[list[str]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TasteTest(Base):
    __tablename__ = "muselly_taste_tests"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_user_profiles.id", ondelete="CASCADE"), primary_key=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InspirationImage(Base):
    __tablename__ = "muselly_inspiration_images"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_taste_tests.user_id", ondelete="CASCADE"), index=True)
    storage_path: Mapped[str] = mapped_column(String(300), unique=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(30))
    size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TasteAnalysisRun(Base):
    __tablename__ = "muselly_taste_analysis_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_taste_tests.user_id", ondelete="CASCADE"), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    sources: Mapped[dict] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    usage: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TasteEnrichmentRun(Base):
    __tablename__ = "muselly_taste_enrichment_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_taste_tests.user_id", ondelete="CASCADE"), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    sources: Mapped[dict] = mapped_column(JSON)
    resolver_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TasteAffinityDismissal(Base):
    __tablename__ = "muselly_taste_affinity_dismissals"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("muselly_taste_tests.user_id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedProduct(Base):
    __tablename__ = 'muselly_saved_products'
    __table_args__ = (UniqueConstraint('user_id', 'url', name='uq_saved_product_owner_url'),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_user_profiles.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048))
    image: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductFeedback(Base):
    __tablename__ = 'muselly_product_feedback'
    __table_args__ = (UniqueConstraint('user_id', 'url', name='uq_product_feedback_owner_url'),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_user_profiles.id', ondelete='CASCADE'), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    kind: Mapped[str] = mapped_column(String(30))
    product: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CulturalDiscoveryRun(Base):
    __tablename__ = 'muselly_cultural_runs'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    sources: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CulturalFeedback(Base):
    __tablename__ = 'muselly_cultural_feedback'
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    entity: Mapped[dict] = mapped_column(JSON)
    preference: Mapped[str | None] = mapped_column(String(20))
    fashion_inspiration: Mapped[bool] = mapped_column(default=False)
    reference_image_ids: Mapped[list] = mapped_column(JSON, default=list)
    fashion_note: Mapped[str] = mapped_column(String(500), default='', server_default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ShoppingAgentSession(Base):
    __tablename__ = 'muselly_shopping_agent_sessions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    state: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CulturalSession(Base):
    __tablename__ = 'muselly_cultural_sessions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CulturalExposure(Base):
    __tablename__ = 'muselly_cultural_exposures'
    __table_args__ = (UniqueConstraint('session_id', 'entity_id', name='uq_cultural_exposure_session_entity'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), index=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_cultural_sessions.id', ondelete='CASCADE'))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    entity: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CulturalEvent(Base):
    __tablename__ = 'muselly_cultural_events'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('muselly_taste_tests.user_id', ondelete='CASCADE'), index=True)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey('muselly_cultural_sessions.id', ondelete='CASCADE'))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutfitLimit(Base):
    __tablename__ = 'muselly_outfit_limits'
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day: Mapped[str] = mapped_column(String(10))
    daily: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)


class GeneratedOutfit(Base):
    __tablename__ = 'muselly_outfits'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))
