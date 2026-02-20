from aiogram.fsm.state import State, StatesGroup

class CreateProfile(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_interests = State()
    waiting_for_description = State()
    waiting_for_photos = State()

class EditProfile(StatesGroup):
    choosing_field = State()
    waiting_for_new_name = State()
    waiting_for_new_age = State()
    waiting_for_new_gender = State()
    waiting_for_new_interests = State()
    waiting_for_new_description = State()
    waiting_for_new_photos = State()

class BrowseProfiles(StatesGroup):
    browsing = State()

class SuperLike(StatesGroup):
    waiting_for_message = State()