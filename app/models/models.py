"""
ORM Models — FCS Bot
Все поля используют String вместо Enum для совместимости с asyncpg.
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Float, Boolean, Text,
    DateTime, Date, BigInteger, Numeric,
    ForeignKey, Index, UniqueConstraint, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database.engine import Base


# Роли: owner / installer / workshop
# Статусы смены: active / completed
# Статусы задачи: pending / done
# Типы объектов: client / workshop


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── User ──────────────────────────────────────────────────────────

class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int]                      = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int]             = mapped_column(BigInteger, unique=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[str]              = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]]     = mapped_column(String(100))
    # owner / installer / workshop
    role: Mapped[str]                    = mapped_column(String(20), nullable=False, server_default="installer")
    is_active: Mapped[bool]              = mapped_column(Boolean, nullable=False, server_default="true")

    shifts: Mapped[List["Shift"]]        = relationship("Shift", back_populates="employee")
    tasks: Mapped[List["Task"]]          = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    created_tasks: Mapped[List["Task"]]  = relationship("Task", back_populates="creator", foreign_keys="Task.creator_id")

    __table_args__ = (
        Index("ix_users_telegram_id", "telegram_id"),
        Index("ix_users_role", "role"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name or ''}".strip()

    @property
    def role_badge(self) -> str:
        return {
            "owner": "👑 Владелец",
            "installer": "🔧 Инсталлер",
            "workshop": "🏭 Сотрудник цеха",
        }.get(self.role, self.role)


# ── Site Object ───────────────────────────────────────────────────

class SiteObject(TimestampMixin, Base):
    __tablename__ = "site_objects"

    id: Mapped[int]                      = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str]                    = mapped_column(String(200), nullable=False)
    address: Mapped[str]                 = mapped_column(String(500), nullable=False)
    client_name: Mapped[Optional[str]]   = mapped_column(String(200))
    latitude: Mapped[float]              = mapped_column(Float, nullable=False)
    longitude: Mapped[float]             = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int]           = mapped_column(Integer, nullable=False, server_default="150")
    # active / completed
    status: Mapped[str]                  = mapped_column(String(20), nullable=False, server_default="active")
    # client / workshop
    object_type: Mapped[str]             = mapped_column(String(20), nullable=False, server_default="client")
    notes: Mapped[Optional[str]]         = mapped_column(Text)
    created_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    shifts: Mapped[List["Shift"]] = relationship("Shift", back_populates="site_object")
    tasks: Mapped[List["Task"]]   = relationship("Task", back_populates="site_object")

    __table_args__ = (
        Index("ix_site_objects_status", "status"),
    )


# ── Shift ─────────────────────────────────────────────────────────

class Shift(TimestampMixin, Base):
    __tablename__ = "shifts"

    id: Mapped[int]                       = mapped_column(BigInteger, primary_key=True)
    employee_id: Mapped[int]              = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    site_object_id: Mapped[int]           = mapped_column(BigInteger, ForeignKey("site_objects.id", ondelete="CASCADE"), nullable=False)
    # active / completed
    status: Mapped[str]                   = mapped_column(String(20), nullable=False, server_default="active")
    started_at: Mapped[datetime]          = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True))
    total_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))

    start_lat: Mapped[Optional[float]]   = mapped_column(Float)
    start_lon: Mapped[Optional[float]]   = mapped_column(Float)
    end_lat: Mapped[Optional[float]]     = mapped_column(Float)
    end_lon: Mapped[Optional[float]]     = mapped_column(Float)

    # Telegram file_ids через запятую
    photos_before: Mapped[Optional[str]] = mapped_column(Text)
    photos_after: Mapped[Optional[str]]  = mapped_column(Text)

    notes: Mapped[Optional[str]]         = mapped_column(Text)

    employee: Mapped["User"]             = relationship("User", back_populates="shifts")
    site_object: Mapped["SiteObject"]    = relationship("SiteObject", back_populates="shifts")

    __table_args__ = (
        Index("ix_shifts_employee_id", "employee_id"),
        Index("ix_shifts_status", "status"),
        Index("ix_shifts_started_at", "started_at"),
    )


# ── Task ──────────────────────────────────────────────────────────

class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int]                          = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str]                       = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]]       = mapped_column(Text)
    creator_id: Mapped[int]                  = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignee_id: Mapped[Optional[int]]       = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    site_object_id: Mapped[Optional[int]]    = mapped_column(BigInteger, ForeignKey("site_objects.id", ondelete="SET NULL"))
    # pending / done
    status: Mapped[str]                      = mapped_column(String(20), nullable=False, server_default="pending")
    deadline: Mapped[Optional[datetime]]     = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    report: Mapped[Optional[str]]            = mapped_column(Text)

    creator: Mapped["User"]                  = relationship("User", back_populates="created_tasks", foreign_keys=[creator_id])
    assignee: Mapped[Optional["User"]]       = relationship("User", back_populates="tasks", foreign_keys=[assignee_id])
    site_object: Mapped[Optional["SiteObject"]] = relationship("SiteObject", back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_assignee_id", "assignee_id"),
        Index("ix_tasks_status", "status"),
    )
