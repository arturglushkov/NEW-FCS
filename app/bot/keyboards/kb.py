from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.models import SiteObject, User, Task


def kb_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Main menus ────────────────────────────────────────────────────

def kb_owner() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🟢 Начать смену"), KeyboardButton(text="🔴 Завершить смену"))
    b.row(KeyboardButton(text="👥 Сотрудники"), KeyboardButton(text="🏗 Объекты"))
    b.row(KeyboardButton(text="📋 Задачи"), KeyboardButton(text="📊 Отчёт за день"))
    b.row(KeyboardButton(text="⏱ Мои часы"), KeyboardButton(text="➕ Добавить объект"))
    b.row(KeyboardButton(text="➕ Добавить сотрудника"))
    return b.as_markup(resize_keyboard=True)


def kb_installer() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🟢 Начать смену"), KeyboardButton(text="🔴 Завершить смену"))
    b.row(KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏱ Мои часы"))
    return b.as_markup(resize_keyboard=True)


def kb_workshop() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🟢 Начать смену"), KeyboardButton(text="🔴 Завершить смену"))
    b.row(KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏱ Мои часы"))
    return b.as_markup(resize_keyboard=True)


def main_kb(role: str) -> ReplyKeyboardMarkup:
    if role == "owner":
        return kb_owner()
    elif role == "installer":
        return kb_installer()
    return kb_workshop()


# ── Location ──────────────────────────────────────────────────────

def kb_location() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(text="📍 Отправить геолокацию", request_location=True))
    b.add(KeyboardButton(text="❌ Отмена"))
    return b.as_markup(resize_keyboard=True, one_time_keyboard=True)


# ── Objects ───────────────────────────────────────────────────────

def kb_select_object(objects: Sequence) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for obj in objects:
        b.row(InlineKeyboardButton(
            text=f"🏗 {obj.name}",
            callback_data=f"obj:{obj.id}",
        ))
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return b.as_markup()


def kb_objects_manage(objects: Sequence) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for obj in objects:
        status = "✅" if obj.status == "active" else "🔴"
        b.row(InlineKeyboardButton(
            text=f"{status} {obj.name}",
            callback_data=f"obj_manage:{obj.id}",
        ))
    return b.as_markup()


def kb_object_actions(obj_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle = "🔴 Закрыть объект" if is_active else "✅ Открыть объект"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data=f"obj_toggle:{obj_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_objects")],
    ])


# ── Employees ─────────────────────────────────────────────────────

def kb_employees(employees: Sequence) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for emp in employees:
        b.row(InlineKeyboardButton(
            text=f"👤 {emp.full_name} ({emp.role_badge})",
            callback_data=f"emp:{emp.id}",
        ))
    return b.as_markup()


def kb_employee_actions(emp_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Дать задачу", callback_data=f"emp_task:{emp_id}")],
        [InlineKeyboardButton(text="⏱ Часы сегодня", callback_data=f"emp_hours:{emp_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_employees")],
    ])


def kb_roles() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Инсталлер", callback_data="role:installer")],
        [InlineKeyboardButton(text="🏭 Сотрудник цеха", callback_data="role:workshop")],
        [InlineKeyboardButton(text="👑 Владелец", callback_data="role:owner")],
    ])


# ── Tasks ─────────────────────────────────────────────────────────

def kb_tasks(tasks: Sequence) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in tasks:
        b.row(InlineKeyboardButton(
            text=f"📋 {t.title[:40]}",
            callback_data=f"task:{t.id}",
        ))
    return b.as_markup()


def kb_task_actions(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено (без отчёта)", callback_data=f"task_done:{task_id}")],
        [InlineKeyboardButton(text="📝 Выполнено + отчёт", callback_data=f"task_report:{task_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_tasks")],
    ])


def kb_my_tasks_owner(tasks: Sequence) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in tasks:
        status = "✅" if t.status == "done" else "⏳"
        b.row(InlineKeyboardButton(
            text=f"{status} {t.title[:40]}",
            callback_data=f"task:{t.id}",
        ))
    return b.as_markup()


# ── Confirm ───────────────────────────────────────────────────────

def kb_confirm(yes_cb: str, no_cb: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_cb),
    ]])


def kb_back(cb: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Назад", callback_data=cb),
    ]])


# ── Photo ─────────────────────────────────────────────────────────

def kb_skip() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_photo"),
    ]])
