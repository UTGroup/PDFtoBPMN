"""
DOCX Extractor - экстрактор для Word документов

Использует python-docx для извлечения:
- Текстовых блоков с сохранением структуры (заголовки, параграфы)
- Таблиц Word
- Изображений (встроенные картинки)
- Форматирования (жирный, курсив, списки)

Применение SOLID:
- Single Responsibility: Только обработка DOCX
- Open/Closed: Расширение BaseExtractor
- Dependency Inversion: Зависимость от абстракции

Автор: PDFtoBPMN Project
Дата: 10.11.2025
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import io

try:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from .base_extractor import BaseExtractor
from ..models.data_models import TextBlock, ImageBlock, TableBlock, BBox


class DOCXExtractor(BaseExtractor):
    """
    Экстрактор для DOCX документов
    
    Ответственность:
    - Извлечение текста с сохранением структуры
    - Парсинг таблиц Word
    - Извлечение изображений
    - Определение форматирования (заголовки, списки, стили)
    """
    
    def __init__(self,
                 extract_images: bool = True,
                 extract_tables: bool = True,
                 preserve_formatting: bool = True,
                 extract_styles: bool = True):
        """
        Инициализация DOCX экстрактора
        
        Args:
            extract_images: Извлекать изображения
            extract_tables: Извлекать таблицы
            preserve_formatting: Сохранять форматирование (жирный, курсив)
            extract_styles: Извлекать стили (заголовки H1-H6)
        
        Raises:
            ImportError: Если python-docx не установлен
        """
        super().__init__(extract_images=extract_images, extract_tables=extract_tables)
        
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx не установлен. Установите: pip install python-docx"
            )
        
        self.preserve_formatting = preserve_formatting
        self.extract_styles = extract_styles
    
    def get_supported_extensions(self) -> List[str]:
        """Поддерживаемые расширения: DOCX"""
        return ['.docx', '.DOCX']
    
    def extract_document(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Извлечь весь контент из DOCX документа
        
        Args:
            file_path: Путь к DOCX файлу
        
        Returns:
            Список "страниц" (в DOCX нет строгих страниц, группируем по разделам)
        """
        # Валидация файла
        self.validate_file(file_path)
        self.reset_stats()
        
        # Открываем документ
        doc = Document(file_path)
        
        # DOCX не имеет строгого понятия "страницы"
        # Создаем одну "виртуальную страницу" со всем контентом
        page_data = {
            "page_num": 0,
            "text_blocks": [],
            "image_blocks": [],
            "table_blocks": [],
            "drawing_blocks": []
        }
        
        # Счетчик позиции для BBox (виртуальные координаты)
        y_position = 0
        line_height = 20  # Виртуальная высота строки
        
        # Обрабатываем элементы документа в порядке появления
        for element in self._iter_block_items(doc):
            if isinstance(element, Paragraph):
                # Обработка параграфа
                text_block = self._extract_paragraph(element, y_position)
                if text_block:
                    page_data["text_blocks"].append(text_block)
                    self._stats["text_blocks"] += 1
                    y_position += line_height
            
            elif isinstance(element, Table) and self.extract_tables:
                # Обработка таблицы
                table_block = self._extract_table(element, y_position)
                if table_block:
                    page_data["table_blocks"].append(table_block)
                    self._stats["table_blocks"] += 1
                    # Таблица занимает больше места
                    y_position += line_height * (len(element.rows) + 1)
        
        # Извлечение изображений (если включено)
        if self.extract_images:
            image_blocks = self._extract_images(doc)
            page_data["image_blocks"].extend(image_blocks)
            self._stats["image_blocks"] += len(image_blocks)
        
        self._stats["pages_processed"] = 1
        
        return [page_data]
    
    def _iter_block_items(self, parent):
        """
        Итератор по элементам документа в порядке появления
        
        Yields:
            Paragraph или Table объекты
        """
        from docx.document import Document as DocumentType
        
        if isinstance(parent, DocumentType):
            parent_elm = parent.element.body
        else:
            parent_elm = parent._element
        
        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)
    
    def _extract_paragraph(self, paragraph: Paragraph, y_position: int) -> Optional[TextBlock]:
        """
        Извлечь текст из параграфа с форматированием
        
        Args:
            paragraph: Объект параграфа python-docx
            y_position: Вертикальная позиция (виртуальная)
        
        Returns:
            TextBlock или None если параграф пустой
        """
        text = paragraph.text.strip()
        if not text:
            return None
        
        # Определяем тип блока по стилю
        style = paragraph.style.name if paragraph.style else "Normal"
        
        # Определяем размер шрифта (для эмуляции font_size)
        font_size = 12.0  # По умолчанию
        if "Heading 1" in style:
            font_size = 24.0
        elif "Heading 2" in style:
            font_size = 20.0
        elif "Heading 3" in style:
            font_size = 16.0
        elif "Heading" in style:
            font_size = 14.0
        
        # Проверка форматирования (жирный)
        is_bold = False
        if paragraph.runs:
            is_bold = any(run.bold for run in paragraph.runs)
        
        # Создаем виртуальный BBox
        bbox = BBox(
            x0=0.0,
            y0=float(y_position),
            x1=600.0,  # Виртуальная ширина страницы
            y1=float(y_position + 20)
        )
        
        return TextBlock(
            text=text,
            bbox=bbox,
            font_size=font_size,
            font_name="Calibri",  # Стандартный шрифт Word
            is_bold=is_bold,
            is_italic=False,  # TODO: добавить проверку курсива
            page_num=0
        )
    
    def _extract_table(self, table: Table, y_position: int) -> Optional[TableBlock]:
        """
        Извлечь таблицу Word
        
        Args:
            table: Объект таблицы python-docx
            y_position: Вертикальная позиция
        
        Returns:
            TableBlock с данными таблицы
        """
        if not table.rows:
            return None
        
        # Извлекаем данные таблицы
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                row_data.append(cell.text.strip())
            table_data.append(row_data)
        
        # Создаем виртуальный BBox для таблицы
        table_height = len(table.rows) * 20
        bbox = BBox(
            x0=0.0,
            y0=float(y_position),
            x1=600.0,
            y1=float(y_position + table_height)
        )
        
        # Генерируем простой HTML для таблицы
        html_rows = []
        for row_data in table_data:
            cells = ''.join([f'<td>{cell}</td>' for cell in row_data])
            html_rows.append(f'<tr>{cells}</tr>')
        html = f'<table>{"".join(html_rows)}</table>'
        
        return TableBlock(
            bbox=bbox,
            html=html,
            rows=len(table.rows),
            cols=len(table.rows[0].cells) if table.rows else 0,
            page_num=0,
            data=table_data
        )
    
    def _extract_images(self, doc: Any) -> List[ImageBlock]:
        """
        Извлечь встроенные изображения из документа
        
        Args:
            doc: Объект документа python-docx
        
        Returns:
            Список ImageBlock с изображениями
        """
        image_blocks = []
        
        # Проходим по всем relationships документа
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    # Получаем изображение
                    image_part = rel.target_part
                    image_data = image_part.blob
                    
                    # Создаем виртуальный BBox
                    bbox = BBox(x0=0.0, y0=0.0, x1=400.0, y1=300.0)
                    
                    image_block = ImageBlock(
                        bbox=bbox,
                        image_data=image_data,
                        page_num=0,
                        format=self._guess_image_format(image_part.content_type)
                    )
                    
                    image_blocks.append(image_block)
                
                except Exception as e:
                    print(f"⚠️  Ошибка извлечения изображения: {e}")
        
        return image_blocks
    
    def _guess_image_format(self, content_type: str) -> str:
        """
        Определить формат изображения по MIME типу
        
        Args:
            content_type: MIME тип (например: image/png)
        
        Returns:
            Расширение файла (png, jpg, etc.)
        """
        mime_to_ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/bmp": "bmp",
            "image/tiff": "tiff"
        }
        
        return mime_to_ext.get(content_type.lower(), "png")

