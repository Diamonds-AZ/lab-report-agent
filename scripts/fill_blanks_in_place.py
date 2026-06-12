from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
BLANK_RE = re.compile(r"_{3,}|（\s*）|\(\s*\)|【\s*】")
FORBIDDEN_PREFIXES = ("填写：", "应填入：", "答案：")


@dataclass
class FillResult:
    anchor: str
    answer: str
    strategy: str
    success: bool


def matching_paragraphs(doc: Document, anchor: str) -> Iterable:
    for paragraph in doc.paragraphs:
        if anchor in paragraph.text:
            yield paragraph
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if anchor in paragraph.text:
                        yield paragraph


def replace_paragraph_text(paragraph, new_text: str, underline_inserted: bool = False):
    runs = paragraph.runs
    if not runs:
        run = paragraph.add_run(new_text)
        run.underline = underline_inserted
        return
    runs[0].text = new_text
    runs[0].underline = underline_inserted
    for run in runs[1:]:
        run.text = ""


def replace_blank_in_paragraph(paragraph, answer: str) -> bool:
    for run in paragraph.runs:
        text = run.text or ""
        if BLANK_RE.search(text):
            run.text = BLANK_RE.sub(answer, text, count=1)
            run.underline = True
            return True
        if re.fullmatch(r" {4,}|\t+", text):
            run.text = answer
            run.underline = True
            return True
    return False


def fill_near_anchor(doc: Document, anchor: str, answer: str, occurrence: int = 0) -> FillResult:
    matches = list(matching_paragraphs(doc, anchor))
    if occurrence >= len(matches):
        return FillResult(anchor, answer, "anchor_not_found", False)

    anchor_para = matches[occurrence]
    if replace_blank_in_paragraph(anchor_para, answer):
        return FillResult(anchor, answer, "same_paragraph_blank", True)

    body = list(anchor_para._parent._element)
    try:
        idx = body.index(anchor_para._p)
    except ValueError:
        idx = -1

    if idx >= 0:
        from docx.text.paragraph import Paragraph

        for element in body[idx + 1 : idx + 5]:
            if element.tag.endswith("}p"):
                paragraph = Paragraph(element, anchor_para._parent)
                if replace_blank_in_paragraph(paragraph, answer):
                    return FillResult(anchor, answer, "nearby_blank_paragraph", True)

    return FillResult(anchor, answer, "no_blank_found", False)


def audit_docx(path: Path) -> dict:
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    all_text = text + "\n" + table_text
    return {
        "remaining_underscore_blanks": len(re.findall(r"_{3,}", all_text)),
        "forbidden_fill_prefixes": [x for x in FORBIDDEN_PREFIXES if x in all_text],
        "tables": len(doc.tables),
        "inline_shapes": len(doc.inline_shapes),
    }


if __name__ == "__main__":
    target = ROOT / "output" / "reports" / "流程测试_实验报告_语义填空测试.docx"
    if target.exists():
        print(audit_docx(target))
    else:
        print("No generated report found for audit.")
