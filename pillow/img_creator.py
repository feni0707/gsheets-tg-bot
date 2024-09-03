from pprint import pprint
from PIL import Image, ImageDraw, ImageFont
from re import search

from data.consts import SCHOOL_DAYS, TIME_BEGINNINGS_THE_LESSONS_FOR_SHIFT


class ImgSchedule:
    def __init__(self, school_shift: int) -> None:
        self.__school_shift = school_shift
        self.__is_time_begin_set = False

    async def __get_properties_text(self, text, is_bold, draw, is_merged, size_font=80):
        font = ImageFont.truetype(
            f"pillow/fonts/times_new_roman{'_bold' if is_bold else ''}.ttf",
            size_font,
        )
        text_width = draw.textlength(max(text.split("\n"), key=len), font)
        default_width = 1800 if is_merged else 750
        if text_width < default_width:
            self.__font, self.__text_width = font, text_width
        else:
            return await self.__get_properties_text(
                text, is_bold, draw, is_merged, size_font - 5
            )

    async def __get_current_template_img(self):
        days = "будни" if self.__day != SCHOOL_DAYS[-1] else "суббота"
        school_class = self.__school_class if self.__is_high_class else "5-9"
        shift = (
            f"{self.__school_shift}смена"
            if days == "будни" and not self.__is_high_class
            else ""
        )
        # for is_true, condition, is_false in (('будни', self.__day != SCHOOL_DAYS[-1], 'суббота'), (''))
        self.__img = Image.open(
            f"pillow/images/templates/шаблон_{'_'.join([value for value in (days, school_class, shift) if value])}.png"
        )

    async def __prepare_to_work(self, school_class, day, lessons_of_class):
        self.__is_time_begin_set = False
        self.__school_class, self.__day = school_class, day
        self.__is_high_class = school_class.isdigit()
        await self.__get_current_template_img()
        if not self.__is_high_class:
            lessons_of_class = {school_class: lessons_of_class}
        self.__lessons_of_class = lessons_of_class
        self.__img_width, self.__img_height = self.__img.size
        self.__draw = ImageDraw.Draw(self.__img)
        await self.__set_title_properties()

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

    async def __prepare_now_coords(self, index, is_merged):
        now_pos_y = 146 + index * 153
        if self.__is_high_class and not is_merged:
            now_pos_x = (self.__img_width - self.__text_width) / 2 + (
                (-1) ** self.__k
            ) * ((self.__img_width - 200) // 4)

        else:
            now_pos_x = (self.__img_width - self.__text_width) / 2
        self.__now_pos_y, self.__now_pos_x = now_pos_y, now_pos_x

    async def __prepare_not_merged_cell(self, text_for_cell, is_merged):
        if is_merged:
            self.__merged_cells[self.__day].remove(text_for_cell)
        else:
            if self.__is_high_class:
                self.__draw.rectangle(
                    (
                        self.__img_width / 2 - 4.5,
                        self.__now_pos_y + 3,
                        self.__img_width / 2 + 4.5,
                        self.__now_pos_y + 160,
                    ),
                    fill="black",
                )

    async def __set_time_begin_to_school(self):
        for index, item in enumerate(self.__lessons_of_class[self.__text]):
            if item:
                matches = search(r"\d{1,2}\.\d{1,2}", item)
                is_time_to_begin = True if matches and matches.group() else False
                key = (
                    f"{self.__school_shift} смена"
                    if self.__day != SCHOOL_DAYS[-1]
                    else "суббота"
                )
                new_item = (
                    "к "
                    + TIME_BEGINNINGS_THE_LESSONS_FOR_SHIFT[key][
                        index - 1 + is_time_to_begin
                    ]
                )
                self.__lessons_of_class[self.__text][
                    index - 1 + is_time_to_begin
                ] = new_item
                if self.__is_high_class:
                    print(self.__day, self.__merged_cells[self.__day], item)
                    self.__is_time_begin_set = item in self.__merged_cells[self.__day]
                    if self.__is_time_begin_set:
                        self.__merged_cells[self.__day].remove(item)
                        self.__merged_cells[self.__day].append(new_item)
                else:
                    self.__is_time_begin_set = True
                break

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
                await self.__prepare_not_merged_cell(text_for_cell, is_merged)
                self.__draw.text(
                    (
                        self.__now_pos_x,
                        self.__now_pos_y + 40,
                    ),
                    text_for_cell,
                    font=self.__font,
                    fill="#000000",
                )

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
            # if not self.__is_time_begin_set:
            #     await self.__set_time_begin_to_school()
            await self.__for_lesson_in_lessons()
        self.__img.save(f"pillow/images/schedules/{day}/{school_class}.jpg")

    async def schedule_to_pictures(self, school_schedule, merged_cells):
        # pprint(school_schedule)
        self.__merged_cells = merged_cells
        for school_class, lessons_of_class_per_day in school_schedule.items():
            for day, data in lessons_of_class_per_day.items():
                if isinstance(data, dict):
                    lists = list(data.values())
                    lessons = lists[0] + lists[1]
                else:
                    lessons = data[:]
                if any(lessons):
                    print(school_class, lessons)
                    await self.__create_img_and_save(school_class, day, data)
