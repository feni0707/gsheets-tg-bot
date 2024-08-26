from aiogram.fsm.state import State, StatesGroup


class User_States(StatesGroup):
    start_menu = State()
    choose_class = State()
    choose_profiles = State()
    yes_no_notify = State()
    menu = State()
    schedule = State()
    settings = State()
    swap_notify = State()
    confimation_reset_settings = State()
    menu_or_reset = State()
