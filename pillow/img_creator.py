from PIL import Image, ImageDraw, ImageFont
from re import search

from data.consts import SCHOOL_DAYS
from utils.utils import delete_photo


class ImgSchedule:
    def __init__(self, school_shift: int) -> None:
        self.__school_shift = school_shift

    async def schedule_to_pictures(self, school_schedule, merged_cells):
        self.__merged_cells = merged_cells
        for school_class, lessons_of_class_per_day in school_schedule.items():
            for day, data in lessons_of_class_per_day.items():
                if isinstance(data, dict):
                    lists = list(data.values())
                    lessons = lists[0] + lists[1]
                else:
                    lessons = data[:]
                if any(lessons):
                    await self.__create_img_and_save(school_class, day, data)
                else:
                    delete_photo(school_class, day)

    async def __create_img_and_save(
        self,
        school_class: str,
        day: str,
        lessons_of_class,
    ):
        await self.__prepare_to_work(school_class, day, lessons_of_class)
        await self.__draw_day()

        data = school_class[-1] if not self.__is_high_class else ["Б", "А"]

        for k, letter in enumerate(data):
            self.__k = k
            self.__letter = letter
            await self.__set_text_and_calculated()
            self.__draw.text(
                (
                    (self.__img_width - self.__title_text_width) // 2
                    + self.__calculated,
                    42,
                ),
                self.__text,
                font=self.__title_font,
                fill="#000000",
            )
            await self.__for_lesson_in_lessons()
        self.__img.save(f"pillow/images/schedules/{day}/{school_class}.jpg")

    async def __prepare_to_work(self, school_class, day, lessons_of_class):
        self.__school_class, self.__day = school_class, day
        self.__is_high_class = school_class.isdigit()
        await self.__get_current_template_img()
        if not self.__is_high_class:
            lessons_of_class = {school_class: lessons_of_class}
        self.__lessons_of_class = lessons_of_class
        self.__img_width, self.__img_height = self.__img.size
        self.__draw = ImageDraw.Draw(self.__img)
        await self.__set_title_properties()

    async def __get_current_template_img(self):
        days = "будни" if self.__day != SCHOOL_DAYS[-1] else "суббота"
        school_class = self.__school_class if self.__is_high_class else "5-9"
        shift = (
            f"{self.__school_shift}смена"
            if days == "будни" and not self.__is_high_class
            else ""
        )
        self.__img = Image.open(
            f"pillow/images/templates/шаблон_{'_'.join([value for value in (days, school_class, shift) if value])}.png"
        )

    async def __set_title_properties(self):
        self.__title_font = ImageFont.truetype("pillow/fonts/calibri_bold.ttf", 90)
        self.__title_text_width = self.__draw.textlength(
            self.__school_class, self.__title_font
        )

    async def __draw_day(self):
        day_font = ImageFont.truetype("pillow/fonts/times_new_roman_bold.ttf", 100)
        line_height = sum(day_font.getmetrics())
        line_width = int(self.__draw.textlength(self.__day, day_font))
        fontimage = Image.new("L", (line_width, line_height))
        ImageDraw.Draw(fontimage).text((0, 0), self.__day, fill=255, font=day_font)
        fontimage = fontimage.rotate(
            270, resample=getattr(Image, "BICUBIC"), expand=True
        )
        self.__img.paste(
            (0, 0, 0),
            box=(self.__img_width - 130, (self.__img_height - line_width) // 2),
            mask=fontimage,
        )

    async def __set_text_and_calculated(self):
        if self.__is_high_class:
            text = self.__school_class + self.__letter
            calculated = (-1) ** self.__k * (self.__img_width // 4)
        else:
            text = self.__school_class
            calculated = 0
        self.__text, self.__calculated = text, calculated

    async def __for_lesson_in_lessons(self):
        for index, text_for_cell in enumerate(self.__lessons_of_class[self.__text]):
            if text_for_cell:
                is_merged = (
                    True
                    if self.__is_high_class
                    and text_for_cell in self.__merged_cells[self.__day]
                    else False
                )
                matches = search(r"РОВ|РМГ|(\d{1,2}\.\d{1,2})", text_for_cell)
                is_bold = True if matches and matches.group() else False
                await self.__get_properties_text(
                    text_for_cell, is_bold, self.__draw, is_merged
                )
                await self.__prepare_now_coords(index, is_merged)
                await self.__prepare_not_merged_cell(text_for_cell, index, is_merged)
                self.__draw.text(
                    (
                        self.__now_pos_x,
                        self.__now_pos_y,
                    ),
                    text_for_cell,
                    font=self.__font,
                    fill="#000000",
                )

    async def __get_properties_text(self, text, is_bold, draw, is_merged, size_font=80):
        font = ImageFont.truetype(
            f"pillow/fonts/times_new_roman{'_bold' if is_bold else ''}.ttf",
            size_font,
        )
        w, h = font.getbbox(max(text.split("\n"), key=len), language="ru")[-2:]
        default_width = 1800 if is_merged else 900
        if w < default_width:
            self.__font, self.__text_width, self.__text_height = font, w, h
        else:
            return await self.__get_properties_text(
                text, is_bold, draw, is_merged, size_font - 1
            )

    async def __prepare_now_coords(self, index, is_merged):
        now_pos_y = 159 + 153.5 * index + (140 - self.__text_height) / 2
        if self.__is_high_class and not is_merged:
            now_pos_x = ((self.__img_width / 2 + 164) - self.__text_width) / 2
            if not self.__k:
                now_pos_x += 950

        else:
            now_pos_x = (self.__img_width - self.__text_width) / 2
        self.__now_pos_y, self.__now_pos_x = now_pos_y, now_pos_x

    async def __prepare_not_merged_cell(self, text_for_cell, index, is_merged):
        if is_merged:
            self.__merged_cells[self.__day].remove(text_for_cell)
        else:
            if self.__is_high_class:
                self.__draw.rectangle(
                    (
                        self.__img_width / 2 - 4.5,
                        155 + 153.5 * index,
                        self.__img_width / 2 + 4.5,
                        159 + 153.5 * (index + 1) - 10.5,
                    ),
                    fill="black",
                )
