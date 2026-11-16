from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DraftRecord(Base):
    __tablename__ = "invoice_draft"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditRecord(Base):
    __tablename__ = "audit_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(40), nullable=False)


class OwnerRecord(Base):
    __tablename__ = "workspace_owner"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    recovery_hash: Mapped[str] = mapped_column(Text, nullable=False)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[str] = mapped_column(String(40), nullable=False, default="0")


class WorkspaceRecord(Base):
    __tablename__ = "workspace_record"
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TemplateRecord(Base):
    __tablename__ = "template_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class InvoiceCounter(Base):
    __tablename__ = "invoice_counter"
    financial_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class IssuedRecord(Base):
    __tablename__ = "issued_invoice"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    financial_year: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class RenderJob(Base):
    __tablename__ = "render_job"
    invoice_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_name: Mapped[str] = mapped_column(Text, nullable=False)
