"""Alembic-Umgebung.

Die Datenbank-URL kommt aus der Umgebungsvariablen ``JOURNAL_DB``; fehlt sie,
gilt der Wert aus ``alembic.ini``. Das Metadatum aus ``journal.schema`` ist
die Vergleichsbasis für die Autogenerate.
"""

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from journal.schema import metadata

config = context.config

if config.config_file_name is not None:
    from logging.config import fileConfig

    fileConfig(config.config_file_name)

_umgebung_url = os.environ.get("JOURNAL_DB")
if _umgebung_url:
    config.set_main_option("sqlalchemy.url", "sqlite:///" + _umgebung_url.replace("\\", "/"))

target_metadata = metadata


def run_migrations_offline() -> None:
    """Offline-Modus: SQL nach stdout, ohne Verbindung."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online-Modus: Migration gegen eine echte Verbindung."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
