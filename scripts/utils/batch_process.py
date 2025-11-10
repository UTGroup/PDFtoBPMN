#!/usr/bin/env python3
"""
Batch Process - CLI утилита для обработки множественных документов

Поддерживает:
- Обработку отдельных файлов (PDF, DOCX, XLSX)
- Batch обработку папки с документами
- Объединение нескольких документов в единый процесс

Применение SOLID:
- Single Responsibility: Только CLI интерфейс
- Dependency Inversion: Зависимость от DocumentToContextPipeline и ProcessBuilder

Автор: PDFtoBPMN Project
Дата: 10.11.2025
"""

import sys
import argparse
from pathlib import Path
from typing import List

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_to_context.document_pipeline import DocumentToContextPipeline
from pdf_to_context.process_builder import ProcessBuilder


def process_single_document(file_path: str, output_dir: str = None, enable_ocr: bool = False):
    """
    Обработать один документ
    
    Args:
        file_path: Путь к документу (PDF/DOCX/XLSX)
        output_dir: Папка для результата (по умолчанию: output/)
        enable_ocr: Включить OCR для PDF
    """
    print(f"\n{'='*60}")
    print(f"ОБРАБОТКА ДОКУМЕНТА")
    print(f"{'='*60}")
    
    # Определяем выходную папку
    file_name = Path(file_path).stem
    # Очистка имени
    if '(' in file_name:
        file_name = file_name[:file_name.index('(')].strip()
    file_name = file_name.replace(' ', '_')
    while '__' in file_name:
        file_name = file_name.replace('__', '_')
    file_name = file_name.strip('_')
    
    if output_dir is None:
        output_dir = f"output/{file_name}"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    output_file = output_path / f"{file_name}_OCR.md"
    
    # Создаем пайплайн
    pipeline = DocumentToContextPipeline(
        enable_pdf_ocr=enable_ocr,
        extract_images=True,
        extract_tables=True
    )
    
    # Показываем поддерживаемые форматы
    print(f"\n📋 Поддерживаемые форматы: {', '.join(pipeline.get_supported_formats())}")
    
    # Обработка
    try:
        markdown = pipeline.process(file_path, output_path=str(output_file))
        
        # Статистика
        stats = pipeline.get_stats()
        print(f"\n📊 Статистика:")
        print(f"   - Формат: {stats['format']}")
        print(f"   - Страниц/листов: {stats['pages_processed']}")
        print(f"   - Текстовых блоков: {stats['text_blocks']}")
        print(f"   - Таблиц: {stats['table_blocks']}")
        print(f"   - Изображений: {stats['image_blocks']}")
        print(f"   - Размер результата: {len(markdown)} символов")
        
        print(f"\n✅ Успешно обработан!")
        print(f"📂 Результат: {output_file}")
        
        return str(output_file)
    
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_batch(input_dir: str, output_dir: str = "output", enable_ocr: bool = False):
    """
    Обработать все документы в папке
    
    Args:
        input_dir: Папка с документами
        output_dir: Папка для результатов
        enable_ocr: Включить OCR для PDF
    """
    print(f"\n{'='*60}")
    print(f"BATCH ОБРАБОТКА")
    print(f"{'='*60}")
    
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"❌ Папка не найдена: {input_dir}")
        return []
    
    # Ищем все поддерживаемые файлы
    supported_extensions = ['.pdf', '.docx', '.xlsx', '.PDF', '.DOCX', '.XLSX']
    files = []
    for ext in supported_extensions:
        files.extend(list(input_path.glob(f"*{ext}")))
    
    print(f"\n📁 Найдено файлов: {len(files)}")
    
    processed_files = []
    
    for idx, file_path in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] {file_path.name}")
        
        result = process_single_document(
            str(file_path),
            output_dir=None,  # Автоматически определится
            enable_ocr=enable_ocr
        )
        
        if result:
            processed_files.append(result)
    
    print(f"\n{'='*60}")
    print(f"✅ Обработано: {len(processed_files)} из {len(files)}")
    print(f"{'='*60}")
    
    return processed_files


def build_multi_document_process(ocr_files: List[str], process_name: str, output_dir: str = None):
    """
    Объединить несколько документов в единый процесс
    
    Args:
        ocr_files: Список путей к _OCR.md файлам
        process_name: Название итогового процесса
        output_dir: Папка для результата
    """
    print(f"\n{'='*60}")
    print(f"ОБЪЕДИНЕНИЕ ДОКУМЕНТОВ В ПРОЦЕСС")
    print(f"{'='*60}")
    
    if output_dir is None:
        output_dir = f"output/{process_name}"
    
    # Создаем построитель
    builder = ProcessBuilder()
    
    # Строим процесс
    try:
        result = builder.build_process(
            ocr_files=ocr_files,
            process_name=process_name,
            output_dir=output_dir
        )
        
        print(f"\n{'='*60}")
        print(f"✅ ПРОЦЕСС СОЗДАН!")
        print(f"{'='*60}")
        print(f"\n📂 Созданные файлы:")
        for key, path in result.items():
            print(f"   - {Path(path).name}")
        
        return result
    
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Batch обработка документов (PDF/DOCX/XLSX) для построения BPMN процессов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

1. Обработать один документ:
   python batch_process.py single input/document.pdf

2. Обработать папку с документами:
   python batch_process.py batch input/

3. Обработать с OCR (для PDF):
   python batch_process.py single input/document.pdf --ocr

4. Объединить документы в процесс:
   python batch_process.py merge \\
       output/Doc1/Doc1_OCR.md \\
       output/Doc2/Doc2_OCR.md \\
       --process-name "Единый_процесс"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Команда для выполнения')
    
    # Команда: single (обработка одного файла)
    single_parser = subparsers.add_parser('single', help='Обработать один документ')
    single_parser.add_argument('file', help='Путь к документу')
    single_parser.add_argument('--output', '-o', help='Папка для результата')
    single_parser.add_argument('--ocr', action='store_true', help='Включить OCR для PDF')
    
    # Команда: batch (обработка папки)
    batch_parser = subparsers.add_parser('batch', help='Обработать все документы в папке')
    batch_parser.add_argument('input_dir', help='Папка с документами')
    batch_parser.add_argument('--output', '-o', default='output', help='Папка для результатов')
    batch_parser.add_argument('--ocr', action='store_true', help='Включить OCR для PDF')
    
    # Команда: merge (объединение документов)
    merge_parser = subparsers.add_parser('merge', help='Объединить документы в процесс')
    merge_parser.add_argument('ocr_files', nargs='+', help='Пути к _OCR.md файлам')
    merge_parser.add_argument('--process-name', '-n', required=True, help='Название процесса')
    merge_parser.add_argument('--output', '-o', help='Папка для результата')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Выполнение команд
    if args.command == 'single':
        process_single_document(args.file, args.output, args.ocr)
    
    elif args.command == 'batch':
        process_batch(args.input_dir, args.output, args.ocr)
    
    elif args.command == 'merge':
        build_multi_document_process(args.ocr_files, args.process_name, args.output)


if __name__ == "__main__":
    main()

