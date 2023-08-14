from mwsqlite import MWBase
from aiogram import Bot, Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from typing import Union
import yaml

def load_yml(path):
    with open(path) as f:
        return yaml.safe_load(f)

BOT_TOKEN = load_yml('settings.yml').get('BOT_TOKEN')
if not BOT_TOKEN:
    input("BOT_TOKEN not found")
    exit()

base = MWBase(
    "bot.db",
    tables = {
        'results': {
            'user_id': int,
            'number1': float,
            'number2': float,
            'result': float,
            'description': str
        }
    }
)

class InputState(StatesGroup):
    number1 = State()
    number2 = State()
    description = State()

factory = CallbackData('tg', 'action')
#  1 - input 
#  0 - cancel
# -1 - history
# -2 - clear history


bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# buttons 
CANCEL = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text = "Назад", 
                callback_data = factory.new(action = 0))
        ]
    ]
)

MENU = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="Добавить расчёт",
                callback_data = factory.new(action = 1))
        ],
        [
            types.InlineKeyboardButton(
                text="История",
                callback_data = factory.new(action = -1))
        ],
        [
            types.InlineKeyboardButton(
                text="Очистить историю",
                callback_data = factory.new(action = -2))
        ]
])

def convert_int_to_string(number):
    return "{:,}".format(number)

async def answer(message: Union[types.Message, types.CallbackQuery], *args, **kwargs):
    if isinstance(message, types.Message):
        await message.answer(*args, **kwargs)
    elif isinstance(message, types.CallbackQuery):
        await bot.edit_message_text(*args, **kwargs, chat_id=message.from_user.id, message_id = message.message.message_id)

@dp.callback_query_handler(factory.filter(action = '1'))
async def add_calc(message: types.CallbackQuery, state: State):
    await InputState.number1.set()
    await answer(
        message,
        "Введите первое число:",
        reply_markup = CANCEL
    )
    
@dp.message_handler(state = InputState.number1)
async def add_num1(message: types.Message, state: FSMContext):
    num = message.text.replace(',', '.')
    try:
        num = float(num)
    except Exception as e:
        await answer(
            message,
            f"Неверное число, попробуйте ещё раз. ({e})",
            reply_markup = CANCEL
        )
        return

    await state.update_data(
        number1 = num
    )

    await InputState.number2.set()
    await answer(
        message,
        f"{num}\n\nВведите второе число:",
        reply_markup = CANCEL
    )

@dp.message_handler(state = InputState.number2)
async def add_num2(message: types.Message, state: FSMContext):
    num = message.text.replace(',', '.')
    try:
        num = float(num)
    except Exception as e:
        await answer(
            message,
            f"Неверное число, попробуйте ещё раз. ({e})",
            reply_markup = CANCEL
        )
        return

    number1 = (await state.get_data()).get('number1')
    number2 = num

    result = number1 - number2

    await state.update_data(
        number2 = num,
        result = result
    )

    await InputState.description.set()

    await answer(
        message,
        f"{number1} - {number2} = {result}\n\nВведите описание:",
        reply_markup = CANCEL
    )

@dp.message_handler(state = InputState.description)
async def add_desc(message: types.Message, state: FSMContext):
    desc = message.text

    data = await state.get_data()
    number1 = data.get('number1')
    number2 = data.get('number2')
    result = data.get('result')

    base.results.add(
        user_id = message.from_user.id,
        number1 = number1,
        number2 = number2,
        result = result,
        description = desc
    )

    await state.finish()

    await answer(
        message,
        "Расчёт сохранён.",
    )

    await start(message)

@dp.callback_query_handler(factory.filter(action = '0'), state = "*") # Назад
async def back(message: types.CallbackQuery, state: State):
    if state:
        await state.finish()

    await start(message)

@dp.callback_query_handler(factory.filter(action = '-1')) # История
async def get_history(message: types.CallbackQuery, state: State):
    user_results = base.results.get(
        user_id = message.from_user.id
    )
    if not user_results:
        await answer(
            message,
            "У вас нет истории расчётов.",
            reply_markup = CANCEL
        )
        return

    text = ""
    for i, result in enumerate(user_results):
        text += f"{i+1}. {convert_int_to_string(result.result)}\n{result.description}\n\n"

    await answer(
        message,
        text,
        reply_markup = CANCEL
    )

@dp.callback_query_handler(factory.filter(action = '-2')) # Очистить историю
async def clear_history(message: types.CallbackQuery, state: State):
    # clear
    base.results.execute(
        "DELETE FROM results WHERE user_id = ?", 
        (message.from_user.id,),
    )

    await answer(
        message,
        "Ваши результаты очищены.",
        reply_markup = CANCEL
    )

@dp.message_handler()
async def start(message: types.Message):
    await answer(
        message,
        "Бот для расчёта разницы между двумя числами.",
        reply_markup = MENU)
    

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
