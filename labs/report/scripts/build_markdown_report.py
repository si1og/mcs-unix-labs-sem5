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


def screenshot_map() -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in IMAGE_DIR.iterdir():
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        match = re.match(r"^(\d+\.\d+)_", path.name)
        if match:
            grouped[match.group(1)].append(path)
    for paths in grouped.values():
        paths.sort(key=lambda path: natural_key(path.name))
    return grouped


def escape_markdown(text: str) -> str:
    # Preserve shell notation that Markdown could otherwise treat as markup.
    return text.replace("`", "\\`").replace("<", "&lt;")


def image_title(path: Path) -> str:
    label = path.stem.split("_", 1)[-1].replace("_", " ")
    return label[:1].upper() + label[1:]


def append_images(output: list[str], exercise: str,
                  images: dict[str, list[Path]]) -> None:
    paths = images.get(exercise, [])
    if not paths:
        return
    output.extend(["", "### Результаты выполнения", ""])
    for path in paths:
        relative = path.relative_to(REPORT_DIR).as_posix()
        title = image_title(path)
        output.append(f"**{title}**")
        output.append("")
        output.append(
            f'<img src="{relative}" alt="{title}" '
            'style="max-width: 100%; height: auto;">'
        )
        output.append("")


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

    for block in blocks:
        lab_match = re.match(r"^Лабораторная работа\s+(\d+)\.\s*(.*)$", block,
                             flags=re.IGNORECASE)
        exercise_match = re.match(r"^Упражнение\s+(\d+\.\d+)\.\s*(.*)$", block,
                                  flags=re.IGNORECASE)

        if lab_match:
            if current_exercise:
                append_images(output, current_exercise, images)
                current_exercise = None
            output.extend(["", f"# Лабораторная работа {lab_match.group(1)}. "
                           f"{escape_markdown(lab_match.group(2))}", ""])
            continue

        if exercise_match:
            if current_exercise:
                append_images(output, current_exercise, images)
            current_exercise = exercise_match.group(1)
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
                append_images(output, current_exercise, images)
                current_exercise = None
            level = "#" if block.lower().startswith("основы") else "##"
            output.extend(["", f"{level} {escape_markdown(block)}", ""])
            continue

        text = escape_markdown(block)
        numbered = re.match(r"^(\d+)\.\s*(.*)$", text)
        lettered = re.match(r"^([a-zа-я])\.\s*(.*)$", text,
                            flags=re.IGNORECASE)
        if numbered:
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

    if current_exercise:
        append_images(output, current_exercise, images)

    return "\n".join(output).rstrip() + "\n"


def main() -> None:
    OUTPUT.write_text(build_markdown(), encoding="utf-8")
    content = OUTPUT.read_text(encoding="utf-8")
    exercises = len(re.findall(r"^## Упражнение ", content, flags=re.MULTILINE))
    images = len(re.findall(r"^<img ", content, flags=re.MULTILINE))
    print(f"Wrote {OUTPUT} ({exercises} exercises, {images} embedded images)")


if __name__ == "__main__":
    main()
