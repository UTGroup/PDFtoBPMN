"""
Document to Context Pipeline - унифицированный обработчик документов

НОВАЯ АРХИТЕКТУРА: Поддержка множественных форматов (PDF, DOCX, XLSX)

Управляет всем процессом обработки документа любого формата:
1. Определение типа документа (по расширению)
2. Делегирование соответствующему экстрактору
3. Построение IR (IRBuilder)
4. Анализ структуры (StructureAnalyzer)
5. Форматирование в Markdown (MarkdownFormatter)

Принципы SOLID:
- Single Responsibility: Только оркестрация компонентов
- Open/Closed: Легко добавить новый формат
- Dependency Inversion: Зависимость от BaseExtractor абстракции
- KISS: Унифицированный путь обработки

Автор: PDFtoBPMN Project
Дата: 10.11.2025
"""

from typing import Optional, Dict, Type
from pathlib import Path

from .extractors.base_extractor import BaseExtractor
from .extractors.pdf_extractor import PDFExtractor
from .extractors.docx_extractor import DOCXExtractor
from .extractors.xlsx_extractor import XLSXExtractor
from .ir.builder import IRBuilder
from .ir.structure_analyzer import StructureAnalyzer
from .output.markdown_formatter import MarkdownFormatter
from .ir.models import IR


class DocumentToContextPipeline:
    """
    Унифицированный пайплайн для обработки документов любого формата
    
    Поддерживаемые форматы:
    - PDF (через PDFExtractor)
    - DOCX (через DOCXExtractor)
    - XLSX (через XLSXExtractor)
    
    Использование:
    ```python
    pipeline = DocumentToContextPipeline()
    
    # Автоматически определит формат и обработает
    markdown = pipeline.process("document.pdf", output_path="output.md")
    markdown = pipeline.process("document.docx", output_path="output.md")
    markdown = pipeline.process("data.xlsx", output_path="output.md")
    ```
    """
    
    def __init__(self,
                 # PDF-специфичные параметры
                 enable_pdf_ocr: bool = False,
                 ocr_base_url: str = "http://localhost:8000",
                 # Общие параметры
                 extract_images: bool = True,
                 extract_tables: bool = True,
                 # Markdown параметры
                 include_frontmatter: bool = True,
                 include_toc: bool = True):
        """
        Инициализация унифицированного пайплайна
        
        Args:
            enable_pdf_ocr: Включить OCR для PDF (требует GPU + DeepSeek-OCR)
            ocr_base_url: URL OCR сервиса
            extract_images: Извлекать изображения
            extract_tables: Извлекать таблицы
            include_frontmatter: Включать YAML frontmatter в Markdown
            include_toc: Включать оглавление в Markdown
        """
        self.enable_pdf_ocr = enable_pdf_ocr
        self.ocr_base_url = ocr_base_url
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.include_frontmatter = include_frontmatter
        self.include_toc = include_toc
        
        # Регистрация доступных экстракторов
        self._extractors_registry: Dict[str, Type[BaseExtractor]] = {}
        self._register_extractors()
        
        # Компоненты обработки (общие для всех форматов)
        self.ir_builder = IRBuilder()
        self.structure_analyzer = StructureAnalyzer()
        self.markdown_formatter = MarkdownFormatter(
            include_frontmatter=include_frontmatter,
            include_toc=include_toc
        )
        
        # Статистика
        self._stats = {
            "format": None,
            "pages_processed": 0,
            "text_blocks": 0,
            "image_blocks": 0,
            "table_blocks": 0
        }
    
    def _register_extractors(self):
        """Регистрация доступных экстракторов"""
        # PDF экстрактор
        for ext in PDFExtractor(enable_ocr=False).get_supported_extensions():
            self._extractors_registry[ext.lower()] = PDFExtractor
        
        # DOCX экстрактор (если python-docx установлен)
        try:
            docx_extractor = DOCXExtractor()
            for ext in docx_extractor.get_supported_extensions():
                self._extractors_registry[ext.lower()] = DOCXExtractor
        except ImportError:
            print("⚠️  python-docx не установлен, DOCX файлы не поддерживаются")
        
        # XLSX экстрактор (если openpyxl установлен)
        try:
            xlsx_extractor = XLSXExtractor()
            for ext in xlsx_extractor.get_supported_extensions():
                self._extractors_registry[ext.lower()] = XLSXExtractor
        except ImportError:
            print("⚠️  openpyxl не установлен, XLSX файлы не поддерживаются")
    
    def get_supported_formats(self) -> list:
        """Получить список поддерживаемых форматов"""
        return sorted(set(self._extractors_registry.keys()))
    
    def _get_extractor(self, file_path: str) -> BaseExtractor:
        """
        Получить подходящий экстрактор для файла
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Экземпляр экстрактора
        
        Raises:
            ValueError: Если формат не поддерживается
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in self._extractors_registry:
            supported = ', '.join(self.get_supported_formats())
            raise ValueError(
                f"Неподдерживаемый формат: {file_ext}\n"
                f"Поддерживаются: {supported}"
            )
        
        extractor_class = self._extractors_registry[file_ext]
        
        # Инициализация экстрактора с параметрами
        if extractor_class == PDFExtractor:
            # PDF-специфичная инициализация (с OCR если включен)
            ocr_client = None
            if self.enable_pdf_ocr:
                try:
                    from .ocr_service.factory import OCRServiceFactory
                    ocr_service = OCRServiceFactory.create(
                        prefer_deepseek=True,
                        deepseek_url=self.ocr_base_url
                    )
                    from .extractors.ocr_client import OCRClient
                    ocr_client = OCRClient(ocr_service=ocr_service)
                except Exception as e:
                    print(f"⚠️  OCR недоступен: {e}")
            
            return PDFExtractor(
                extract_images=self.extract_images,
                extract_tables=self.extract_tables,
                enable_ocr=self.enable_pdf_ocr,
                ocr_client=ocr_client
            )
        
        elif extractor_class == DOCXExtractor:
            return DOCXExtractor(
                extract_images=self.extract_images,
                extract_tables=self.extract_tables
            )
        
        elif extractor_class == XLSXExtractor:
            return XLSXExtractor(
                extract_tables=self.extract_tables
            )
        
        else:
            raise ValueError(f"Неизвестный экстрактор: {extractor_class}")
    
    def process(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        Обработать документ любого поддерживаемого формата
        
        Args:
            file_path: Путь к входному файлу (PDF/DOCX/XLSX)
            output_path: Путь для сохранения результата (опционально)
        
        Returns:
            Markdown контент
        
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если формат не поддерживается
        """
        print(f"🔄 Обработка документа: {Path(file_path).name}")
        
        # Определяем формат и получаем экстрактор
        file_ext = Path(file_path).suffix.lower()
        self._stats["format"] = file_ext
        
        extractor = self._get_extractor(file_path)
        print(f"📄 Формат: {file_ext.upper()} → {extractor.__class__.__name__}")
        
        # Шаг 1: Извлечение контента
        print("🔍 Извлечение контента...")
        pages_data = extractor.extract_document(file_path)
        
        # Обновляем статистику
        extractor_stats = extractor.get_stats()
        self._stats.update(extractor_stats)
        
        print(f"   ✓ Обработано: {extractor_stats['pages_processed']} страниц/листов")
        print(f"   ✓ Текстовых блоков: {extractor_stats['text_blocks']}")
        print(f"   ✓ Таблиц: {extractor_stats['table_blocks']}")
        if extractor_stats['image_blocks'] > 0:
            print(f"   ✓ Изображений: {extractor_stats['image_blocks']}")
        
        # Шаг 2: Построение IR
        print("\n🏗️  Построение промежуточного представления...")
        
        # Создаем document_metadata
        from .ir.models import DocumentMetadata
        document_metadata = DocumentMetadata(
            total_pages=extractor_stats['pages_processed'],
            title=Path(file_path).stem,
            source_file=file_path
        )
        
        ir = self.ir_builder.build_ir(pages_data, document_metadata)
        
        # Шаг 3: Анализ структуры
        print("🔬 Анализ структуры документа...")
        ir = self.structure_analyzer.analyze(ir)
        
        # Шаг 4: Форматирование в Markdown
        print("📝 Форматирование в Markdown...")
        markdown = self.markdown_formatter.format(ir)
        
        # Сохранение результата (если указан путь)
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown, encoding='utf-8')
            print(f"\n✅ Результат сохранен: {output_path}")
        
        print(f"✅ Обработка завершена ({len(markdown)} символов)")
        
        return markdown
    
    def get_stats(self) -> Dict[str, any]:
        """Получить статистику обработки"""
        return self._stats.copy()

