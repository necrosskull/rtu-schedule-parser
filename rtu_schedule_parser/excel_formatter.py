from __future__ import annotations

import logging
import re
from dataclasses import replace

from .constants import Campus, LessonType, RoomType, TestSessionLessonType
from .formatter import Formatter
from .schedule import Room

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExcelFormatter(Formatter):
    """Format the lesson name according to the specified rules."""

    # Numbers separated by commas or dashes
    _RE_NUMBERS = r"(?:\d+[-,\s.]*)+"

    # Exclude weeks words
    _RE_EXCLUDE_WEEKS = r"\W*(?:кр|кроме)(?:\.|\b)"

    _RE_SUBGROUPS = r"(подгруппа|подгруп|подгр|п\/г|группа|гр|пг)"

    # Including weeks words, ignoring subgroups
    _RE_WEEKS = rf"{_RE_NUMBERS}\s*(?:(?:нед|н)|\W)(?![.\s\d,-]*{_RE_SUBGROUPS})[.\s]*"

    # Lesson type
    _RE_LESSON_TYPES = r"(?:\b(лк|пр|лек|лаб)\b)"

    # Unnecessary characters at the beginning of the line
    _RE_TRASH_START = r"(\A\W+\s*)"

    # Unnecessary characters at the end of the line
    _RE_TRASH_END = r"([-,_.\+;]+$)"

    _RE_SEPARATORS = r" {2,}|\n{1,}|,|;|\+|\/"

    # Room type short names
    ROOM_TYPE_SHORT_NAMES = {
        "ауд": RoomType.AUDITORY,
        "лаб": RoomType.LABORATORY,
        "комп": RoomType.COMPUTERS,
        "физ": RoomType.SPORT,
        "адм": RoomType.ADM,
        "коворкинг": RoomType.COWORKING,
        "ауд спец": RoomType.AUDITORY,
        "каб": RoomType.AUDITORY,
        "лаб спец": RoomType.LABORATORY,
    }

    def __format_subgroups_and_type(self, lesson: str) -> list:
        """Format rare cases when subgroup and lesson type are specified in a strange way.

        Returns:
            list of separated and formatted lesson names.
        """

        result = []

        # 2,4,6,8,10 (лк),12,14н (пр) Инструментарий информационно-аналитической деятельности
        # group 1 - week numbers, group 2 - lesson type
        regexp_1 = r"(?:((?:\d+[-, \.]*)+(?:н|нед)?[. ]*)(?:[( ]*(лк|пр|лек|лаб)[) ]+))"

        # 1гр.= 2н.; 2гр.=4н. Криптографические методы защиты информации;
        # group 1 - subgroup num, group 2 - week numbers
        regexp_2 = r"(?:(\d+[-, \.]*)+(?:группа|груп|гр|подгруппа|подгр)[. -]*=\s*((?:\d+[-, \.]*)+(?:нед|н)?[;. \b]+))"

        # 6,12н-1гр 4,10н-2 гр Материалы и технологии трехмерной печати в машиностр
        # group 1 - week numbers, group 2 - subgroup num
        regexp_3 = r"(?:((?:\d+[-, \.]*)+(?:нед|н)[. ]*\-)(?:(\d+[-, =\.]*)+(?:группа|груп|гр|подгруппа|подгр)[. \b]*))"

        # (3,7,11,15 н. - лк; 5,9,13,17 н. - пр) Современные проблемы и методы прикладной информатики и развития
        # информационного общества
        # group 1 - week numbers, group 2 - lesson type
        regexp_4 = (
            rf"({self._RE_NUMBERS}(?:н|нед)?[. ]*)(?:[- ]*(лк|пр|лек|лаб)(\b|[; ]+))"
        )

        expressions = [regexp_1, regexp_2, regexp_3, regexp_4]

        # Check which regexp is suitable for the lesson name. Divide lesson name according to subgroups,
        # types of pairs, weeks, remove garbage and return the finished list.
        for regexp in expressions:
            found = re.finditer(regexp, lesson)
            found_items = [x for x in found]
            if len(found_items) > 0:
                for week_types in found_items:
                    lesson = lesson.replace(week_types.group(), "")

                # Remove unnecessary characters from the beginning and end of the lesson name.
                remove_trash = r"(\A\W+\s*)|([-,_\+;]+$)"
                lesson = re.sub(remove_trash, "", lesson)
                lesson = lesson.strip()
                list_lessons = lesson.split(";")

                group_substr = (
                    " подгруппа" if regexp == regexp_2 or regexp == regexp_3 else ""
                )

                if len(list_lessons) == 2 and len(found_items) == 4:
                    for i in range(len(found_items)):
                        index = int(i >= 2)

                        group_1 = re.sub(remove_trash, "", found_items[i].group(1))
                        group_1 = group_1.strip()

                        group_2 = re.sub(remove_trash, "", found_items[i].group(2))
                        group_2 = group_2.strip()

                        if regexp == regexp_2:
                            result.append(
                                f"{group_2} {list_lessons[index]} {group_1}{group_substr}"
                            )

                        else:
                            result.append(
                                f"{group_2} {list_lessons[index]} {group_2}{group_substr}"
                            )

                else:
                    for week_types in found_items:
                        group_1 = re.sub(remove_trash, "", week_types.group(1))
                        group_1 = group_1.strip()

                        group_2 = re.sub(remove_trash, "", week_types.group(2))
                        group_2 = group_2.strip()

                        if regexp == regexp_2:
                            result.append(f"{group_2} {lesson} {group_1}{group_substr}")
                        else:
                            result.append(f"{group_1} {lesson} {group_2}{group_substr}")

        return result

    def __split_lessons(self, lessons: str) -> list:
        """Split lessons by different separators."""
        result = []

        # Several lessons are separated by line breaks
        if "\n" in lessons:
            result = lessons.split("\n")

        # Several lessons are separated by large spaces
        elif len(re.split(r" {3,}", lessons)) > 1:
            result = re.split(r" {3,}", lessons)

        # Uses the default separator
        if len(result) > 0:
            for lesson in sorted(result):
                formatted_lessons = self.__format_subgroups_and_type(lesson)
                if len(formatted_lessons) > 0:
                    result.remove(lesson)
                    result += formatted_lessons

        else:
            formatted_lessons = self.__format_subgroups_and_type(lessons)
            if len(formatted_lessons) > 0:
                result += formatted_lessons

        # If previous steps did not work, so we have only one lesson or several lessons in one line
        if len(result) == 0:
            # Try to split by semicolon
            if ";" in lessons:
                result += lessons.split(";")
            else:
                # Handle case when lesson is written in one line without any separators. For example:
                # "1,3,9,13 Конфиденциальное делопроизводство 5,7,11,15 н. кр 5 н. Деньги, кредит,банки"
                re_one_line_lessons = r"(?:\d+[-,\s.]*)+(?:(?:нед|н)|\b)[\. ]*(?:\(?(?:кроме|кр)? *(?:\d+[-,\s.]*)+(?:(?:нед|н)|\b)[\. ])(?![.\s,\-\d]*(?:подгруппа|подгруп|подгр|п\/г|группа|гр))"
                found = [x for x in re.finditer(re_one_line_lessons, lessons)]
                length = len(found)
                if length > 1:
                    for i in range(length):
                        current_found_pos = found[i].span()
                        is_last_element = i == length - 1
                        if is_last_element:
                            result.append(lessons[current_found_pos[0] :])
                        else:
                            next_found_pos = found[i + 1].span()
                            result.append(
                                lessons[current_found_pos[0] : next_found_pos[0]]
                            )
                else:
                    # One lesson in one line
                    result.append(lessons)

        return [lesson for lesson in result if lesson.strip() != ""]

    def __format_subgroups(self, lessons: list[str]) -> list[tuple[str, int | None]]:
        """
        If subgroup is specified in lessons, returns list of tuples with lesson name (without subgroup) and subgroup
        number. Else returns list of tuples with lesson name and None.

        Example:
            "Физика (1 п/г)" -> [("Физика", 1)]
        """
        re_subgroups = self._RE_NUMBERS + self._RE_SUBGROUPS
        new_lessons = []
        for lesson_ in lessons:
            lesson = lesson_
            if found := re.search(re_subgroups, lesson):
                numbers_only = found[0].replace(found[1], "").strip()
                groups = self.__parse_numbers(numbers_only)
                if len(groups) == 1:
                    lesson = lesson.replace(found[0], "")
                    # If subgroups are specified in brackets, remove them
                    lesson = re.sub(r"\(\W*\s*\)", "", lesson)
                    # Remove commas
                    lesson = re.sub(r"^\s*,\s*|\s*,\s*$", "", lesson)
                    new_lessons.append((lesson, groups[0]))
                else:
                    new_lessons.append((lesson, None))
            else:
                new_lessons.append((lesson, None))
        return new_lessons

    def __parse_numbers(self, numbers_substr) -> list[int]:
        def parse_interval_numbers(substring: str):
            """
            Given a string like "1-5", returns a list of numbers from 1 to 5.
            """

            weeks_range = substring.split("-")
            return list(
                range(int(weeks_range[0].strip()), int(weeks_range[1].strip()) + 1)
            )

        def parse_listed_numbers(substring: str):
            """
            Get list of numbers from string with numbers separated by comma.
            Example: "1, 2, 3" -> [1, 2, 3]
            """
            substring = re.sub(r"^([\W\s])+|([\W\s])+$", "", substring)
            weeks_list = substring.split(",")
            return [int(week.strip()) for week in weeks_list]

        numbers = []

        if (
            "-" in numbers_substr
            and "," in numbers_substr
            and re.search(r"\d+-\d+,\d+-\d+", numbers_substr)
        ):
            re_interval_numbers = r"(\d+ *- *\d+)"
            interval_weeks_substring = re.findall(re_interval_numbers, numbers_substr)
            for interval in interval_weeks_substring:
                numbers += parse_interval_numbers(interval)
            numbers.sort()

        # Weeks are listed in interval format and separated by comma
        elif "-" in numbers_substr and "," in numbers_substr:
            re_interval_numbers = r"(\d+ *- *\d+)"
            interval_weeks_substring = re.findall(re_interval_numbers, numbers_substr)[
                0
            ]

            numbers += parse_interval_numbers(interval_weeks_substring)
            weeks_substring = re.sub(re_interval_numbers, "", numbers_substr)
            # Remove unnecessary symbols
            weeks_substring = re.sub(r"^([\W\s])+|([\W\s])+$", "", weeks_substring)
            numbers += parse_listed_numbers(weeks_substring)
            numbers.sort()

        # Weeks are listed in interval format
        elif "-" in numbers_substr:
            numbers += parse_interval_numbers(numbers_substr)

        # Weeks are listed in comma-separated format
        elif "," in numbers_substr:
            numbers += parse_listed_numbers(numbers_substr)

        # Only one week
        else:
            clear_week = numbers_substr.strip()
            if len(clear_week) > 0:
                numbers.append(int(clear_week))

        return numbers

    def __fix_lesson_typos(self, names: str) -> str:
        """Fix typos in lesson names."""
        names = re.sub(r"деятельность\s*деятельность", "деятельность", names)
        names = re.sub(
            r"^\s*Военная\s*$", "Военная подготовка", names, flags=re.MULTILINE
        )
        names = re.sub(
            r"^\s*подготовка\s*$", "Военная подготовка", names, flags=re.MULTILINE
        )
        names = re.sub(r"^((\s*\d\s*п[/\\]?г,*){2})$", "", names, flags=re.MULTILINE)
        # replace \n to space
        names = re.sub(r"(\n)(\d\s*п[/\\]?г)", r" \g<2>", names, flags=re.MULTILINE)

        names = re.sub(r"Переезд", "", names, flags=re.MULTILINE)

        return names

    def __fix_room_typos(self, rooms: str) -> str:
        """Fix typos in room names."""
        rooms = rooms.replace("ауд спец.", "лаб.")
        rooms = rooms.replace("Учебный портал РТУ МИРЭА", "СДО")
        rooms = re.sub(
            r"ауд\.\s*каф\.", "ауд. кафедра", rooms, flags=re.IGNORECASE | re.MULTILINE
        )
        rooms = re.sub(
            r"Спорт\.?\s*зал\s*\((\w+)\)",
            r"\g<1> спорт. зал",
            rooms,
            flags=re.MULTILINE,
        )

        en_to_ru_letters = {
            "A": "А",
            "B": "В",
            "C": "С",
        }

        # replace english letters to russian
        try:
            rooms = re.sub(r"([A-Z])", lambda x: en_to_ru_letters[x.group(0)], rooms)
        except KeyError as e:
            raise ValueError("Unknown letter in rooms cell") from e

        return rooms

    def __parse_weeks(
        self, weeks_substring: str, is_even: bool | None = None
    ) -> list[int]:
        """Get list of weeks from substring with weeks numbers considering parity."""
        weeks = self.__parse_numbers(weeks_substring)
        if is_even is not None:
            weeks = [week for week in weeks if week % 2 != is_even]
        return weeks

    def __get_only_lesson_name(self, lesson):
        """Remove all unnecessary information from lesson name."""

        lesson = re.sub(self._RE_WEEKS, "", lesson)
        lesson = re.sub(self._RE_EXCLUDE_WEEKS, "", lesson)
        lesson = re.sub(self._RE_LESSON_TYPES, "", lesson)
        lesson = re.sub(self._RE_TRASH_START, "", lesson)
        lesson = re.sub(self._RE_TRASH_END, "", lesson)
        lesson = lesson.strip()

        return lesson

    def get_rooms(self, rooms_cell_value: str) -> list[Room]:
        result = []

        rooms_cell_value = self.__fix_room_typos(rooms_cell_value)

        # Convert values like "Г-101а" to "Г-101-а"
        rooms_cell_value = re.sub(r"(\d)([а-яА-Я])", r"\g<1>-\g<2>", rooms_cell_value)

        # Regex explanation:
        # 1. ([а-яА-Я]+)\. - room type (e.g. "лаб.")
        # 2. ([а-яА-Я0-9-]+) - room name (e.g. "А-101")
        # 3. \(([а-яА-Я0-9-]+)\) - campus name (e.g. "(В-78)")
        re_rooms_with_type = r"([а-яА-Я]+)\. ([а-яА-Я0-9-]+) \(([а-яА-Я0-9-]+)\)"
        rooms_with_type = re.findall(re_rooms_with_type, rooms_cell_value)

        def try_get_room(room) -> Room:
            try:
                return Room(
                    room[1],
                    Campus.get_by_short_name(room[2]),
                    self.ROOM_TYPE_SHORT_NAMES[room[0].strip().lower()],
                )

            except ValueError:
                return Room(
                    room[1],
                    None,
                    self.ROOM_TYPE_SHORT_NAMES[room[0].strip().lower()],
                )

        for room in rooms_with_type:
            result.append(try_get_room(room))

        if result:
            return result

        for campus in Campus:
            short_name = campus.short_name
            res = re.findall(short_name, rooms_cell_value, flags=re.A)
            if res:
                rooms = (
                    rooms_cell_value.replace("  ", "")
                    .replace("*", "")
                    .replace("\n", "")
                )
                rooms = re.sub(
                    res[0],
                    "",
                    rooms,
                    flags=re.A,
                )
                result.append(Room(rooms, Campus.get_by_short_name(short_name), None))

        if not result:
            rooms = re.split(r" {2,}|\n", rooms_cell_value)
            result = [Room(room.strip(), None, None) for room in rooms if room]

        for i in range(len(result)):
            room = result[i]
            new_name = re.sub(r"(\s*\(\))\s*", "", room.name)
            result[i] = replace(room, name=new_name)

        return result

    def __replace_empty_teachers_to_text(self, text: str) -> str:
        """Иногда стоят подгруппы бе преподавателей, заменяем их на текст. Такое бывает, если расписание не доделано."""
        return re.sub(
            r"^(\d п/г)$",
            r"Нет,\g<1>",
            text.strip(),
            flags=re.IGNORECASE | re.MULTILINE,
        )

    def get_teachers(self, names_cell_value: str) -> list[str] | list[tuple[str, int]]:
        if not re.search(r"[а-яА-Я]", names_cell_value):
            return []

        names_cell_value = self.__replace_empty_teachers_to_text(names_cell_value)

        teachers_names = names_cell_value.strip()

        re_typos = r"[а-яё]{1}(,) {0,2}[а-яё]{1}[. ]"
        typos = re.finditer(re_typos, teachers_names, flags=re.I)
        for typo in typos:
            teachers_names = (
                f"{teachers_names[:typo.span(1)[0]]}.{teachers_names[typo.span(1)[1]:]}"
            )

        def fix_typos(formatted_name: str):
            # Format names to "Иванов И.И." format
            re_name = r"([а-яА-ЯёЁ]+)\s+([а-яА-ЯёЁ]+)\.?\s*([а-яА-ЯёЁ]+)\.?"

            fixed = re.sub(re_name, r"\g<1> \g<2>.\g<3>.", formatted_name).strip()

            if not fixed or abs(len(formatted_name) - len(formatted_name)) > 3:
                return formatted_name

            return fixed

        names = re.split(self._RE_SEPARATORS, teachers_names)

        def parse_teacher_subgroups(
            cell_value: str,
        ) -> list[tuple[str, int | None]] | None:
            """Parse teacher subgroups from teacher name.
            Returns list of tuples with teacher name and subgroup number.
            Or None if no subgroups found in teacher names cell.

            Example:
                "Казачкова О.А.,1 пг\nИванова И.С.,2 пг" -> [("Казачкова О.А.", 1), ("Иванова И.С.", 2)]
                "Казачкова О.А.,1 пг\nИванова И.С" -> [("Казачкова О.А.", 1), ("Иванова И.С.", None)]
            """

            if not re.search(rf"(\d) ?{self._RE_SUBGROUPS}", cell_value):
                return None

            re_teacher = rf"([а-яА-ЯёЁ\- \.]+), ?(\d) ?{self._RE_SUBGROUPS}({self._RE_SEPARATORS})?|([а-яА-ЯёЁ\- \.]+)"

            re_teacher = re.compile(re_teacher, flags=re.I)
            teachers = re_teacher.findall(cell_value)

            if not teachers:
                return None

            result = []

            for teacher in teachers:
                teacher_name, subgroup, _, _, teacher_name_without_subgroup = teacher

                if (
                    len(teacher_name.strip()) < 3
                    and len(teacher_name_without_subgroup.strip()) < 3
                ):
                    continue

                if teacher_name and not teacher_name_without_subgroup:
                    teacher_name = fix_typos(teacher_name)
                elif teacher_name_without_subgroup and not teacher_name:
                    teacher_name_without_subgroup = fix_typos(
                        teacher_name_without_subgroup
                    )

                subgroup = int(subgroup) if subgroup else None
                if subgroup:
                    result.append((teacher_name.strip(), subgroup))
                else:
                    result.append((teacher_name_without_subgroup.strip(), None))

            return result

        def normalize_names(names_to_normalize: list[str]) -> list[str]:
            # Format names like "Иванов И.И.", "Иванов И. И.", "Иванов И И.", "Иванов И. И" and etc to "Иванов И.И."
            return [
                re.sub(
                    r"([а-яА-ЯёЁ\-]+) ([а-яА-ЯёЁ])\.? ?([а-яА-ЯёЁ])\.?",
                    r"\g<1> \g<2>.\g<3>.",
                    name,
                )
                for name in names_to_normalize
            ]

        if len(names) > 1:
            with_subgroups = parse_teacher_subgroups(names_cell_value)

            return with_subgroups or [
                name.strip()
                for name in normalize_names(names)
                if len(name.strip().replace(" ", "")) > 2
            ]

        # Names with initials (e.g. И.И. Иванов) may be separated by spaces
        re_teacher_name = r"(?:(?:(?:[а-яё\-]{1,}) +(?:[а-яё]{1}\. {0,2}){1,2})|(?:(?:[а-яё\-]{3,}) ?))"
        found = re.findall(re_teacher_name, teachers_names, flags=re.I)

        found = [fix_typos(name) for name in normalize_names(found)]

        return [x.strip() for x in found if len(x.strip()) > 2]

    def __get_lesson_type(
        self, type_name: str
    ) -> LessonType | TestSessionLessonType | None:
        """Get lesson type by name"""
        if type_name in [LessonType.PRACTICE.value, "п", "пр", "кр", "крпа"]:
            return LessonType.PRACTICE
        elif type_name in [LessonType.LECTURE.value, "лк", "лек", "л"]:
            return LessonType.LECTURE
        elif type_name in [LessonType.INDIVIDUAL_WORK.value, "ср"]:
            return LessonType.INDIVIDUAL_WORK
        elif type_name in [LessonType.LABORATORY_WORK.value, "лб", "лаб", "лр"]:
            return LessonType.LABORATORY_WORK
        elif type_name in [TestSessionLessonType.CREDIT.value, "зач", "з"]:
            return TestSessionLessonType.CREDIT
        elif type_name in [
            TestSessionLessonType.COURSE_WORK.value,
            "к/р",
            "защ кр",
            "защ к/р",
            "защ",
        ]:
            return TestSessionLessonType.COURSE_WORK
        elif type_name in [TestSessionLessonType.COURSE_PROJECT.value, "к/п"]:
            return TestSessionLessonType.COURSE_PROJECT
        elif type_name in [
            TestSessionLessonType.DIFFERENTIATED_CREDIT.value,
            "диф. зач",
            "д/з",
            "диф",
            "зд",
        ]:
            return TestSessionLessonType.DIFFERENTIATED_CREDIT
        else:
            logger.warning(f"Unknown lesson type: {type_name}")
            return None

    def get_weeks(self, lesson: str, is_even=None, max_weeks=None) -> list[list[int]]:
        result = []

        lesson = self.__fix_lesson_typos(lesson)

        lessons = self.__split_lessons(lesson)

        include_weeks = (
            r"(\b(\d+[-, ]*)+)((н|нед)?(?![.\s,\-\d]*(?:подгруппа|подгруп|подгр|п\/г|группа|гр))"
            r"(\.|\b))"
        )
        for lesson in lessons:
            lesson = lesson.lower()

            exclude_weeks = r"(\b(кр|кроме)(\.|\b)\s*)" + include_weeks

            exclude_weeks_substr = re.search(exclude_weeks, lesson)
            # 4 group is a week number
            exclude_weeks_substr = (
                "" if exclude_weeks_substr is None else exclude_weeks_substr[4]
            )

            # It is necessary to exclude the weeks on which the subject is not held
            lesson = re.sub(exclude_weeks, "", lesson)
            include_weeks_substr = re.search(include_weeks, lesson)
            include_weeks_substr = (
                "" if include_weeks_substr is None else include_weeks_substr[1]
            )

            # Remove unnecessary symbols
            include_weeks_substr = include_weeks_substr.strip()
            exclude_weeks_substr = exclude_weeks_substr.strip()

            # Get weeks from the string
            nums_include_weeks = self.__parse_weeks(include_weeks_substr, is_even)
            nums_exclude_weeks = self.__parse_weeks(exclude_weeks_substr, is_even)

            total_weeks = []

            # if inclusion weeks are not specified, but exclusion weeks are specified, then this means that the subject
            # takes place on all weeks except exception weeks
            if len(nums_include_weeks) == 0 and len(nums_exclude_weeks) > 0:
                total_weeks.extend(
                    i
                    for i in range(1, max_weeks + 1)
                    if i not in nums_exclude_weeks
                    and (
                        is_even is not None
                        and bool(i % 2) != is_even
                        or is_even is None
                    )
                )

            elif len(nums_include_weeks) > 0:
                total_weeks.extend(
                    week
                    for week in nums_include_weeks
                    if week not in nums_exclude_weeks
                )

            elif len(nums_include_weeks) == 0 and len(nums_exclude_weeks) == 0:
                if max_weeks is None:
                    raise ValueError(
                        "No weeks specified for lesson. Please specify max_weeks parameter"
                    )

                total_weeks.extend(
                    i
                    for i in range(1, max_weeks + 1)
                    if is_even is not None and bool(i % 2) != is_even or is_even is None
                )

            result.append(total_weeks)

        return result

    def get_lessons(
        self, lessons_cell_value: str
    ) -> list[tuple[str, LessonType | None, int | None]]:
        lesson = self.__fix_lesson_typos(lessons_cell_value)

        lessons = self.__format_subgroups(self.__split_lessons(lesson))
        result = []

        for i in range(len(lessons)):
            types = re.findall(self._RE_LESSON_TYPES, lessons[i][0])

            if len(types) > 0:
                lesson_type = self.__get_lesson_type(types[0].lower().strip())
                result.append(
                    (
                        self.__get_only_lesson_name(lessons[i][0]),
                        lesson_type,
                        lessons[i][1],
                    )
                )
            else:
                result.append(
                    (self.__get_only_lesson_name(lessons[i][0]), None, lessons[i][1])
                )

        return [lesson for lesson in result if lesson[0].strip() != ""]

    def get_types(self, cell_value: str) -> list[LessonType]:
        # Because `/` can be used to separate multiple types, need to make sure that the type for individual work
        # will not be split
        cell_value = cell_value.replace("с/р", "ср")

        types = re.split(self._RE_SEPARATORS, cell_value)

        return [self.__get_lesson_type(el.strip().lower()) for el in types if el != ""]
