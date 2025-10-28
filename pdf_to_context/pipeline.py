"""
PDF to Context Pipeline - главный оркестратор

Управляет всем процессом обработки PDF:
1. Парсинг PDF (PDFParser)
2. Анализ страниц (PageAnalyzer)
3. Маршрутизация (ContentRouter)
4. Извлечение контента (NativeExtractor / OCRClient / HybridHandler)
5. Построение IR (IRBuilder)
6. Анализ структуры (StructureAnalyzer)
7. Форматирование в Markdown (MarkdownFormatter)

Принципы SOLID:
- Single Responsibility: Только оркестрация компонентов
- Dependency Inversion: Все компоненты передаются как зависимости
- Open/Closed: Легко заменять компоненты
"""

from typing import Optional
from pathlib import Path

from .core.parser import PDFParser
from .core.analyzer import PageAnalyzer
from .core.router import ContentRouter
from .extractors.native_extractor import NativeExtractor
from .extractors.ocr_client import OCRClient
from .extractors.hybrid_handler import HybridHandler
from .ir.builder import IRBuilder
from .ir.structure_analyzer import StructureAnalyzer
from .output.markdown_formatter import MarkdownFormatter
from .ir.models import IR
from .models.data_models import RouteDecision


class PDFToContextPipeline:
    """
    Главный пайплайн для обработки PDF в контекст
    
    Использование:
    ```python
    pipeline = PDFToContextPipeline(
        ocr_base_url="http://localhost:8000",
        prioritize_accuracy=True
    )
    
    markdown = pipeline.process("document.pdf", output_path="output.md")
    ```
    """
    
    def __init__(self,
                 ocr_base_url: str = "http://localhost:8000",
                 prioritize_accuracy: bool = True,
                 extract_images: bool = True,
                 extract_drawings: bool = True,
                 extract_tables: bool = True,
                 include_frontmatter: bool = True,
                 include_toc: bool = True):
        """
        Инициализация пайплайна
        
        Args:
            ocr_base_url: URL DeepSeek-OCR микросервиса
            prioritize_accuracy: Приоритет точности над скоростью
            extract_images: Извлекать изображения
            extract_drawings: Извлекать векторную графику
            extract_tables: Извлекать таблицы
            include_frontmatter: Включать YAML frontmatter
            include_toc: Включать оглавление
        """
        # Инициализация компонентов
        self.analyzer = PageAnalyzer()
        self.router = ContentRouter(
            analyzer=self.analyzer,
            prioritize_accuracy=prioritize_accuracy
        )
        self.native_extractor = NativeExtractor(
            extract_images=extract_images,
            extract_drawings=extract_drawings,
            extract_tables=extract_tables
        )
        self.ocr_client = OCRClient(base_url=ocr_base_url)
        self.hybrid_handler = HybridHandler(
            native_extractor=self.native_extractor,
            ocr_client=self.ocr_client
        )
        self.ir_builder = IRBuilder()
        self.structure_analyzer = StructureAnalyzer()
        self.markdown_formatter = MarkdownFormatter(
            include_frontmatter=include_frontmatter,
            include_toc=include_toc
        )
        
        self.prioritize_accuracy = prioritize_accuracy
        self._stats = {
            "total_pages": 0,
            "native_pages": 0,
            "ocr_pages": 0,
            "hybrid_pages": 0,
            "errors": []
        }
    
    def process(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """
        Обработать PDF документ
        
        Args:
            pdf_path: Путь к PDF файлу
            output_path: Путь для сохранения Markdown (опционально)
        
        Returns:
            Markdown строка
        """
        print(f"🚀 Начало обработки: {pdf_path}")
        
        # 1. Открытие PDF
        with PDFParser(pdf_path) as parser:
            print(f"📄 Документ: {parser.get_total_pages()} страниц")
            
            # Извлечение метаданных
            document_metadata = parser.extract_metadata()
            self._stats["total_pages"] = document_metadata.total_pages
            
            # 2. Обработка каждой страницы
            extracted_data = []
            
            for page_num in range(parser.get_total_pages()):
                print(f"   Обработка страницы {page_num + 1}/{parser.get_total_pages()}...", end=" ")
                
                page = parser.get_page(page_num)
                
                try:
                    # Анализ страницы
                    metadata = self.analyzer.analyze_page(page)
                    
                    # Маршрутизация
                    route_info = self.router.route_page(page, metadata)
                    decision = route_info.decision
                    
                    print(f"[{decision.value}]", end=" ")
                    
                    # Извлечение контента в зависимости от решения
                    if decision == RouteDecision.NATIVE:
                        page_data = self.native_extractor.extract_page(page, pdf_path)
                        self._stats["native_pages"] += 1
                    
                    elif decision == RouteDecision.OCR:
                        # OCR всей страницы
                        ocr_response = self.ocr_client.ocr_page(
                            page,
                            mode=route_info.ocr_mode
                        )
                        page_data = {
                            "text_blocks": [],
                            "image_blocks": [],
                            "drawing_blocks": [],
                            "table_blocks": [],
                            "ocr_blocks": ocr_response.blocks
                        }
                        self._stats["ocr_pages"] += 1
                    
                    elif decision == RouteDecision.HYBRID:
                        # Гибридная обработка
                        page_data = self.hybrid_handler.process_page(page, pdf_path)
                        self._stats["hybrid_pages"] += 1
                    
                    else:
                        # Fallback: native
                        page_data = self.native_extractor.extract_page(page, pdf_path)
                    
                    extracted_data.append(page_data)
                    print("✓")
                
                except Exception as e:
                    print(f"✗ Ошибка: {e}")
                    self._stats["errors"].append({
                        "page": page_num + 1,
                        "error": str(e)
                    })
                    # Добавляем пустые данные
                    extracted_data.append({
                        "text_blocks": [],
                        "image_blocks": [],
                        "drawing_blocks": [],
                        "table_blocks": [],
                        "ocr_blocks": []
                    })
            
            # 3. Построение IR
            print("🔨 Построение промежуточного представления...")
            ir = self.ir_builder.build_ir(extracted_data, document_metadata)
            
            # 4. Анализ структуры
            print("🔍 Анализ структуры документа...")
            ir = self.structure_analyzer.analyze(ir)
            
            # 5. Форматирование в Markdown
            print("📝 Форматирование в Markdown...")
            markdown = self.markdown_formatter.format(ir)
            
            # 6. Сохранение (если указан путь)
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown)
                
                print(f"💾 Сохранено в: {output_path}")
            
            # 7. Статистика
            self._print_stats(ir)
            
            return markdown
    
    def process_to_ir(self, pdf_path: str) -> IR:
        """
        Обработать PDF и вернуть IR (без Markdown форматирования)
        
        Args:
            pdf_path: Путь к PDF файлу
        
        Returns:
            IR: Промежуточное представление
        """
        with PDFParser(pdf_path) as parser:
            document_metadata = parser.extract_metadata()
            extracted_data = []
            
            for page_num in range(parser.get_total_pages()):
                page = parser.get_page(page_num)
                metadata = self.analyzer.analyze_page(page)
                route_info = self.router.route_page(page, metadata)
                
                if route_info.decision == RouteDecision.NATIVE:
                    page_data = self.native_extractor.extract_page(page, pdf_path)
                elif route_info.decision == RouteDecision.OCR:
                    ocr_response = self.ocr_client.ocr_page(page, mode=route_info.ocr_mode)
                    page_data = {
                        "text_blocks": [],
                        "image_blocks": [],
                        "drawing_blocks": [],
                        "table_blocks": [],
                        "ocr_blocks": ocr_response.blocks
                    }
                else:
                    page_data = self.hybrid_handler.process_page(page, pdf_path)
                
                extracted_data.append(page_data)
            
            ir = self.ir_builder.build_ir(extracted_data, document_metadata)
            ir = self.structure_analyzer.analyze(ir)
            
            return ir
    
    def health_check(self) -> dict:
        """
        Проверка работоспособности пайплайна
        
        Returns:
            Словарь с статусами компонентов
        """
        return {
            "ocr_service": self.ocr_client.health_check(),
            "components": {
                "parser": "ready",
                "analyzer": "ready",
                "router": "ready",
                "native_extractor": "ready",
                "ocr_client": "ready" if self.ocr_client.health_check() else "unavailable",
                "ir_builder": "ready",
                "structure_analyzer": "ready",
                "markdown_formatter": "ready"
            }
        }
    
    def _print_stats(self, ir: IR):
        """Вывод статистики обработки"""
        print("\n📊 Статистика обработки:")
        print(f"   Всего страниц: {self._stats['total_pages']}")
        print(f"   Native: {self._stats['native_pages']}")
        print(f"   OCR: {self._stats['ocr_pages']}")
        print(f"   Hybrid: {self._stats['hybrid_pages']}")
        
        ir_stats = ir.get_statistics()
        print(f"\n   Блоков в IR: {ir_stats['total_blocks']}")
        print(f"   - Native: {ir_stats['blocks_by_source']['native']}")
        print(f"   - OCR: {ir_stats['blocks_by_source']['ocr']}")
        
        if self._stats['errors']:
            print(f"\n   ⚠️  Ошибок: {len(self._stats['errors'])}")
        
        print("\n✅ Обработка завершена!")
    
    def __repr__(self) -> str:
        """Строковое представление"""
        mode = "accuracy" if self.prioritize_accuracy else "balanced"
        return f"PDFToContextPipeline(mode={mode})"

