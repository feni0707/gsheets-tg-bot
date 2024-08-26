from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotmap import DotMap

from data.consts import DICT_PROFILES, TEXT_FOR_KB


kb_data = {}

# for name_kb in list(TEXT_FOR_KB.keys())[:-1]:
for name_kb in list(TEXT_FOR_KB.keys()):
    builder = ReplyKeyboardBuilder()
    for text in TEXT_FOR_KB[name_kb]:
        builder.add(KeyboardButton(text=text))
    if len(TEXT_FOR_KB[name_kb]) == 3:
        builder.adjust(2)
    kb_data[name_kb] = builder.as_markup(resize_keyboard=True)


async def get_choose_profile_keyboard(
    pressed_buttons: list[str] = [], pressed_button: str | None = ""
):
    builder = InlineKeyboardBuilder()

    if pressed_button:
        if pressed_button.startswith("cancel_"):
            pressed_buttons.remove(pressed_button[7:])
        else:
            pressed_buttons.append(pressed_button)

    for call_data, profile in DICT_PROFILES.items():
        if call_data in pressed_buttons:
            profile += "✅"
            # profile = "✅" + profile
            call_data = "cancel_" + call_data
        builder.button(text=profile, callback_data=call_data)

    builder.button(text="✅Готово", callback_data="done")
    builder.adjust(2)

    return builder.as_markup(), pressed_buttons


async def get_settings_kb(notify: bool):
    text_for_kb = TEXT_FOR_KB["settings"][:2]
    text_for_kb.append(
        TEXT_FOR_KB["settings"][3] if notify else TEXT_FOR_KB["settings"][2]
    )
    builder = ReplyKeyboardBuilder()
    for text in text_for_kb:
        builder.add(KeyboardButton(text=text))
    builder.adjust(2)

    return builder.as_markup(resize_keyboard=True)


keyboards = DotMap(kb_data)
