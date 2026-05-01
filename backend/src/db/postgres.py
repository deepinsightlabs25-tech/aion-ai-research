import logging
import os
from contextlib import contextmanager
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

logger = logging.getLogger(__name__)

Base = declarative_base()


def _engine_connect_args(database_url: str) -> dict:
    try:
        host = (make_url(database_url).host or "").lower()
        if "supabase.co" in host or "pooler.supabase.com" in host:
            return {"sslmode": "require"}
    except Exception:
        pass
    return {}

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    name = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Database:
    def __init__(self):
        database_url = os.getenv("DATABASE_URL", "").strip() || "postgresql://postgres.urjlnpjvrqbfylrwxlfc:Gate%402026%403@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
        if not database_url:
            # For testing or when database is not configured
            self.engine = None
            self.SessionLocal = None
            return

        self.engine = create_engine(
            database_url,
            echo=False,
            connect_args=_engine_connect_args(database_url),
            pool_pre_ping=True,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _disable_connection(self) -> None:
        """Drop the engine so callers use the no-DB mock paths."""
        if self.engine is not None:
            self.engine.dispose()
        self.engine = None
        self.SessionLocal = None

    def create_tables(self) -> None:
        """Create all tables defined in the models.

        If Postgres is unreachable (e.g. Supabase direct host is IPv6-only on an IPv4-only
        network), logs a warning and disables SQL unless ``POSTGRES_STRICT_STARTUP`` is set.
        """
        if not self.engine:
            return
        strict = os.getenv("POSTGRES_STRICT_STARTUP", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Postgres schema ensured (create_all).")
        except OperationalError as e:
            logger.warning(
                "Postgres connection failed (%s). "
                "Supabase direct URLs often need IPv6 or the IPv4 add-on; use a pooler URI or "
                "enable IPv4 in Supabase. Continuing without SQL user persistence.",
                e.orig if getattr(e, "orig", None) else e,
            )
            self._disable_connection()
            if strict:
                raise

    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions."""
        if not self.engine:
            # For testing, return a mock session
            from unittest.mock import MagicMock
            mock_session = MagicMock()
            yield mock_session
            return

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_or_create_user(self, google_id: str, email: Optional[str] = None,
                          name: Optional[str] = None) -> User:
        """Get existing user or create new one, updating last_login."""
        if not self.engine:
            # For testing, return a mock user
            from unittest.mock import MagicMock
            mock_user = MagicMock()
            mock_user.google_id = google_id
            mock_user.email = email
            mock_user.name = name
            return mock_user

        with self.get_session() as session:
            user = session.query(User).filter(User.google_id == google_id).first()
            if user:
                # Update user info and last login
                user.email = email or user.email
                user.name = name or user.name
                user.last_login = func.now()
            else:
                # Create new user
                user = User(
                    google_id=google_id,
                    email=email,
                    name=name
                )
                session.add(user)
            session.commit()
            session.refresh(user)
            return user

# Global database instance
db = Database()