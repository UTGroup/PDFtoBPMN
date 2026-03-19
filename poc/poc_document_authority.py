"""
POC Document Authority — парсинг кодов документов СМК,
определение семейств, версий и authority.

TASK-004: standalone POC, не импортирует из core/.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


DOC_TYPE_NAMES: dict[str, str] = {
    "ДП": "Должностная процедура",
    "РГ": "Регламент",
    "РД": "Руководящий документ",
    "РИ": "Рабочая инструкция",
    "СТ": "Стандарт",
    "ИОТ": "Инструкция по охране труда",
    "РК": "Руководство по качеству",
    "СТО": "Стандарт организации",
    "ПР": "Процедура",
    "TPM": "TPM документ",
}

KNOWN_TYPES = {"ДП", "РГ", "РД", "РИ", "СТ", "ИОТ", "РК", "СТО", "ПР", "TPM"}
KNOWN_PREFIXES = {"КД"}

FORMAT_PRIORITY = {"pdf": 4, "docx": 3, "bpmn": 2, "md": 1, "xlsx": 0}
AUTHORITY_ORDER = ["canonical", "draft", "superseded", "archived"]

SKIP_NAMES = {
    "ocr_full_run", "Integrated_Pipeline",
    "ocr_run_20260127_185423.log",
}


@dataclass
class DocumentInfo:
    raw_name: str
    family_code: str
    version: Optional[int] = None
    doc_type: Optional[str] = None
    department: Optional[str] = None
    prefix: Optional[str] = None
    parse_method: str = "unknown"


@dataclass
class DocumentRecord:
    info: DocumentInfo
    format: str
    source_path: str
    authority: str = "canonical"


@dataclass
class DocumentFamily:
    family_code: str
    documents: list[DocumentRecord] = field(default_factory=list)

    def add_document(self, info: DocumentInfo, fmt: str, source_path: str) -> None:
        self.documents.append(DocumentRecord(info=info, format=fmt, source_path=source_path))

    def resolve_authority(self) -> dict:
        if not self.documents:
            return {}

        by_version: dict[Optional[int], list[DocumentRecord]] = {}
        for doc in self.documents:
            by_version.setdefault(doc.info.version, []).append(doc)

        versions_with_numbers = [v for v in by_version if v is not None]
        max_version = max(versions_with_numbers) if versions_with_numbers else None

        for doc in self.documents:
            doc.authority = "superseded"

        if max_version is not None:
            latest_docs = by_version[max_version]
        elif None in by_version:
            latest_docs = by_version[None]
        else:
            latest_docs = []

        best_format_priority = -1
        for doc in latest_docs:
            p = FORMAT_PRIORITY.get(doc.format, 0)
            if p > best_format_priority:
                best_format_priority = p

        for doc in latest_docs:
            p = FORMAT_PRIORITY.get(doc.format, 0)
            if p == best_format_priority:
                doc.authority = "canonical"
            else:
                doc.authority = "draft"

        return {
            "family_code": self.family_code,
            "total_documents": len(self.documents),
            "versions": sorted(v for v in by_version if v is not None),
            "canonical_count": sum(1 for d in self.documents if d.authority == "canonical"),
            "superseded_count": sum(1 for d in self.documents if d.authority == "superseded"),
        }


class DocumentCodeParser:
    """Парсит имена файлов/папок в структуру DocumentInfo."""

    # Паттерн 1: СТО_И38-2025_V3 (нестандартный с _V)
    _RE_STO = re.compile(
        r'^(СТО)_([A-Za-zА-Яа-я0-9]+[-][0-9]{4})_V(\d+)$'
    )

    # Паттерн 2: РК01-2017-07, РК02-2025-01 (нестандартный РК)
    _RE_RK = re.compile(
        r'^(РК\d+[-][0-9]{4})[-](\d+)$'
    )

    # Паттерн 3: КД-TYPE-DEPT.NUM-VER (с КД-префиксом, dept с точкой)
    _RE_KD_DEPT = re.compile(
        r'^(КД)[-](ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-]'
        r'([A-Za-zА-Яа-я0-9]+(?:\.[A-Za-zА-Яа-я0-9]+)*)\.(\d+)[-](\d+)$'
    )

    # Паттерн 3b: КД-TYPE-NUM-VER (с КД-префиксом, без dept)
    _RE_KD_NO_DEPT = re.compile(
        r'^(КД)[-](ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-](\d+)[-](\d+)$'
    )

    # Паттерн 4: TYPE-DEPT.NUM-VER (стандартный с dept через точку)
    _RE_STD_DEPT = re.compile(
        r'^(ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-]'
        r'([A-Za-zА-Яа-я0-9]+(?:\.[A-Za-zА-Яа-я0-9]+)*)\.(\d+)[-](\d+)$'
    )

    # Паттерн 5: TYPE-NUM-VER (стандартный без dept)
    _RE_STD_NO_DEPT = re.compile(
        r'^(ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-](\d+)[-](\d+)$'
    )

    # Паттерн 6: TPM-UTA-UTG-002-03 (TPM с составным dept)
    _RE_TPM = re.compile(
        r'^(TPM)[-]([A-Z]+-[A-Z]+)[-](\d+)[-](\d+)$'
    )

    # Паттерн 7: ДП-Б6001-07 (без точки в dept+number, dept слит с number)
    _RE_MERGED_DEPT_NUM = re.compile(
        r'^(КД[-])?(ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-]'
        r'([А-Яа-яA-Za-z]+)(\d{3,})[-](\d+)$'
    )

    # Паттерн 8: КД-ДП-Б7-008 (КД-TYPE-DEPT-NUM без версии и без точки)
    _RE_KD_DEPT_NO_VER = re.compile(
        r'^(КД)[-](ДП|РГ|РД|РИ|СТ|ИОТ|РК|СТО|ПР|TPM)[-]'
        r'([А-Яа-яA-Za-z]+\d*)[-](\d{3,})$'
    )

    # Паттерн 9: ВБК2026 — спецкоды без версии
    _RE_SPECIAL_NO_VER = re.compile(
        r'^(ВБК\d+)$'
    )

    def parse(self, filename: str) -> Optional[DocumentInfo]:
        name = self._clean_name(filename)
        if not name or name in SKIP_NAMES:
            return None

        for method in [
            self._try_sto,
            self._try_rk,
            self._try_tpm,
            self._try_kd_dept,
            self._try_kd_no_dept,
            self._try_kd_dept_no_ver,
            self._try_merged_dept_num,
            self._try_std_dept,
            self._try_std_no_dept,
            self._try_special_no_ver,
            self._try_human_readable,
        ]:
            result = method(name)
            if result is not None:
                return result

        return DocumentInfo(
            raw_name=name,
            family_code=name,
            parse_method="fallback",
        )

    def _clean_name(self, filename: str) -> str:
        name = filename.strip()
        for suffix in ["_OCR.md", "_OCR.docx", ".bpmn.backup",
                        ".bpmn", ".docx", ".pdf", ".md", ".html",
                        ".xlsx", ".py", ".log", ".json"]:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        name = name.strip()
        return name

    def _try_sto(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_STO.match(name)
        if not m:
            return None
        doc_type, body, ver = m.group(1), m.group(2), m.group(3)
        family = f"{doc_type}_{body}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            parse_method="sto_pattern",
        )

    def _try_rk(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_RK.match(name)
        if not m:
            return None
        family, ver = m.group(1), m.group(2)
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type="РК",
            parse_method="rk_pattern",
        )

    def _try_tpm(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_TPM.match(name)
        if not m:
            return None
        doc_type, dept, num, ver = m.group(1), m.group(2), m.group(3), m.group(4)
        family = f"{doc_type}-{dept}-{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type, department=dept,
            parse_method="tpm_pattern",
        )

    def _try_kd_dept(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_KD_DEPT.match(name)
        if not m:
            return None
        prefix, doc_type = m.group(1), m.group(2)
        dept, num, ver = m.group(3), m.group(4), m.group(5)
        family = f"{prefix}-{doc_type}-{dept}.{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            department=dept, prefix=prefix,
            parse_method="kd_dept_pattern",
        )

    def _try_kd_no_dept(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_KD_NO_DEPT.match(name)
        if not m:
            return None
        prefix, doc_type = m.group(1), m.group(2)
        num, ver = m.group(3), m.group(4)
        family = f"{prefix}-{doc_type}-{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            prefix=prefix,
            parse_method="kd_no_dept_pattern",
        )

    def _try_kd_dept_no_ver(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_KD_DEPT_NO_VER.match(name)
        if not m:
            return None
        prefix, doc_type = m.group(1), m.group(2)
        dept, num = m.group(3), m.group(4)
        family = f"{prefix}-{doc_type}-{dept}-{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            doc_type=doc_type, department=dept,
            prefix=prefix,
            parse_method="kd_dept_no_ver_pattern",
        )

    def _try_std_dept(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_STD_DEPT.match(name)
        if not m:
            return None
        doc_type, dept, num, ver = m.group(1), m.group(2), m.group(3), m.group(4)
        family = f"{doc_type}-{dept}.{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            department=dept,
            parse_method="std_dept_pattern",
        )

    def _try_std_no_dept(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_STD_NO_DEPT.match(name)
        if not m:
            return None
        doc_type, num, ver = m.group(1), m.group(2), m.group(3)
        family = f"{doc_type}-{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            parse_method="std_no_dept_pattern",
        )

    def _try_merged_dept_num(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_MERGED_DEPT_NUM.match(name)
        if not m:
            return None
        kd_prefix = m.group(1)
        doc_type = m.group(2)
        dept_letters, num, ver = m.group(3), m.group(4), m.group(5)
        prefix = "КД" if kd_prefix else None
        if prefix:
            family = f"{prefix}-{doc_type}-{dept_letters}{num}"
        else:
            family = f"{doc_type}-{dept_letters}{num}"
        return DocumentInfo(
            raw_name=name, family_code=family,
            version=int(ver), doc_type=doc_type,
            department=dept_letters, prefix=prefix,
            parse_method="merged_dept_num_pattern",
        )

    def _try_special_no_ver(self, name: str) -> Optional[DocumentInfo]:
        m = self._RE_SPECIAL_NO_VER.match(name)
        if not m:
            return None
        code = m.group(1)
        return DocumentInfo(
            raw_name=name, family_code=code,
            parse_method="special_no_ver",
        )

    def _try_human_readable(self, name: str) -> Optional[DocumentInfo]:
        if re.match(r'^[А-Яа-яA-Za-z][А-Яа-яA-Za-z_\s]+$', name):
            return DocumentInfo(
                raw_name=name, family_code=name,
                parse_method="human_readable",
            )
        return None


class DocumentRegistry:
    def __init__(self) -> None:
        self.parser = DocumentCodeParser()
        self.families: dict[str, DocumentFamily] = {}
        self._all_records: list[DocumentRecord] = []
        self._unparsed: list[str] = []

    def scan_output(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        self._scan_top_level_dirs(output_dir)
        self._scan_ocr_full_run(output_dir / "ocr_full_run")

    def _scan_top_level_dirs(self, output_dir: Path) -> None:
        for item in sorted(output_dir.iterdir()):
            if item.name in SKIP_NAMES or item.name == "ocr_full_run":
                continue
            if item.is_dir():
                info = self.parser.parse(item.name)
                if info is None:
                    self._unparsed.append(str(item))
                    continue
                formats_found = self._detect_formats(item)
                if not formats_found:
                    formats_found = ["dir"]
                for fmt in formats_found:
                    rec = DocumentRecord(info=info, format=fmt, source_path=str(item))
                    self._all_records.append(rec)

    def _scan_ocr_full_run(self, ocr_dir: Path) -> None:
        if not ocr_dir.exists():
            return
        for item in sorted(ocr_dir.iterdir()):
            if item.name in SKIP_NAMES or not item.is_file():
                continue
            if item.suffix == ".log":
                continue
            info = self.parser.parse(item.name)
            if info is None:
                self._unparsed.append(str(item))
                continue
            fmt = item.suffix.lstrip(".") if item.suffix else "unknown"
            rec = DocumentRecord(info=info, format=fmt, source_path=str(item))
            self._all_records.append(rec)

    def _detect_formats(self, directory: Path) -> list[str]:
        formats = set()
        target_exts = {".pdf", ".docx", ".bpmn", ".md", ".xlsx"}
        for f in directory.iterdir():
            if f.is_file() and f.suffix in target_exts:
                if "_OCR" not in f.stem:
                    formats.add(f.suffix.lstrip("."))
        return sorted(formats)

    def build_families(self) -> None:
        self.families.clear()
        for rec in self._all_records:
            fc = rec.info.family_code
            if fc not in self.families:
                self.families[fc] = DocumentFamily(family_code=fc)
            self.families[fc].add_document(rec.info, rec.format, rec.source_path)
        for fam in self.families.values():
            fam.resolve_authority()

    def detect_conflicts(self) -> list[dict]:
        conflicts = []

        for fc, fam in sorted(self.families.items()):
            canonical_docs = [d for d in fam.documents if d.authority == "canonical"]
            if len(canonical_docs) > 1:
                conflicts.append({
                    "type": "multiple_canonical",
                    "family": fc,
                    "count": len(canonical_docs),
                    "sources": [d.source_path for d in canonical_docs],
                })

            sources_by_type: dict[str, list[DocumentRecord]] = {}
            for doc in fam.documents:
                if "/ocr_full_run/" in doc.source_path:
                    sources_by_type.setdefault("ocr", []).append(doc)
                else:
                    sources_by_type.setdefault("processed", []).append(doc)

            if "ocr" in sources_by_type and "processed" in sources_by_type:
                ocr_paths = sorted(set(d.source_path for d in sources_by_type["ocr"]))
                proc_paths = sorted(set(d.source_path for d in sources_by_type["processed"]))
                conflicts.append({
                    "type": "duplicate_ocr_and_processed",
                    "family": fc,
                    "ocr_count": len(ocr_paths),
                    "processed_count": len(proc_paths),
                    "ocr_sources": ocr_paths,
                    "processed_sources": proc_paths,
                })

            versions_seen: dict[int, list[DocumentRecord]] = {}
            for doc in fam.documents:
                if doc.info.version is not None:
                    versions_seen.setdefault(doc.info.version, []).append(doc)
            for ver, docs in versions_seen.items():
                unique_sources = set(d.source_path for d in docs)
                if len(unique_sources) > 1:
                    conflicts.append({
                        "type": "same_version_multiple_sources",
                        "family": fc,
                        "version": ver,
                        "sources": sorted(unique_sources),
                    })

        return conflicts

    def summary(self) -> dict:
        type_counts: dict[str, int] = {}
        version_counts: dict[str, int] = {}
        parse_method_counts: dict[str, int] = {}
        total_docs = 0

        for fam in self.families.values():
            for doc in fam.documents:
                total_docs += 1
                dt = doc.info.doc_type or "unknown"
                type_counts[dt] = type_counts.get(dt, 0) + 1
                pm = doc.info.parse_method
                parse_method_counts[pm] = parse_method_counts.get(pm, 0) + 1

        for fam in self.families.values():
            versions = set()
            for doc in fam.documents:
                if doc.info.version is not None:
                    versions.add(doc.info.version)
            version_counts[fam.family_code] = len(versions)

        conflicts = self.detect_conflicts()
        authority_counts: dict[str, int] = {}
        for fam in self.families.values():
            for doc in fam.documents:
                authority_counts[doc.authority] = authority_counts.get(doc.authority, 0) + 1

        return {
            "total_families": len(self.families),
            "total_documents": total_docs,
            "doc_type_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            "authority_counts": authority_counts,
            "parse_method_counts": dict(sorted(parse_method_counts.items(), key=lambda x: -x[1])),
            "families_with_multiple_versions": sum(1 for v in version_counts.values() if v > 1),
            "total_conflicts": len(conflicts),
            "unparsed_count": len(self._unparsed),
            "unparsed_files": self._unparsed,
        }

    def save(self, path: str) -> None:
        data = {
            "summary": self.summary(),
            "families": {},
        }
        for fc, fam in sorted(self.families.items()):
            data["families"][fc] = {
                "family_code": fam.family_code,
                "documents": [
                    {
                        "raw_name": doc.info.raw_name,
                        "family_code": doc.info.family_code,
                        "version": doc.info.version,
                        "doc_type": doc.info.doc_type,
                        "department": doc.info.department,
                        "prefix": doc.info.prefix,
                        "parse_method": doc.info.parse_method,
                        "format": doc.format,
                        "source_path": doc.source_path,
                        "authority": doc.authority,
                    }
                    for doc in fam.documents
                ],
            }
        data["conflicts"] = self.detect_conflicts()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.families.clear()
        self._all_records.clear()
        self._unparsed = data.get("summary", {}).get("unparsed_files", [])

        for fc, fam_data in data.get("families", {}).items():
            fam = DocumentFamily(family_code=fc)
            for doc_data in fam_data.get("documents", []):
                info = DocumentInfo(
                    raw_name=doc_data["raw_name"],
                    family_code=doc_data["family_code"],
                    version=doc_data.get("version"),
                    doc_type=doc_data.get("doc_type"),
                    department=doc_data.get("department"),
                    prefix=doc_data.get("prefix"),
                    parse_method=doc_data.get("parse_method", "loaded"),
                )
                rec = DocumentRecord(
                    info=info,
                    format=doc_data["format"],
                    source_path=doc_data["source_path"],
                    authority=doc_data.get("authority", "canonical"),
                )
                fam.documents.append(rec)
                self._all_records.append(rec)
            self.families[fc] = fam


def main() -> None:
    output_dir = Path(__file__).resolve().parent.parent / "output"
    print(f"Сканирование: {output_dir}")
    print("=" * 70)

    registry = DocumentRegistry()
    registry.scan_output(output_dir)
    registry.build_families()

    stats = registry.summary()

    print(f"\n{'='*70}")
    print("СТАТИСТИКА РЕЕСТРА ДОКУМЕНТОВ")
    print(f"{'='*70}")
    print(f"Всего семейств:        {stats['total_families']}")
    print(f"Всего документов:      {stats['total_documents']}")
    print(f"Нераспознанных:        {stats['unparsed_count']}")
    print(f"Семейств с >1 версией: {stats['families_with_multiple_versions']}")
    print(f"Конфликтов:            {stats['total_conflicts']}")

    print(f"\n--- Типы документов ---")
    for dt, cnt in stats["doc_type_counts"].items():
        label = DOC_TYPE_NAMES.get(dt, dt)
        print(f"  {dt:6s} ({label}): {cnt}")

    print(f"\n--- Authority ---")
    for auth, cnt in stats["authority_counts"].items():
        print(f"  {auth:12s}: {cnt}")

    print(f"\n--- Методы парсинга ---")
    for pm, cnt in stats["parse_method_counts"].items():
        print(f"  {pm:30s}: {cnt}")

    conflicts = registry.detect_conflicts()
    if conflicts:
        print(f"\n{'='*70}")
        print(f"КОНФЛИКТЫ ({len(conflicts)})")
        print(f"{'='*70}")
        for i, c in enumerate(conflicts, 1):
            print(f"\n  [{i}] Тип: {c['type']}")
            print(f"      Семейство: {c.get('family', 'N/A')}")
            if c["type"] == "multiple_canonical":
                print(f"      Canonical документов: {c['count']}")
                for s in c["sources"]:
                    print(f"        - {s}")
            elif c["type"] == "duplicate_ocr_and_processed":
                print(f"      OCR: {c['ocr_count']}, Обработанных: {c['processed_count']}")
                for s in c["ocr_sources"]:
                    print(f"        OCR: {s}")
                for s in c["processed_sources"]:
                    print(f"        Processed: {s}")
            elif c["type"] == "same_version_multiple_sources":
                print(f"      Версия: {c['version']}")
                for s in c["sources"]:
                    print(f"        - {s}")
    else:
        print("\nКонфликтов не обнаружено.")

    if stats["unparsed_files"]:
        print(f"\n{'='*70}")
        print(f"НЕРАСПОЗНАННЫЕ ФАЙЛЫ ({stats['unparsed_count']})")
        print(f"{'='*70}")
        for f in stats["unparsed_files"]:
            print(f"  - {f}")

    print(f"\n--- Примеры семейств (первые 10) ---")
    for i, (fc, fam) in enumerate(sorted(registry.families.items())):
        if i >= 10:
            print("  ...")
            break
        versions = sorted(set(d.info.version for d in fam.documents if d.info.version is not None))
        auth_list = [d.authority for d in fam.documents]
        print(f"  {fc}: {len(fam.documents)} док., версии={versions}, authority={auth_list}")

    registry_path = Path(__file__).resolve().parent / "document_registry.json"
    registry.save(str(registry_path))
    print(f"\nРеестр сохранён: {registry_path}")

    ocr_files = list((output_dir / "ocr_full_run").glob("*_OCR.md"))
    parsed_ocr = 0
    failed_ocr = []
    for f in ocr_files:
        info = registry.parser.parse(f.name)
        if info and info.parse_method != "fallback":
            parsed_ocr += 1
        else:
            failed_ocr.append(f.name)

    total_ocr = len(ocr_files)
    pct = (parsed_ocr / total_ocr * 100) if total_ocr > 0 else 0
    print(f"\n{'='*70}")
    print(f"КАЧЕСТВО ПАРСИНГА OCR ({parsed_ocr}/{total_ocr} = {pct:.1f}%)")
    print(f"{'='*70}")
    if failed_ocr:
        print("Не удалось распарсить:")
        for name in failed_ocr:
            print(f"  - {name}")
    else:
        print("Все OCR файлы успешно распознаны!")


if __name__ == "__main__":
    main()
