"""POC Page Classifier — rule-based классификатор страниц PDF документов СМК.

Определяет тип каждой страницы (cover, approval_sheet, appendix, content)
для routing в extraction pipeline.

TASK-005 | POC | read-only для input2/
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageClass:
    page_type: str
    confidence: float
    signals: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PageClassifier — rule-based эвристики для одной страницы
# ---------------------------------------------------------------------------

DOC_CODE_RE = re.compile(
    r"(ДП|РГ|КД|СТ|РД|РИ|ИОТ|TPM|DP|KD)[-–—]"
)

NUMBERED_SECTION_RE = re.compile(
    r"^\s*\d+(\.\d+){0,4}\.?\s+\S", re.MULTILINE
)

APPENDIX_START_RE = re.compile(
    r"^\s*Приложение\s*(№?\s*\d+|[А-ЯA-Z])?", re.MULTILINE | re.IGNORECASE
)


class PageClassifier:
    """Классифицирует одну страницу PDF по тексту."""

    COVER_KEYWORDS = [
        "УТВЕРЖДАЮ", "УТВЕРЖДЕНО", "Генеральный директор",
        "Введен в действие", "Введён в действие",
        "ВВЕДЕН В ДЕЙСТВИЕ", "ВВЕДЁН В ДЕЙСТВИЕ",
        "СИСТЕМА МЕНЕДЖМЕНТА КАЧЕСТВА",
    ]

    COVER_OCR_PATTERNS = [
        re.compile(r"[yY]TBEP.{0,3}(AE|ДЕ)"),
        re.compile(r"eHep.{0,3}(bH|ьн).{0,5}(A|Д).{0,3}(peKTop|ректор)", re.IGNORECASE),
        re.compile(r"CIICTEM.{0,3}MEHEAXMEHT"),
    ]

    APPROVAL_KEYWORDS = [
        "Лист согласования", "СОГЛАСОВАНО", "Лист ознакомления",
        "Подпись", "Дата ознакомления", "Должность",
        "ЛИСТ СОГЛАСОВАНИЯ", "ЛИСТ ОЗНАКОМЛЕНИЯ",
        "лист регистрации изменений", "ЛИСТ РЕГИСТРАЦИИ ИЗМЕНЕНИЙ",
    ]

    APPENDIX_FORM_KEYWORDS = [
        "Форма", "Шаблон", "Бланк", "Образец",
        "ФОРМА", "ШАБЛОН", "БЛАНК", "ОБРАЗЕЦ",
    ]

    def classify_page(
        self,
        page_text: str,
        page_num: int,
        total_pages: int,
        metadata: dict | None = None,
    ) -> PageClass:
        candidates: list[PageClass] = []

        candidates.append(self._check_cover(page_text, page_num, total_pages))
        candidates.append(self._check_approval(page_text, page_num, total_pages))
        candidates.append(self._check_appendix(page_text, page_num, total_pages))

        best = max(candidates, key=lambda c: c.confidence)
        if best.confidence >= 0.4:
            return best

        return self._make_content(page_text)

    # -- cover ---------------------------------------------------------------

    def _check_cover(
        self, text: str, page_num: int, total_pages: int,
    ) -> PageClass:
        signals: list[str] = []
        score = 0.0

        non_empty = [ln for ln in text.splitlines() if ln.strip()]

        if page_num == 1 and len(non_empty) == 0:
            signals.append("empty_first_page (scanned cover)")
            return PageClass(page_type="cover", confidence=0.85, signals=signals)

        if page_num <= 2:
            signals.append(f"page_num={page_num} (≤2)")
            score += 0.25

        kw_hits = [kw for kw in self.COVER_KEYWORDS if kw in text]
        if kw_hits:
            signals.append(f"keywords: {kw_hits}")
            score += 0.15 * min(len(kw_hits), 3)

        ocr_hits = [p.pattern for p in self.COVER_OCR_PATTERNS if p.search(text)]
        if ocr_hits:
            signals.append(f"ocr_cover_patterns ({len(ocr_hits)})")
            score += 0.2 * min(len(ocr_hits), 2)

        if page_num <= 2:
            if DOC_CODE_RE.search(text):
                signals.append("doc_code_pattern")
                score += 0.15
            if "ПРЕДИСЛОВИЕ" in text or "ПРЕДИСЛОВИ" in text:
                signals.append("preface_marker")
                score += 0.15

        if len(non_empty) < 20:
            signals.append(f"short_page ({len(non_empty)} lines)")
            score += 0.1

        return PageClass(page_type="cover", confidence=min(score, 1.0), signals=signals)

    # -- approval_sheet ------------------------------------------------------

    def _check_approval(
        self, text: str, page_num: int, total_pages: int,
    ) -> PageClass:
        signals: list[str] = []
        score = 0.0

        kw_hits = [kw for kw in self.APPROVAL_KEYWORDS if kw.lower() in text.lower()]
        if kw_hits:
            signals.append(f"keywords: {kw_hits}")
            score += 0.2 * min(len(kw_hits), 3)

        if total_pages > 2 and page_num >= total_pages - 5:
            signals.append(f"near_end (page {page_num}/{total_pages})")
            score += 0.15

        lines = text.splitlines()
        non_empty = [ln for ln in lines if ln.strip()]
        if non_empty:
            short_lines = sum(1 for ln in non_empty if len(ln.strip()) < 40)
            ratio = short_lines / len(non_empty)
            if ratio > 0.6:
                signals.append(f"tabular_structure (short_ratio={ratio:.2f})")
                score += 0.15

        fio_pattern = re.search(
            r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.", text,
        )
        if fio_pattern:
            signals.append("fio_pattern")
            score += 0.1

        return PageClass(
            page_type="approval_sheet", confidence=min(score, 1.0), signals=signals,
        )

    # -- appendix ------------------------------------------------------------

    def _check_appendix(
        self, text: str, page_num: int, total_pages: int,
    ) -> PageClass:
        signals: list[str] = []
        score = 0.0

        if APPENDIX_START_RE.search(text):
            signals.append("starts_with_appendix")
            score += 0.35

        form_hits = [kw for kw in self.APPENDIX_FORM_KEYWORDS if kw in text]
        if form_hits:
            signals.append(f"form_keywords: {form_hits}")
            score += 0.15

        if total_pages > 3 and page_num > total_pages * 0.6:
            signals.append(f"after_60pct (page {page_num}/{total_pages})")
            score += 0.15

        return PageClass(
            page_type="appendix", confidence=min(score, 1.0), signals=signals,
        )

    # -- content (default) ---------------------------------------------------

    def _make_content(self, text: str) -> PageClass:
        signals: list[str] = []
        sections = NUMBERED_SECTION_RE.findall(text)
        if sections:
            signals.append(f"numbered_sections ({len(sections)})")
        signals.append("default_type")
        return PageClass(page_type="content", confidence=0.5, signals=signals)


# ---------------------------------------------------------------------------
# DocumentClassifier — обработка целого PDF
# ---------------------------------------------------------------------------

class DocumentClassifier:
    """Классифицирует все страницы PDF-документа."""

    def __init__(self) -> None:
        self._page_clf = PageClassifier()

    def classify_document(self, pdf_path: Path) -> list[PageClass]:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        results: list[PageClass] = []

        for page_idx in range(total_pages):
            page = doc[page_idx]
            text = page.get_text()
            page_num = page_idx + 1  # 1-based
            pc = self._page_clf.classify_page(text, page_num, total_pages)
            results.append(pc)

        doc.close()
        return results

    @staticmethod
    def summary(results: list[PageClass]) -> dict:
        type_counts: dict[str, int] = {}
        type_conf_sum: dict[str, float] = {}

        for pc in results:
            type_counts[pc.page_type] = type_counts.get(pc.page_type, 0) + 1
            type_conf_sum[pc.page_type] = type_conf_sum.get(pc.page_type, 0.0) + pc.confidence

        avg_conf = {
            t: type_conf_sum[t] / type_counts[t] for t in type_counts
        }

        return {
            "total_pages": len(results),
            "type_counts": type_counts,
            "avg_confidence": {t: round(v, 3) for t, v in avg_conf.items()},
        }


# ---------------------------------------------------------------------------
# main — тестирование на реальных PDF
# ---------------------------------------------------------------------------

ROUTING = {
    "cover": "Metadata only",
    "approval_sheet": "Skip extraction, metadata only",
    "appendix": "Parse as FORM_TEMPLATE",
    "content": "Full extraction pipeline",
}

TEST_PDFS = [
    # ДП (должностная процедура)
    Path("input2/BND/pdf/ДП-Б1.007-07 ^6DDA144DEE7164CC45258512003199A7/"
         "ДП-Б1.007-07 (Эталон №4 для печати).pdf"),
    # ДП-М (другой тип ДП)
    Path("input2/BND/pdf/ДП-М1.020-06 ^692386276D6DDE30452584F50038090F/"
         "ДП-М1.020-06 (Эталон №15 для печати).pdf"),
    # КД-РГ
    Path("input2/BND/pdf/КД-РГ-039-05 ^98922A5C1D13C8AF45258B0400287F5F/"
         "КД-РГ-039-05 (эталон №1 для печати).pdf"),
    # РГ (регламент)
    Path("input2/BND/pdf/РГ-004-05 ^F7FDA156A0186BDA45258CE00046D2A9/"
         "РГ-004-05 (Эталон для печати).pdf"),
    # ИОТ
    Path("input2/BND/pdf/ИОТ-001-02 ^0E02046716E6B8434525880F004081C1/"
         "ИОТ-001-02 (Эталон для печати).pdf"),
]


def main() -> None:
    clf = DocumentClassifier()

    all_summaries: list[dict] = []

    for pdf_path in TEST_PDFS:
        print("=" * 80)
        print(f"📄 {pdf_path.name}")
        print(f"   Путь: {pdf_path}")

        if not pdf_path.exists():
            print("   ⚠️  Файл не найден, пропускаю")
            print()
            continue

        try:
            results = clf.classify_document(pdf_path)
        except Exception as exc:
            print(f"   ❌ Ошибка: {exc}")
            print()
            continue

        for i, pc in enumerate(results, 1):
            routing = ROUTING.get(pc.page_type, "?")
            print(
                f"   стр. {i:>3}: {pc.page_type:<16} "
                f"conf={pc.confidence:.2f}  "
                f"→ {routing}"
            )
            if pc.signals:
                print(f"            сигналы: {pc.signals}")

        s = clf.summary(results)
        all_summaries.append({"file": pdf_path.name, **s})

        print(f"\n   Сводка: {s['total_pages']} стр. | "
              f"типы: {s['type_counts']} | "
              f"avg conf: {s['avg_confidence']}")
        print()

    # Общая сводка
    print("=" * 80)
    print("📊 ОБЩАЯ СВОДКА")
    print("=" * 80)
    total_type_counts: dict[str, int] = {}
    total_pages = 0
    for s in all_summaries:
        total_pages += s["total_pages"]
        for t, c in s["type_counts"].items():
            total_type_counts[t] = total_type_counts.get(t, 0) + c

    print(f"Документов обработано: {len(all_summaries)}")
    print(f"Всего страниц: {total_pages}")
    print(f"По типам: {total_type_counts}")
    for t, c in sorted(total_type_counts.items()):
        pct = c / total_pages * 100 if total_pages else 0
        print(f"  {t:<16}: {c:>4} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
