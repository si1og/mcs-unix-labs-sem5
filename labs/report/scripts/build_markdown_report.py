#!/usr/bin/env python3
"""Build the Markdown version of the UNIX laboratory workbook.

The assignment text is extracted from the original PDF. Existing screenshots
are grouped by exercise from their stable filename prefix (for example,
``4.3_`` or ``6.2_``) and embedded directly into the document.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path


REPORT_DIR = Path(__file__).resolve().parents[1]
SOURCE_PDF = REPORT_DIR / "tex/graphics/labs.pdf"
IMAGE_DIR = REPORT_DIR / "img/lab1"
OUTPUT = REPORT_DIR / "lab1-filled.md"


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", value)]


def screenshot_sort_key(exercise: str, path: Path) -> tuple[object, ...]:
    """Keep screenshots in the command order used to perform each task."""
    if exercise == "5.2":
        suffix = path.stem[len(exercise) + 1:]
        command_order = {
            "1_touch": 0,
            "1_ls": 1,
            "2a_umask.png": 0,
            "2a_umask_symbolic": 1,
            "2b_umask": 0,
            "2b_touch": 1,
            "2b_ls": 2,
            "2c_umask": 0,
            "2c_touch": 1,
            "2c_ls": 2,
            "3a_touch": 0,
            "3a_chmod": 1,
            "3a_ls": 2,
            "3b_touch": 0,
            "3b_chmod": 1,
            "3b_ls": 2,
            "3c_mkdir": 0,
            "3c_chmod": 1,
            "3c_ls": 2,
            "3d_mkdir": 0,
            "3d_chmod": 1,
            "3d_ls": 2,
        }
        for prefix, rank in command_order.items():
            if suffix.startswith(prefix.removesuffix(".png")):
                return (rank, *natural_key(path.name))
    return (99, *natural_key(path.name))


def extract_pages() -> list[list[str]]:
    result = subprocess.run(
        ["pdftotext", "-raw", str(SOURCE_PDF), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    pages = result.stdout.split("\f")
    # Page 1 is the table of contents. The complete conditions begin on page 2.
    pages = pages[1:]
    cleaned: list[list[str]] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        while lines and re.fullmatch(r"\d+", lines[0]):
            lines.pop(0)
        while lines and re.fullmatch(r"\d+", lines[-1]):
            lines.pop()
        if lines:
            cleaned.append(lines)
    return cleaned


def is_heading(line: str) -> bool:
    return bool(re.match(
        r"^(?:Лабораторная работа\s+\d+\.|Упражнение\s+\d+\.\d+\.|"
        r"Основы программирования|Создание скелета сценария|"
        r"Реализация алгоритма сценария)",
        line,
        flags=re.IGNORECASE,
    ))


def is_block_start(line: str) -> bool:
    return bool(
        is_heading(line)
        or re.match(r"^\d+\.\s*", line)
        or re.match(r"^[a-zа-я]\.\s+", line, flags=re.IGNORECASE)
        or line.startswith("•")
        or line.startswith("Примечание:")
        or line.startswith("Лабораторная работа зачтена:")
        or line.startswith("Дата:")
        or line.startswith("Подпись преподавателя:")
    )


def logical_blocks(pages: list[list[str]]) -> list[str]:
    blocks: list[str] = []
    for lines in pages:
        for line in lines:
            if is_block_start(line) or not blocks:
                blocks.append(line)
            else:
                blocks[-1] += " " + line
    return [re.sub(r"\s+", " ", block).strip() for block in blocks]


def image_target(exercise: str, path: Path) -> tuple[str | None, str | None]:
    """Return ``(parent number, subpoint)`` encoded in an image name."""
    suffix = path.stem[len(exercise) + 1:]

    # A few early screenshots received descriptive names before the naming
    # scheme was established.
    if exercise == "4.1":
        if suffix.startswith("1_root_"):
            return None, "a"
        if suffix.startswith("2_"):
            return None, "b"
    if exercise == "1.8" and suffix.startswith("6_wall"):
        return "4", None
    if exercise == "4.3" and suffix.startswith("ab_"):
        return None, "b"
    if exercise == "7.2":
        if suffix == "vim_navigation":
            return "1", "a"
        if suffix in {"vim_insert", "vim_append"}:
            return "1", "f"
        if suffix.startswith("vim_delete"):
            return "1", "g"

    match = re.match(r"^(\d+)_([a-z])(?:_|$)", suffix)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^(\d+)([a-z])(?:_|$)", suffix)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^(\d+)(?:_|$)", suffix)
    if match:
        return match.group(1), None
    match = re.match(r"^([a-z])(?:_|$)", suffix)
    if match:
        return None, match.group(1)
    return None, None


def screenshot_map() -> dict[
        str, dict[tuple[str | None, str | None], list[Path]]]:
    grouped: dict[
        str, dict[tuple[str | None, str | None], list[Path]]
    ] = defaultdict(lambda: defaultdict(list))
    for path in IMAGE_DIR.iterdir():
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        # These two crops show the same `ls /` output. Keep the first one so
        # the report does not repeat an identical screenshot.
        if path.name == "4.1_1_root_2.png":
            continue
        match = re.match(r"^(\d+\.\d+)_", path.name)
        if match:
            exercise = match.group(1)
            grouped[exercise][image_target(exercise, path)].append(path)
    for exercise, targets in grouped.items():
        for paths in targets.values():
            paths.sort(key=lambda path: screenshot_sort_key(exercise, path))
    return grouped


def append_exercise_notes(output: list[str], exercise: str | None,
                          marker: str | None) -> None:
    """Insert concise observations that belong to a specific subpoint."""
    if exercise == "4.2" and marker == "f":
        output.extend([
            "Обозначение типа объекта первым символом в выводе `ls -l`:",
            "",
            "| Символ | Тип объекта |",
            "|---|---|",
            "| `-` | обычный файл |",
            "| `d` | каталог |",
            "| `b` | блочное устройство |",
            "| `c` | символьное устройство |",
            "| `p` | именованный канал (FIFO) |",
            "| `s` | сокет |",
            "| `l` | символическая ссылка |",
            "",
            "Поля строки `ls -l` слева направо:",
            "",
            "| Поле | Что обозначает |",
            "|---|---|",
            "| `-rw-r--r--` | тип объекта и права владельца, группы и остальных пользователей |",
            "| `1` | количество жёстких ссылок |",
            "| `root` | владелец |",
            "| `root` | группа |",
            "| `1234` | размер в байтах; для устройства — номера `major, minor` |",
            "| дата и время | время последнего изменения содержимого |",
            "| имя | имя объекта; у символической ссылки также выводится `-> цель` |",
            "",
        ])
        return
    if exercise != "4.1" or marker != "c":
        return
    output.extend([
        "| Каталог | Назначение |",
        "|---|---|",
        "| `/` | Корень файловой системы. |",
        "| `/etc` | Системные настройки. |",
        "| `/home` | Домашние каталоги пользователей. |",
        "| `/usr` | Программы, библиотеки и общие данные. |",
        "| `/var` | Изменяемые данные и журналы. |",
        "| `/tmp` | Временные файлы. |",
        "| `/dev` | Файлы устройств. |",
        "| `/proc`, `/sys` | Интерфейсы ядра. |",
        "| `/run` | Данные работающих служб. |",
        "| `/boot` | Файлы загрузки. |",
        "",
    ])


def escape_markdown(text: str) -> str:
    # Preserve shell notation that Markdown could otherwise treat as markup.
    return text.replace("`", "\\`").replace("<", "&lt;")


def image_title(path: Path) -> str:
    label = path.stem.split("_", 1)[-1].replace("_", " ")
    return label[:1].upper() + label[1:]


def append_image_paths(output: list[str], paths: list[Path],
                       used: set[Path]) -> None:
    for path in paths:
        if path in used:
            continue
        relative = path.relative_to(REPORT_DIR).as_posix()
        title = image_title(path)
        used.add(path)
        output.append(
            f'<img src="{relative}" alt="{title}" '
            'style="max-width: 100%; height: auto;">'
        )
        output.append("")


def append_target_images(
    output: list[str],
    exercise: str | None,
    parent: str | None,
    marker: str | None,
    images: dict[str, dict[tuple[str | None, str | None], list[Path]]],
    used: set[Path],
) -> None:
    if not exercise:
        return
    targets = images.get(exercise, {})
    keys = [(parent, marker)]
    if marker is not None:
        keys.append((None, marker))
    for key in keys:
        append_image_paths(output, targets.get(key, []), used)


def append_remaining_images(
    output: list[str],
    exercise: str | None,
    images: dict[str, dict[tuple[str | None, str | None], list[Path]]],
    used: set[Path],
) -> None:
    if not exercise:
        return
    for paths in images.get(exercise, {}).values():
        append_image_paths(output, paths, used)


def build_markdown() -> str:
    blocks = logical_blocks(extract_pages())
    images = screenshot_map()
    output = [
        "# Лабораторные работы по UNIX",
        "",
        "> Условия сохранены по исходному заданию `tex/graphics/labs.pdf`. "
        "Результаты выполнения встроены непосредственно в соответствующие упражнения. "
        "LaTeX-версия отчёта сохранена отдельно.",
        "",
    ]
    current_exercise: str | None = None
    current_parent: str | None = None
    used_images: set[Path] = set()

    for block in blocks:
        lab_match = re.match(r"^Лабораторная работа\s+(\d+)\.\s*(.*)$", block,
                             flags=re.IGNORECASE)
        exercise_match = re.match(r"^Упражнение\s+(\d+\.\d+)\.\s*(.*)$", block,
                                  flags=re.IGNORECASE)

        if lab_match:
            if current_exercise:
                append_remaining_images(output, current_exercise, images,
                                        used_images)
                current_exercise = None
                current_parent = None
            output.extend(["", f"# Лабораторная работа {lab_match.group(1)}. "
                           f"{escape_markdown(lab_match.group(2))}", ""])
            continue

        if exercise_match:
            if current_exercise:
                append_remaining_images(output, current_exercise, images,
                                        used_images)
            current_exercise = exercise_match.group(1)
            current_parent = None
            heading_text = exercise_match.group(2)
            intro = ""
            intro_match = re.search(r"\s+(?=(?:При помощи|Примечание:))",
                                    heading_text)
            if intro_match:
                intro = heading_text[intro_match.end():]
                heading_text = heading_text[:intro_match.start()]
            output.extend(["", f"## Упражнение {current_exercise}. "
                           f"{escape_markdown(heading_text)}", ""])
            if intro:
                output.extend([escape_markdown(intro), ""])
            continue

        if re.match(r"^(?:Основы программирования|Создание скелета сценария|"
                    r"Реализация алгоритма сценария)", block,
                    flags=re.IGNORECASE):
            if current_exercise:
                append_remaining_images(output, current_exercise, images,
                                        used_images)
                current_exercise = None
                current_parent = None
            level = "#" if block.lower().startswith("основы") else "##"
            output.extend(["", f"{level} {escape_markdown(block)}", ""])
            continue

        text = escape_markdown(block)
        numbered = re.match(r"^(\d+)\.\s*(.*)$", text)
        lettered = re.match(r"^([a-zа-я])\.\s*(.*)$", text,
                            flags=re.IGNORECASE)
        if numbered:
            current_parent = numbered.group(1)
            output.append(f"{numbered.group(1)}. {numbered.group(2)}")
        elif lettered:
            output.append(f"   - **{lettered.group(1)}.** {lettered.group(2)}")
        elif text.startswith("•"):
            output.append(f"- {text[1:].strip()}")
        elif text in {"Дата:", "Подпись преподавателя:",
                      "Лабораторная работа зачтена:"}:
            output.append(f"**{text}**")
        else:
            output.append(text)
        output.append("")

        if numbered:
            append_target_images(output, current_exercise, current_parent,
                                 None, images, used_images)
        elif lettered:
            append_target_images(output, current_exercise, current_parent,
                                 lettered.group(1).lower(), images, used_images)
            append_exercise_notes(output, current_exercise,
                                  lettered.group(1).lower())

    if current_exercise:
        append_remaining_images(output, current_exercise, images, used_images)

    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    OUTPUT.write_text(build_markdown(), encoding="utf-8")
    content = OUTPUT.read_text(encoding="utf-8")
    exercises = len(re.findall(r"^## Упражнение ", content, flags=re.MULTILINE))
    images = len(re.findall(r"^<img ", content, flags=re.MULTILINE))
    print(f"Wrote {OUTPUT} ({exercises} exercises, {images} embedded images)")


if __name__ == "__main__":
    main()
