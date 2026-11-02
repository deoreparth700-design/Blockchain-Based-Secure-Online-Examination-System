"""
tests/test_database_url.py
--------------------------
Unit tests for database URL normalization and psycopg v3 driver registration.
No active database connection or .env file required.
"""

import os
import sys
import unittest
import sqlalchemy

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from database import normalize_database_url


class TestDatabaseUrlNormalization(unittest.TestCase):
    def test_postgres_scheme_rewritten_to_psycopg(self):
        url = "postgres://user:pass@localhost:5432/db"
        expected = "postgresql+psycopg://user:pass@localhost:5432/db"
        self.assertEqual(normalize_database_url(url), expected)

    def test_postgresql_scheme_rewritten_to_psycopg(self):
        url = "postgresql://user:pass@localhost:5432/db"
        expected = "postgresql+psycopg://user:pass@localhost:5432/db"
        self.assertEqual(normalize_database_url(url), expected)

    def test_postgresql_psycopg_scheme_unchanged(self):
        url = "postgresql+psycopg://user:pass@localhost:5432/db"
        self.assertEqual(normalize_database_url(url), url)

    def test_sqlite_scheme_unchanged(self):
        url = "sqlite:///exam_system.db"
        self.assertEqual(normalize_database_url(url), url)

    def test_sqlite_memory_unchanged(self):
        url = "sqlite:///:memory:"
        self.assertEqual(normalize_database_url(url), url)

    def test_quotes_and_whitespace_stripped(self):
        raw = "  'postgres://user:pass@localhost:5432/db'  "
        expected = "postgresql+psycopg://user:pass@localhost:5432/db"
        self.assertEqual(normalize_database_url(raw), expected)

    def test_empty_or_none_url(self):
        self.assertIsNone(normalize_database_url(None))
        self.assertEqual(normalize_database_url(""), "")

    def test_create_engine_psycopg_lazy_initialization(self):
        normalized_url = normalize_database_url("postgresql://user:pass@localhost:5432/db")
        engine = sqlalchemy.create_engine(normalized_url)
        self.assertEqual(engine.dialect.name, "postgresql")
        self.assertEqual(engine.dialect.driver, "psycopg")
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
