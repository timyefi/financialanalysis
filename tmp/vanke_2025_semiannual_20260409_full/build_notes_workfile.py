from __future__ import annotations

import json
import re
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
MD_PATH = RUN_DIR / "mineru" / "万科A：2025年半年度财务报告" / "万科A：2025年半年度财务报告.md"
OUT_PATH = RUN_DIR / "notes_workfile.json"


def main() -> None:
    lines = MD_PATH.read_text(encoding="utf-8").splitlines()
    notes_section_line = None
    for idx, line in enumerate(lines, start=1):
        if "合并财务报表项目注释" in line:
            notes_section_line = idx
            break
    if notes_section_line is None:
        raise SystemExit("cannot locate notes section")

    main_note_re = re.compile(r"^#\s*(\d+)、\s*(.+?)\s*$")
    notes = []
    seen = set()
    for idx in range(notes_section_line + 1, len(lines) + 1):
        line = lines[idx - 1].strip()
        match = main_note_re.match(line)
        if not match:
            continue
        note_no = match.group(1)
        if note_no in seen:
            continue
        seen.add(note_no)
        notes.append(
            {
                "note_no": note_no,
                "chapter_title": match.group(2).strip(),
                "start_line": idx,
                "end_line": None,
                "evidence": [line[:200]],
            }
        )

    if not notes:
        raise SystemExit("no note headings found")

    for index, note in enumerate(notes):
        note["end_line"] = notes[index + 1]["start_line"] - 1 if index + 1 < len(notes) else len(lines)

    notes_workfile = {
        "notes_start_line": notes_section_line,
        "notes_end_line": len(lines),
        "locator_evidence": [
            {
                "step": "keyword_search",
                "keyword": "合并财务报表项目注释",
                "excerpt": lines[notes_section_line - 1][:200],
            },
            {
                "step": "sample_read",
                "keyword": notes[0]["chapter_title"],
                "excerpt": notes[0]["evidence"][0],
            },
        ],
        "notes_catalog": notes,
    }
    OUT_PATH.write_text(json.dumps(notes_workfile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"notes_start_line={notes_section_line}")
    print(f"notes_end_line={len(lines)}")
    print(f"notes_count={len(notes)}")
    print(f"first_note={notes[0]['note_no']} {notes[0]['chapter_title']} {notes[0]['start_line']}")
    print(f"last_note={notes[-1]['note_no']} {notes[-1]['chapter_title']} {notes[-1]['start_line']}")


if __name__ == "__main__":
    main()
