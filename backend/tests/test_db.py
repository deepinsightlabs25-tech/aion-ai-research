#!/usr/bin/env python3
"""
Test script to verify database connection and user creation.
"""
import os
import sys
sys.path.insert(0, 'src')

from src.db.postgres import db

def test_database():
    print("Testing database connection...")

    # Test table creation
    try:
        db.create_tables()
        print("✓ Tables created successfully")
    except Exception as e:
        print(f"✗ Failed to create tables: {e}")
        return False

    # Test user creation
    try:
        user = db.get_or_create_user(
            google_id="test_google_id_123",
            email="test@example.com",
            name="Test User"
        )
        print(f"✓ User created/updated successfully: {user.google_id}")
    except Exception as e:
        print(f"✗ Failed to create user: {e}")
        return False

    print("All database tests passed!")
    return True

if __name__ == "__main__":
    # Set a dummy DATABASE_URL for testing
    if not os.getenv("DATABASE_URL"):
        print("Please set DATABASE_URL environment variable")
        sys.exit(1)

    test_database()