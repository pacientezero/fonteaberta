from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

DEFAULT_DATABASE_URL = "postgresql://fonteaberta:fonteaberta@localhost:5432/fonteaberta"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


@contextmanager
def db_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_database_url(), row_factory=dict_row) as connection:
        yield connection
