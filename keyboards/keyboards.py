from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotmap import DotMap

from data.consts import TEXT_FOR_KB


kb_data = {}

# for name_kb in list(TEXT_FOR_KB.keys())[:-1]:
for name_kb in list(TEXT_FOR_KB.keys()):
    builder = ReplyKeyboardBuilder()
    for text in TEXT_FOR_KB[name_kb]:
        builder.add(KeyboardButton(text=text))
    if len(TEXT_FOR_KB[name_kb]) == 3:
        builder.adjust(2)
    kb_data[name_kb] = builder.as_markup(
        resize_keyboard=True, input_field_placeholder="Воспользуйтесь меню ниже"
    )


async def get_settings_kb(notify: bool):
    text_for_kb = TEXT_FOR_KB["settings"][:2]
    text_for_kb.append(
        TEXT_FOR_KB["settings"][3] if notify else TEXT_FOR_KB["settings"][2]
    )
    builder = ReplyKeyboardBuilder()
    for text in text_for_kb:
        builder.add(KeyboardButton(text=text))
    builder.adjust(2)

    return builder.as_markup(
        resize_keyboard=True, input_field_placeholder="Воспользуйтесь меню ниже"
    )


for key in ("confimation_reset_settings", "yes_no_notify"):
    kb_data[key] = kb_data["yes_no"]
keyboards = DotMap(kb_data)
