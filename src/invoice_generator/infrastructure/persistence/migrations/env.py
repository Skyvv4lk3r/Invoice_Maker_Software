from alembic import context

from invoice_generator.infrastructure.persistence.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError(
        "Run migrations through create_database(), using the configured local database."
    )
context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
