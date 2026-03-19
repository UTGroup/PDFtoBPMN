#!/usr/bin/env python3
"""POC: Описание графики из PDF через Qwen2-VL-2B-Instruct.

TASK-006: Standalone POC — извлечение страниц с графикой из PDF,
описание через VLM, замер производительности.
"""

import gc
import time
from pathlib import Path

import fitz  # PyMuPDF
import torch
from PIL import Image

BASE_DIR = Path("/home/budnik_an/Obligations")
PDF_DIR = BASE_DIR / "input2" / "BND" / "pdf"

TEST_PDFS = [
    PDF_DIR / "КД-РГ-039-05 ^98922A5C1D13C8AF45258B0400287F5F"
    / "КД-РГ-039-05 (эталон №1 для печати).pdf",
    PDF_DIR / "ДП-М1.020-06 ^692386276D6DDE30452584F50038090F"
    / "ДП-М1.020-06 (Эталон №15 для печати).pdf",
    PDF_DIR / "РГ-179-02 ^B88F3504B6B7C3D3452582C0003229D5"
    / "РГ-179-02 (Эталон для печати).pdf",
]

PROMPT_GENERAL = (
    "Опиши эту схему/диаграмму на русском языке. "
    "Если это блок-схема — опиши последовательность шагов, условия и переходы. "
    "Извлеки весь текст из прямоугольников и блоков."
)

PROMPT_BPMN = (
    "Это BPMN диаграмма. Опиши все элементы: задачи (tasks), "
    "шлюзы (gateways), события (events), потоки (flows) и дорожки (swimlanes)."
)

MAX_GRAPHICS_PAGES = 5
RENDER_DPI = 300
MIN_DRAWINGS_THRESHOLD = 10
MAX_TEXT_RATIO = 0.3  # если текст занимает < 30% площади — вероятно графика


def get_vram_usage_mb() -> float:
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0.0


def detect_graphics_pages(pdf_path: Path, max_pages: int = MAX_GRAPHICS_PAGES) -> list[dict]:
    """Определяет страницы PDF, содержащие графику."""
    doc = fitz.open(str(pdf_path))
    graphics_pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height

        drawings = page.get_drawings()
        num_drawings = len(drawings)

        images = page.get_images(full=True)
        num_images = len(images)

        text_blocks = page.get_text("blocks")
        text_area = sum(
            (b[2] - b[0]) * (b[3] - b[1])
            for b in text_blocks
            if b[6] == 0  # тип 0 = текст
        )
        text_ratio = text_area / page_area if page_area > 0 else 1.0

        is_graphics = False
        reason = []

        if num_drawings >= MIN_DRAWINGS_THRESHOLD:
            is_graphics = True
            reason.append(f"drawings={num_drawings}")

        if num_images > 0:
            is_graphics = True
            reason.append(f"images={num_images}")

        if text_ratio < MAX_TEXT_RATIO and num_drawings > 3:
            is_graphics = True
            reason.append(f"low_text={text_ratio:.2f}")

        if is_graphics:
            graphics_pages.append({
                "page_num": page_num,
                "num_drawings": num_drawings,
                "num_images": num_images,
                "text_ratio": text_ratio,
                "reason": ", ".join(reason),
            })

        if len(graphics_pages) >= max_pages:
            break

    doc.close()
    return graphics_pages


def render_page(pdf_path: Path, page_num: int, dpi: int = RENDER_DPI) -> Image.Image:
    """Рендерит страницу PDF в PIL Image."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def load_model():
    """Загружает Qwen2-VL-2B-Instruct."""
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

    model_name = "Qwen/Qwen2-VL-2B-Instruct"
    print(f"  Загрузка модели {model_name}...")
    t0 = time.time()

    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(model_name)

    load_time = time.time() - t0
    vram = get_vram_usage_mb()
    print(f"  Модель загружена за {load_time:.1f}с, VRAM: {vram:.0f} MB")
    return model, processor, load_time


def describe_image(model, processor, image: Image.Image, prompt: str) -> tuple[str, float]:
    """Описывает изображение через VLM. Возвращает (текст, время_сек)."""
    from qwen_vl_utils import process_vision_info

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cuda")

    t0 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=1024)
    inference_time = time.time() - t0

    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return output[0], inference_time


def unload_model(model, processor):
    """Выгружает модель и очищает VRAM."""
    del model
    del processor
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    vram_after = get_vram_usage_mb()
    print(f"  Модель выгружена, VRAM после очистки: {vram_after:.0f} MB")


def main():
    print("=" * 70)
    print("POC: Описание графики из PDF через Qwen2-VL-2B-Instruct")
    print("=" * 70)

    vram_start = get_vram_usage_mb()
    print(f"\nVRAM в начале: {vram_start:.0f} MB")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # --- Шаг 1: поиск PDF и детекция графики ---
    print("\n" + "=" * 70)
    print("Шаг 1: Поиск страниц с графикой")
    print("=" * 70)

    all_tasks = []  # (pdf_path, page_info, rendered_image)

    for pdf_path in TEST_PDFS:
        if not pdf_path.exists():
            print(f"\n  SKIP: {pdf_path.name} — файл не найден")
            continue

        print(f"\n  PDF: {pdf_path.name}")
        graphics = detect_graphics_pages(pdf_path)
        print(f"  Найдено страниц с графикой: {len(graphics)}")

        for pg in graphics:
            print(
                f"    стр. {pg['page_num'] + 1}: "
                f"drawings={pg['num_drawings']}, images={pg['num_images']}, "
                f"text_ratio={pg['text_ratio']:.2f} [{pg['reason']}]"
            )
            img = render_page(pdf_path, pg["page_num"])
            all_tasks.append((pdf_path, pg, img))

    if not all_tasks:
        print("\nНет страниц с графикой — завершение.")
        return

    print(f"\nВсего страниц для описания: {len(all_tasks)}")

    # --- Шаг 2: загрузка модели ---
    print("\n" + "=" * 70)
    print("Шаг 2: Загрузка Qwen2-VL-2B-Instruct")
    print("=" * 70)

    model, processor, model_load_time = load_model()

    # --- Шаг 3: описание графики ---
    print("\n" + "=" * 70)
    print("Шаг 3: Описание графики через VLM")
    print("=" * 70)

    results = []
    total_inference_time = 0.0

    for i, (pdf_path, pg, img) in enumerate(all_tasks, 1):
        page_label = f"{pdf_path.stem} стр.{pg['page_num'] + 1}"
        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(all_tasks)}] {page_label}")
        print(f"{'─' * 60}")

        vram_before = get_vram_usage_mb()

        # Общий промпт
        print(f"\n  Промпт: ОБЩИЙ")
        desc_general, t_general = describe_image(model, processor, img, PROMPT_GENERAL)
        print(f"  Время: {t_general:.1f}с")
        print(f"  Описание:\n{_indent(desc_general)}")

        # BPMN промпт
        print(f"\n  Промпт: BPMN")
        desc_bpmn, t_bpmn = describe_image(model, processor, img, PROMPT_BPMN)
        print(f"  Время: {t_bpmn:.1f}с")
        print(f"  Описание:\n{_indent(desc_bpmn)}")

        page_time = t_general + t_bpmn
        total_inference_time += page_time
        vram_after = get_vram_usage_mb()

        results.append({
            "pdf": pdf_path.stem,
            "page": pg["page_num"] + 1,
            "reason": pg["reason"],
            "time_general": t_general,
            "time_bpmn": t_bpmn,
            "time_total": page_time,
            "len_general": len(desc_general),
            "len_bpmn": len(desc_bpmn),
            "vram_mb": vram_after,
        })

        print(f"\n  Итого страница: {page_time:.1f}с, VRAM: {vram_after:.0f} MB")

    # --- Шаг 4: выгрузка модели ---
    print("\n" + "=" * 70)
    print("Шаг 4: Выгрузка модели и очистка VRAM")
    print("=" * 70)

    unload_model(model, processor)

    # --- Сводка ---
    print("\n" + "=" * 70)
    print("СВОДКА")
    print("=" * 70)

    print(f"\n  Тестовых PDF: {len(TEST_PDFS)}")
    print(f"  Страниц с графикой: {len(results)}")
    print(f"  Время загрузки модели: {model_load_time:.1f}с")
    print(f"  Общее время inference: {total_inference_time:.1f}с")

    if results:
        avg_time = total_inference_time / len(results) / 2  # /2 т.к. 2 промпта
        print(f"  Среднее время на промпт: {avg_time:.1f}с")
        max_vram = max(r["vram_mb"] for r in results)
        print(f"  Пиковый VRAM: {max_vram:.0f} MB")

    vram_end = get_vram_usage_mb()
    print(f"  VRAM в конце: {vram_end:.0f} MB")

    print(f"\n  Результаты по страницам:")
    for r in results:
        status = "OK" if r["time_general"] < 30 and r["time_bpmn"] < 30 else "SLOW"
        print(
            f"    [{status}] {r['pdf']} стр.{r['page']}: "
            f"general={r['time_general']:.1f}с ({r['len_general']} chars), "
            f"bpmn={r['time_bpmn']:.1f}с ({r['len_bpmn']} chars)"
        )

    print("\n" + "=" * 70)
    print("POC завершён")
    print("=" * 70)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.strip().split("\n"))


if __name__ == "__main__":
    main()
