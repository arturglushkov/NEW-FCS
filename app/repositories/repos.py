from __future__ import annotations
from datetime import datetime, date
from typing import Optional, Sequence
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import User, SiteObject, Shift, Task


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_by_telegram_id(self, tid: int) -> Optional[User]:
        r = await self.s.execute(select(User).where(User.telegram_id == tid))
        return r.scalar_one_or_none()

    async def get_by_id(self, uid: int) -> Optional[User]:
        return await self.s.get(User, uid)

    async def get_all_active(self) -> Sequence[User]:
        r = await self.s.execute(
            select(User).where(User.is_active == True).order_by(User.first_name)
        )
        return r.scalars().all()

    async def get_by_role(self, role: str) -> Sequence[User]:
        r = await self.s.execute(
            select(User).where(User.role == role, User.is_active == True).order_by(User.first_name)
        )
        return r.scalars().all()

    async def create(self, telegram_id: int, first_name: str,
                     last_name: Optional[str] = None,
                     username: Optional[str] = None,
                     role: str = "installer") -> User:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            telegram_username=username,
            role=role,
            is_active=True,
        )
        self.s.add(user)
        await self.s.flush()
        await self.s.refresh(user)
        return user

    async def save(self, user: User) -> User:
        self.s.add(user)
        await self.s.flush()
        await self.s.refresh(user)
        return user

    async def commit(self) -> None:
        await self.s.commit()


class ObjectRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_by_id(self, oid: int) -> Optional[SiteObject]:
        return await self.s.get(SiteObject, oid)

    async def get_active(self) -> Sequence[SiteObject]:
        r = await self.s.execute(
            select(SiteObject).where(SiteObject.status == "active").order_by(SiteObject.name)
        )
        return r.scalars().all()

    async def create(self, name: str, address: str, lat: float, lon: float,
                     client_name: Optional[str] = None,
                     object_type: str = "client",
                     created_by_id: Optional[int] = None,
                     notes: Optional[str] = None) -> SiteObject:
        obj = SiteObject(
            name=name, address=address, latitude=lat, longitude=lon,
            client_name=client_name, object_type=object_type,
            created_by_id=created_by_id, notes=notes,
            status="active",
        )
        self.s.add(obj)
        await self.s.commit()
        await self.s.refresh(obj)
        return obj

    async def save(self, obj: SiteObject) -> SiteObject:
        self.s.add(obj)
        await self.s.commit()
        await self.s.refresh(obj)
        return obj


class ShiftRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_active(self, employee_id: int) -> Optional[Shift]:
        r = await self.s.execute(
            select(Shift).where(
                Shift.employee_id == employee_id,
                Shift.status == "active",
            )
        )
        return r.scalar_one_or_none()

    async def get_by_id(self, sid: int) -> Optional[Shift]:
        return await self.s.get(Shift, sid)

    async def get_today_all(self) -> Sequence[Shift]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        r = await self.s.execute(
            select(Shift)
            .options(selectinload(Shift.employee), selectinload(Shift.site_object))
            .where(Shift.started_at >= today)
            .order_by(Shift.started_at.desc())
        )
        return r.scalars().all()

    async def get_by_employee(self, employee_id: int,
                               date_from: Optional[date] = None,
                               date_to: Optional[date] = None,
                               limit: int = 30) -> Sequence[Shift]:
        q = select(Shift).where(Shift.employee_id == employee_id)
        if date_from:
            q = q.where(Shift.started_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            q = q.where(Shift.started_at <= datetime.combine(date_to, datetime.max.time()))
        q = q.options(selectinload(Shift.site_object)).order_by(Shift.started_at.desc()).limit(limit)
        r = await self.s.execute(q)
        return r.scalars().all()

    async def start(self, employee_id: int, site_object_id: int,
                    lat: float, lon: float) -> Shift:
        shift = Shift(
            employee_id=employee_id,
            site_object_id=site_object_id,
            status="active",
            started_at=datetime.utcnow(),
            start_lat=lat,
            start_lon=lon,
        )
        self.s.add(shift)
        await self.s.commit()
        await self.s.refresh(shift)
        return shift

    async def end(self, shift: Shift, lat: float, lon: float) -> Shift:
        now = datetime.utcnow()
        shift.ended_at = now
        shift.end_lat = lat
        shift.end_lon = lon
        shift.status = "completed"
        hours = (now - shift.started_at).total_seconds() / 3600
        shift.total_hours = round(hours, 2)
        self.s.add(shift)
        await self.s.flush()
        return shift

    async def total_hours(self, employee_id: int,
                          date_from: date, date_to: date) -> float:
        r = await self.s.execute(
            select(func.sum(Shift.total_hours)).where(
                Shift.employee_id == employee_id,
                Shift.status == "completed",
                Shift.started_at >= datetime.combine(date_from, datetime.min.time()),
                Shift.started_at <= datetime.combine(date_to, datetime.max.time()),
            )
        )
        return float(r.scalar() or 0)


class TaskRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_by_id(self, tid: int) -> Optional[Task]:
        return await self.s.get(Task, tid)

    async def get_for_employee(self, employee_id: int) -> Sequence[Task]:
        r = await self.s.execute(
            select(Task)
            .where(Task.assignee_id == employee_id, Task.status == "pending")
            .order_by(Task.created_at.desc())
        )
        return r.scalars().all()

    async def get_all_created_by(self, creator_id: int) -> Sequence[Task]:
        r = await self.s.execute(
            select(Task)
            .where(Task.creator_id == creator_id)
            .order_by(Task.created_at.desc())
            .limit(20)
        )
        return r.scalars().all()

    async def create(self, title: str, creator_id: int,
                     assignee_id: int,
                     description: Optional[str] = None,
                     deadline: Optional[datetime] = None,
                     site_object_id: Optional[int] = None) -> Task:
        task = Task(
            title=title,
            description=description,
            creator_id=creator_id,
            assignee_id=assignee_id,
            deadline=deadline,
            site_object_id=site_object_id,
        )
        self.s.add(task)
        await self.s.commit()
        await self.s.refresh(task)
        return task

    async def complete(self, task: Task, report: Optional[str] = None) -> Task:
        task.status = "done"
        task.completed_at = datetime.utcnow()
        task.report = report
        self.s.add(task)
        await self.s.flush()
        return task
