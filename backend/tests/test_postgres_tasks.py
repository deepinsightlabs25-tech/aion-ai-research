"""Tests for Postgres ``tasks`` persistence (research task_id + user + query)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.postgres import Base, Database, Task, User


def test_record_research_task_inserts_row():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    db = Database.__new__(Database)
    db.engine = engine
    db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db.record_research_task(
        "550e8400-e29b-41d4-a716-446655440000",
        "google-sub-1",
        "What is machine learning?",
        email="u@example.com",
        name="User One",
    )

    session = db.SessionLocal()
    try:
        tasks = session.query(Task).all()
        users = session.query(User).all()
        assert len(users) == 1
        assert users[0].google_id == "google-sub-1"
        assert len(tasks) == 1
        assert tasks[0].task_id == "550e8400-e29b-41d4-a716-446655440000"
        assert tasks[0].user_id == users[0].id
        assert tasks[0].user_query == "What is machine learning?"
    finally:
        session.close()
