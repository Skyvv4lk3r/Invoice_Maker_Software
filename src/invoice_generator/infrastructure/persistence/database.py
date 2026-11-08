from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, event


def create_database(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        URL.create("sqlite", database=str(path)),
        connect_args={"timeout": 10},
        hide_parameters=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        # Explicit BEGIN avoids sqlite3 legacy transaction surprises.
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    @event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    config = Config()
    location = str(Path(__file__).parent / "migrations")
    config.set_main_option("script_location", location.replace("%", "%%"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return engine
