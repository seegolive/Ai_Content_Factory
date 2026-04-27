"""Pytest configuration and shared fixtures."""
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@postgres:5432/ai_content_factory_test"
TEST_DATABASE_URL_SYNC = "postgresql://postgres:password@postgres:5432/ai_content_factory_test"


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables using a sync engine — once per session, no event loop conflict."""
    import app.models  # noqa: F401  — registers all ORM models
    engine = create_engine(TEST_DATABASE_URL_SYNC)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest_asyncio.fixture
async def db(setup_db) -> AsyncGenerator[AsyncSession, None]:
    """Fresh async session per test — own engine to avoid event loop sharing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        google_id=f"google_{uuid.uuid4().hex}",
        name="Test User",
        plan="free",
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_video_path(tmp_path) -> str:
    """Create a tiny test video file placeholder."""
    p = tmp_path / "test_video.mp4"
    p.write_bytes(b"\x00" * 1024)  # minimal placeholder
    return str(p)


@pytest_asyncio.fixture
async def test_video(db: AsyncSession, test_user: User):
    """A queued video owned by test_user."""
    from app.models.video import Video
    video = Video(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Test Video",
        status="queued",
        copyright_status="unchecked",
    )
    db.add(video)
    await db.commit()
    return video


@pytest_asyncio.fixture
async def test_clip(db: AsyncSession, test_video, test_user: User):
    """A pending clip belonging to test_video."""
    from app.models.clip import Clip
    clip = Clip(
        id=uuid.uuid4(),
        video_id=test_video.id,
        user_id=test_user.id,
        title="Test Clip",
        start_time=0.0,
        end_time=45.0,
        duration=45.0,
        viral_score=80,
        moment_type="clutch",
        hashtags=["gaming", "battlefield6"],
        format="vertical",
        qc_status="passed",
        review_status="pending",
        platform_status={},
        format_generated={},
    )
    db.add(clip)
    await db.commit()
    return clip
