"""FCS Bot handlers"""
from __future__ import annotations
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ContentType, BufferedInputFile
from app.core.database.engine import async_session_factory
from app.core.config.settings import settings
from app.repositories.repos import UserRepo, ObjectRepo, ShiftRepo, TaskRepo
from app.utils.geo import check_location
from app.bot.keyboards.kb import (
    kb_remove, main_kb, kb_location, kb_select_object,
    kb_objects_manage, kb_object_actions, kb_employees,
    kb_employee_actions, kb_tasks, kb_task_actions,
    kb_my_tasks_owner, kb_back,
)
logger = logging.getLogger(__name__)
router = Router()

class Reg(StatesGroup):
    first_name = State()
    last_name = State()

class AddObject(StatesGroup):
    name = State()
    address = State()
    lat = State()
    lon = State()
    client = State()

class ShiftFlow(StatesGroup):
    pick_object = State()
    geo_start = State()
    photo_before = State()
    geo_end = State()
    photo_after = State()
    punch_list = State()
    notes = State()

class TaskCreate(StatesGroup):
    title = State()
    description = State()

class TaskComplete(StatesGroup):
    report = State()

async def get_user(telegram_id: int):
    async with async_session_factory() as s:
        await s.commit()  # ensure clean state
        return await UserRepo(s).get_by_telegram_id(telegram_id)

async def notify_owner(bot: Bot, text: str) -> None:
    try:
        await bot.send_message(settings.OWNER_TELEGRAM_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Owner notify failed: {e}")

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👋 С возвращением, <b>{user.full_name}</b>!\n{user.role_badge}",
            parse_mode="HTML", reply_markup=main_kb(user.role))
        return
    await message.answer("👋 Привет! Я бот FCS.\n\nВведи своё <b>имя</b>:", parse_mode="HTML", reply_markup=kb_remove())
    await state.set_state(Reg.first_name)

@router.message(Reg.first_name)
async def reg_first_name(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Введи имя (минимум 2 символа):")
        return
    await state.update_data(first_name=message.text.strip())
    await message.answer("Теперь введи <b>фамилию</b>:", parse_mode="HTML")
    await state.set_state(Reg.last_name)

@router.message(Reg.last_name)
async def reg_last_name(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Введи фамилию (минимум 2 символа):")
        return
    data = await state.get_data()
    first_name = data["first_name"]
    last_name = message.text.strip()
    from app.models.models import User as UserModel
    async with async_session_factory() as s:
        repo = UserRepo(s)
        user = await repo.get_by_telegram_id(message.from_user.id)
        if user:
            user.first_name = first_name
            user.last_name = last_name
            s.add(user)
        else:
            user = UserModel(
                telegram_id=message.from_user.id,
                first_name=first_name,
                last_name=last_name,
                telegram_username=message.from_user.username,
                role="installer",
                is_active=True,
            )
            s.add(user)
        await s.commit()
        await s.refresh(user)
        full_name = user.full_name
        role = user.role
        role_badge = user.role_badge
    await state.clear()
    await message.answer(
        f"✅ Готово, <b>{full_name}</b>!\n{role_badge}",
        parse_mode="HTML", reply_markup=main_kb(role))
    await notify_owner(message.bot, f"👤 Новый сотрудник:\n<b>{full_name}</b>\n@{message.from_user.username or chr(8212)}")

@router.message(F.text == "🟢 Начать смену")
async def shift_start(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся /start")
        return
    async with async_session_factory() as s:
        active = await ShiftRepo(s).get_active(user.id)
        if active:
            await message.answer("⚠️ У тебя уже есть активная смена!")
            return
        objects = await ObjectRepo(s).get_active()
    if not objects:
        await message.answer("❌ Нет активных объектов. Обратись к владельцу.")
        return
    await state.set_state(ShiftFlow.pick_object)
    await state.update_data(user_id=user.id, role=user.role)
    await message.answer("🏗 <b>Выбери объект:</b>", parse_mode="HTML", reply_markup=kb_select_object(objects))

@router.callback_query(ShiftFlow.pick_object, F.data.startswith("obj:"))
async def shift_pick_object(callback: CallbackQuery, state: FSMContext) -> None:
    obj_id = int(callback.data.split(":")[1])
    await state.update_data(obj_id=obj_id)
    await state.set_state(ShiftFlow.geo_start)
    await callback.message.edit_text("📍 Отправь геолокацию чтобы начать смену:")
    await callback.message.answer("👇", reply_markup=kb_location())
    await callback.answer()

@router.message(ShiftFlow.geo_start, F.content_type == ContentType.LOCATION)
async def shift_geo_start(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lat, lon = message.location.latitude, message.location.longitude
    async with async_session_factory() as s:
        obj = await ObjectRepo(s).get_by_id(data["obj_id"])
    ok, dist = check_location(lat, lon, obj.latitude, obj.longitude, obj.radius_meters)
    if not ok:
        await message.answer(
            f"❌ Ты в {dist}м от объекта.\nДопустимый радиус: {obj.radius_meters}м.\nПодойди ближе.",
            reply_markup=kb_location())
        return
    async with async_session_factory() as s:
        user = await UserRepo(s).get_by_telegram_id(message.from_user.id)
        shift = await ShiftRepo(s).start(user.id, obj.id, lat, lon)
        await s.commit()
        shift_id = shift.id
        started_at = shift.started_at
    await state.update_data(shift_id=shift_id)
    if data.get("role") == "installer":
        await state.set_state(ShiftFlow.photo_before)
        await message.answer(
            f"✅ Геолокация подтверждена ({dist}м).\n\n📸 <b>Фото объекта ДО начала работ:</b>",
            parse_mode="HTML", reply_markup=kb_remove())
    else:
        await state.clear()
        await message.answer(
            f"✅ <b>Смена начата!</b>\n\n🏗 {obj.name}\n⏰ {shift.started_at.strftime('%H:%M')}",
            parse_mode="HTML", reply_markup=main_kb(data.get("role", "workshop")))
        await notify_owner(message.bot, f"🟢 <b>{user.full_name}</b> начал смену\n📍 {obj.name}\n⏰ {shift.started_at.strftime('%H:%M')}")

@router.message(ShiftFlow.photo_before, F.photo)
async def shift_photo_before(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    async with async_session_factory() as s:
        shift = await ShiftRepo(s).get_by_id(data["shift_id"])
        shift.photos_before = file_id
        s.add(shift)
        obj = await ObjectRepo(s).get_by_id(shift.site_object_id)
    user = await get_user(message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ <b>Смена начата!</b>\n\n🏗 {obj.name}\n⏰ {shift.started_at.strftime('%H:%M')}\n📸 Фото ДО сохранено",
        parse_mode="HTML", reply_markup=main_kb(user.role))
    await notify_owner(message.bot, f"🟢 <b>{user.full_name}</b> начал смену\n📍 {obj.name}\n⏰ {shift.started_at.strftime('%H:%M')}")

@router.message(F.text == "🔴 Завершить смену")
async def shift_end(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся /start")
        return
    async with async_session_factory() as s:
        active = await ShiftRepo(s).get_active(user.id)
        if not active:
            await message.answer("❌ У тебя нет активной смены.", reply_markup=main_kb(user.role))
            return
        obj = await ObjectRepo(s).get_by_id(active.site_object_id)
    elapsed = (datetime.utcnow() - active.started_at).total_seconds() / 3600
    await state.set_state(ShiftFlow.geo_end)
    await state.update_data(shift_id=active.id, role=user.role, obj_id=active.site_object_id)
    await message.answer(
        f"⏱ <b>Завершить смену?</b>\n\n🏗 {obj.name}\nНачало: {active.started_at.strftime('%H:%M')}\nПрошло: {elapsed:.1f} ч.\n\n📍 Отправь геолокацию:",
        parse_mode="HTML", reply_markup=kb_location())

@router.message(ShiftFlow.geo_end, F.content_type == ContentType.LOCATION)
async def shift_geo_end(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lat, lon = message.location.latitude, message.location.longitude
    async with async_session_factory() as s:
        obj = await ObjectRepo(s).get_by_id(data["obj_id"])
    ok, dist = check_location(lat, lon, obj.latitude, obj.longitude, obj.radius_meters + 200)
    if not ok:
        await message.answer(f"❌ Ты в {dist}м от объекта. Подойди ближе.", reply_markup=kb_location())
        return
    async with async_session_factory() as s:
        shift = await ShiftRepo(s).get_by_id(data["shift_id"])
        shift = await ShiftRepo(s).end(shift, lat, lon)
    # Все роли обязаны отправить фото после работы
    await state.set_state(ShiftFlow.photo_after)
    await message.answer(
        "✅ Геолокация подтверждена.\n\n"
        "📸 <b>Отправь фото выполненной работы:</b>\n"
        "(обязательно)",
        parse_mode="HTML", reply_markup=kb_remove())

@router.message(ShiftFlow.photo_after, F.photo)
async def shift_photo_after(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with async_session_factory() as s:
        shift = await ShiftRepo(s).get_by_id(data["shift_id"])
        shift.photos_after = message.photo[-1].file_id
        s.add(shift)
        await s.commit()
    await state.set_state(ShiftFlow.punch_list)
    await message.answer(
        "✅ Фото сохранено!\n\n"
        "📋 <b>Punch List</b> — опиши что было сделано:\n"
        "• Что установлено\n"
        "• Что осталось\n"
        "• Проблемы если были\n\n"
        "(или /skip)",
        parse_mode="HTML")

@router.message(ShiftFlow.punch_list, F.text)
async def shift_punch_list(message: Message, state: FSMContext) -> None:
    notes = None if message.text == "/skip" else message.text
    await _finish_shift(message, state, notes)

@router.message(ShiftFlow.notes)
async def shift_notes(message: Message, state: FSMContext) -> None:
    notes = None if message.text == "/skip" else message.text
    await _finish_shift(message, state, notes)

@router.message(Command("skip"))
async def skip_cmd(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current == ShiftFlow.notes.state:
        await _finish_shift(message, state, None)
    elif current == ShiftFlow.punch_list.state:
        await _finish_shift(message, state, None)
    elif current == AddObject.client.state:
        await add_object_client(message, state)
    elif current == TaskCreate.description.state:
        await task_description(message, state)

async def _finish_shift(message, state, notes):
    data = await state.get_data()
    if not data.get("shift_id"):
        return
    async with async_session_factory() as s:
        shift = await ShiftRepo(s).get_by_id(data["shift_id"])
        if notes:
            shift.notes = notes
            s.add(shift)
        obj = await ObjectRepo(s).get_by_id(shift.site_object_id)
    await state.clear()
    user = await get_user(message.from_user.id)
    async with async_session_factory() as s:
        shift = await ShiftRepo(s).get_by_id(data["shift_id"])
    # Считаем часы за сегодня
    today = date.today()
    async with async_session_factory() as s:
        hours_today = await ShiftRepo(s).total_hours(user.id, today, today)
        hours_week = await ShiftRepo(s).total_hours(
            user.id, today - timedelta(days=today.weekday()), today
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb_after = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📊 Часы за неделю", callback_data="hours_week_after")
    ]])

    punch_text = f"\n📋 Punch list: {notes}" if notes else ""
    await message.answer(
        f"✅ <b>Смена завершена!</b>\n\n"
        f"🏗 {obj.name}\n"
        f"⏰ {shift.started_at.strftime('%H:%M')} → {shift.ended_at.strftime('%H:%M')}\n"
        f"⏱ Смена: <b>{float(shift.total_hours):.1f} ч.</b>\n"
        f"📅 Сегодня итого: <b>{hours_today:.1f} ч.</b>"
        f"{punch_text}",
        parse_mode="HTML",
        reply_markup=main_kb(user.role))
    await message.answer("Хочешь посмотреть часы за неделю?", reply_markup=kb_after)
    await notify_owner(message.bot,
        f"🔴 <b>{user.full_name}</b> завершил смену\n📍 {obj.name}\n"
        f"⏱ {float(shift.total_hours):.1f} ч.\n"
        f"{'📸 Фото: ✅' if shift.photos_after else '📸 Фото: —'}"
        f"{punch_text}")

@router.message(F.text == "📋 Мои задачи")
async def my_tasks(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся /start")
        return
    if user.role == "owner":
        async with async_session_factory() as s:
            tasks = await TaskRepo(s).get_all_created_by(user.id)
        if not tasks:
            await message.answer("📋 Нет созданных задач.", reply_markup=main_kb(user.role))
            return
        await message.answer(f"📋 <b>Задачи ({len(tasks)}):</b>", parse_mode="HTML", reply_markup=kb_my_tasks_owner(tasks))
        return
    async with async_session_factory() as s:
        tasks = await TaskRepo(s).get_for_employee(user.id)
    if not tasks:
        await message.answer("📋 Нет активных задач!", reply_markup=main_kb(user.role))
        return
    await message.answer(f"📋 <b>Твои задачи ({len(tasks)}):</b>", parse_mode="HTML", reply_markup=kb_tasks(tasks))

@router.callback_query(F.data.startswith("task:"))
async def task_view(callback: CallbackQuery) -> None:
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as s:
        task = await TaskRepo(s).get_by_id(task_id)
    if not task:
        await callback.answer("Задача не найдена")
        return
    deadline = task.deadline.strftime("%d.%m %H:%M") if task.deadline else "Не указан"
    await callback.message.edit_text(
        f"📋 <b>{task.title}</b>\n\n{task.description or ''}\n\nДедлайн: {deadline}",
        parse_mode="HTML", reply_markup=kb_task_actions(task.id))
    await callback.answer()

@router.callback_query(F.data.startswith("task_done:"))
async def task_done(callback: CallbackQuery) -> None:
    task_id = int(callback.data.split(":")[1])
    user = await get_user(callback.from_user.id)
    async with async_session_factory() as s:
        task = await TaskRepo(s).get_by_id(task_id)
        await TaskRepo(s).complete(task)
    await callback.message.edit_text("✅ Задача выполнена!")
    await callback.answer()
    await notify_owner(callback.bot, f"✅ <b>{user.full_name}</b> выполнил:\n<b>{task.title}</b>")

@router.callback_query(F.data.startswith("task_report:"))
async def task_report_start(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.split(":")[1])
    await state.set_state(TaskComplete.report)
    await state.update_data(task_id=task_id)
    await callback.message.edit_text("📝 Напиши отчёт о выполнении:")
    await callback.answer()

@router.message(TaskComplete.report)
async def task_report_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user = await get_user(message.from_user.id)
    async with async_session_factory() as s:
        task = await TaskRepo(s).get_by_id(data["task_id"])
        await TaskRepo(s).complete(task, report=message.text)
    await state.clear()
    await message.answer("✅ Задача выполнена! Отчёт сохранён.", reply_markup=main_kb(user.role))
    await notify_owner(message.bot, f"✅ <b>{user.full_name}</b> выполнил:\n<b>{task.title}</b>\n\nОтчёт: {message.text}")

@router.message(F.text == "⏱ Мои часы")
async def my_hours(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся /start")
        return
    today = date.today()
    async with async_session_factory() as s:
        repo = ShiftRepo(s)
        ht = await repo.total_hours(user.id, today, today)
        hw = await repo.total_hours(user.id, today - timedelta(days=today.weekday()), today)
        hm = await repo.total_hours(user.id, today.replace(day=1), today)
        shifts = await repo.get_by_employee(user.id, today - timedelta(days=7), today, limit=5)
    lines = ""
    for sh in shifts:
        h = float(sh.total_hours or 0)
        name = sh.site_object.name if sh.site_object else "—"
        lines += f"\n• {sh.started_at.strftime('%d.%m')} — {name} — {h:.1f} ч."
    await message.answer(
        f"⏱ <b>Мои часы</b>\n\nСегодня: <b>{ht:.1f} ч.</b>\nНеделя: <b>{hw:.1f} ч.</b>\nМесяц: <b>{hm:.1f} ч.</b>\n\nПоследние смены:{lines or ' —'}",
        parse_mode="HTML", reply_markup=main_kb(user.role))

@router.message(F.text == "🏗 Объекты")
async def objects_list(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or user.role != "owner":
        await message.answer("❌ Нет доступа.")
        return
    async with async_session_factory() as s:
        objects = await ObjectRepo(s).get_active()
    if not objects:
        await message.answer("Нет объектов.", reply_markup=main_kb(user.role))
        return
    await message.answer(f"🏗 <b>Объекты ({len(objects)}):</b>", parse_mode="HTML", reply_markup=kb_objects_manage(objects))

@router.callback_query(F.data.startswith("obj_manage:"))
async def object_manage(callback: CallbackQuery) -> None:
    obj_id = int(callback.data.split(":")[1])
    async with async_session_factory() as s:
        obj = await ObjectRepo(s).get_by_id(obj_id)
    await callback.message.edit_text(
        f"🏗 <b>{obj.name}</b>\n\nАдрес: {obj.address}\nКлиент: {obj.client_name or '—'}\nСтатус: {'✅ Активный' if obj.status == 'active' else '🔴 Закрыт'}",
        parse_mode="HTML", reply_markup=kb_object_actions(obj.id, obj.status == "active"))
    await callback.answer()

@router.callback_query(F.data.startswith("obj_toggle:"))
async def object_toggle(callback: CallbackQuery) -> None:
    obj_id = int(callback.data.split(":")[1])
    async with async_session_factory() as s:
        obj = await ObjectRepo(s).get_by_id(obj_id)
        obj.status = "completed" if obj.status == "active" else "active"
        await ObjectRepo(s).save(obj)
    await callback.message.edit_text(f"✅ Статус <b>{obj.name}</b>: {'Активный' if obj.status == 'active' else 'Закрыт'}", parse_mode="HTML")
    await callback.answer()

@router.message(F.text == "➕ Добавить объект")
async def add_object_start(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    if not user or user.role != "owner":
        await message.answer("❌ Нет доступа.")
        return
    await state.set_state(AddObject.name)
    await message.answer("🏗 <b>Название объекта</b>\nПример: Кухня — Смирновы:", parse_mode="HTML", reply_markup=kb_remove())

@router.message(AddObject.name)
async def add_object_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await message.answer("📍 <b>Адрес объекта:</b>", parse_mode="HTML")
    await state.set_state(AddObject.address)

@router.message(AddObject.address)
async def add_object_address(message: Message, state: FSMContext) -> None:
    await state.update_data(address=message.text.strip())
    await message.answer(
        "🌐 <b>Широта (latitude)</b>\nОткрой Google Maps → нажми на точку → скопируй первое число.\nПример: <code>25.9950</code>",
        parse_mode="HTML")
    await state.set_state(AddObject.lat)

@router.message(AddObject.lat)
async def add_object_lat(message: Message, state: FSMContext) -> None:
    try:
        lat = float(message.text.strip().replace(",", "."))
        await state.update_data(lat=lat)
        await message.answer("🌐 <b>Долгота (longitude)</b>\nПример: <code>-80.1426</code>", parse_mode="HTML")
        await state.set_state(AddObject.lon)
    except ValueError:
        await message.answer("❌ Введи число. Пример: 25.9950")

@router.message(AddObject.lon)
async def add_object_lon(message: Message, state: FSMContext) -> None:
    try:
        lon = float(message.text.strip().replace(",", "."))
        await state.update_data(lon=lon)
        await message.answer("👤 <b>Имя клиента</b> (или /skip):", parse_mode="HTML")
        await state.set_state(AddObject.client)
    except ValueError:
        await message.answer("❌ Введи число. Пример: -80.1426")

@router.message(AddObject.client, F.text)
async def add_object_client(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    client = None if message.text == "/skip" else message.text.strip()
    user = await get_user(message.from_user.id)
    async with async_session_factory() as s:
        repo = ObjectRepo(s)
        obj = await repo.create(name=data["name"], address=data["address"], lat=data["lat"], lon=data["lon"], client_name=client, created_by_id=user.id)
        obj_name = obj.name
        obj_address = obj.address
        obj_client = obj.client_name
    await state.clear()
    await message.answer(
        f"✅ <b>Объект создан!</b>\n\n🏗 {obj_name}\n📍 {obj_address}\n👤 {obj_client or '—'}",
        parse_mode="HTML", reply_markup=main_kb(user.role))

@router.message(F.text == "👥 Сотрудники")
async def employees_list(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or user.role != "owner":
        await message.answer("❌ Нет доступа.")
        return
    async with async_session_factory() as s:
        employees = await UserRepo(s).get_all_active()
    if not employees:
        await message.answer("Нет сотрудников.", reply_markup=main_kb(user.role))
        return
    await message.answer(f"👥 <b>Сотрудники ({len(employees)}):</b>", parse_mode="HTML", reply_markup=kb_employees(employees))

@router.callback_query(F.data.startswith("emp:"))
async def emp_view(callback: CallbackQuery) -> None:
    emp_id = int(callback.data.split(":")[1])
    today = date.today()
    async with async_session_factory() as s:
        emp = await UserRepo(s).get_by_id(emp_id)
        hours = await ShiftRepo(s).total_hours(emp_id, today, today)
        active = await ShiftRepo(s).get_active(emp_id)
    status = "🟢 На смене" if active else "⚫️ Не работает"
    await callback.message.edit_text(
        f"👤 <b>{emp.full_name}</b>\n{emp.role_badge}\n\nСтатус: {status}\nЧасов сегодня: {hours:.1f} ч.",
        parse_mode="HTML", reply_markup=kb_employee_actions(emp_id))
    await callback.answer()

@router.callback_query(F.data.startswith("emp_hours:"))
async def emp_hours(callback: CallbackQuery) -> None:
    emp_id = int(callback.data.split(":")[1])
    today = date.today()
    async with async_session_factory() as s:
        emp = await UserRepo(s).get_by_id(emp_id)
        ht = await ShiftRepo(s).total_hours(emp_id, today, today)
        hw = await ShiftRepo(s).total_hours(emp_id, today - timedelta(days=today.weekday()), today)
        shifts = await ShiftRepo(s).get_by_employee(emp_id, today - timedelta(days=6), today, limit=7)
    lines = ""
    for sh in shifts:
        lines += f"\n• {sh.started_at.strftime('%d.%m')} — {float(sh.total_hours or 0):.1f} ч."
    await callback.message.edit_text(
        f"⏱ <b>{emp.full_name}</b>\n\nСегодня: {ht:.1f} ч.\nНеделя: {hw:.1f} ч.\n\nПоследние смены:{lines or ' —'}",
        parse_mode="HTML", reply_markup=kb_back("back_employees"))
    await callback.answer()

@router.callback_query(F.data.startswith("emp_task:"))
async def emp_task_start(callback: CallbackQuery, state: FSMContext) -> None:
    emp_id = int(callback.data.split(":")[1])
    await state.set_state(TaskCreate.title)
    await state.update_data(assignee_id=emp_id)
    async with async_session_factory() as s:
        emp = await UserRepo(s).get_by_id(emp_id)
    await callback.message.edit_text(f"📋 Задача для <b>{emp.full_name}</b>\n\nВведи <b>название</b>:", parse_mode="HTML")
    await callback.answer()

@router.message(TaskCreate.title)
async def task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await message.answer("📝 Описание (или /skip):")
    await state.set_state(TaskCreate.description)

@router.message(TaskCreate.description, F.text)
async def task_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    description = None if message.text == "/skip" else message.text.strip()
    user = await get_user(message.from_user.id)
    async with async_session_factory() as s:
        task = await TaskRepo(s).create(title=data["title"], creator_id=user.id, assignee_id=data["assignee_id"], description=description)
        assignee = await UserRepo(s).get_by_id(data["assignee_id"])
    await state.clear()
    await message.answer(f"✅ Задача создана!\n\n<b>{task.title}</b>\nДля: {assignee.full_name}", parse_mode="HTML", reply_markup=main_kb(user.role))
    try:
        await message.bot.send_message(assignee.telegram_id, f"📋 <b>Новая задача:</b>\n\n<b>{task.title}</b>\n{description or ''}", parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not notify: {e}")

@router.message(F.text == "➕ Добавить сотрудника")
async def add_employee_info(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or user.role != "owner":
        await message.answer("❌ Нет доступа.")
        return
    await message.answer(
        "👤 Попроси сотрудника написать боту /start\n\n"
        "После регистрации ты получишь уведомление.\n"
        "Роль можно изменить прямо в базе данных Railway.",
        reply_markup=main_kb(user.role))

@router.message(F.text == "📊 Отчёт за день")
async def daily_report(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user or user.role != "owner":
        await message.answer("❌ Нет доступа.")
        return
    today = date.today()
    async with async_session_factory() as s:
        shifts = await ShiftRepo(s).get_today_all()
    if not shifts:
        await message.answer(f"📊 За {today.strftime('%d.%m.%Y')} смен не найдено.")
        return
    from app.utils.pdf_report import generate_daily_report
    shifts_data = [{"employee": sh.employee.full_name if sh.employee else "—", "object": sh.site_object.name if sh.site_object else "—", "start": sh.started_at.strftime("%H:%M"), "end": sh.ended_at.strftime("%H:%M") if sh.ended_at else "—", "hours": float(sh.total_hours or 0), "photos_before": bool(sh.photos_before), "photos_after": bool(sh.photos_after), "notes": sh.notes or ""} for sh in shifts]
    pdf_bytes = generate_daily_report(today, shifts_data)
    await message.answer_document(document=BufferedInputFile(pdf_bytes, filename=f"report_{today.strftime('%Y%m%d')}.pdf"), caption=f"📊 Отчёт за {today.strftime('%d.%m.%Y')} — {len(shifts)} смен")

@router.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()

@router.callback_query(F.data == "hours_week_after")
async def hours_week_after(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    today = date.today()
    async with async_session_factory() as s:
        hw = await ShiftRepo(s).total_hours(
            user.id, today - timedelta(days=today.weekday()), today
        )
        shifts = await ShiftRepo(s).get_by_employee(
            user.id, today - timedelta(days=today.weekday()), today, limit=7
        )
    lines = ""
    for sh in shifts:
        h = float(sh.total_hours or 0)
        name = sh.site_object.name if sh.site_object else "—"
        lines += f"\n• {sh.started_at.strftime('%d.%m')} {sh.started_at.strftime('%H:%M')}–{sh.ended_at.strftime('%H:%M') if sh.ended_at else '...'} {name} — {h:.1f} ч."
    await callback.message.edit_text(
        f"📊 <b>Часы за неделю</b>\n\n"
        f"Итого: <b>{hw:.1f} ч.</b>\n"
        f"Смен: {len(shifts)}"
        f"{lines}",
        parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_employees")
async def back_employees(callback: CallbackQuery) -> None:
    async with async_session_factory() as s:
        employees = await UserRepo(s).get_all_active()
    await callback.message.edit_text(f"👥 <b>Сотрудники ({len(employees)}):</b>", parse_mode="HTML", reply_markup=kb_employees(employees))
    await callback.answer()

@router.callback_query(F.data == "back_tasks")
async def back_tasks(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    async with async_session_factory() as s:
        tasks = await TaskRepo(s).get_for_employee(user.id)
    await callback.message.edit_text(f"📋 <b>Твои задачи ({len(tasks)}):</b>", parse_mode="HTML", reply_markup=kb_tasks(tasks))
    await callback.answer()

@router.callback_query(F.data == "back_objects")
async def back_objects(callback: CallbackQuery) -> None:
    async with async_session_factory() as s:
        objects = await ObjectRepo(s).get_active()
    await callback.message.edit_text(f"🏗 <b>Объекты ({len(objects)}):</b>", parse_mode="HTML", reply_markup=kb_objects_manage(objects))
    await callback.answer()
