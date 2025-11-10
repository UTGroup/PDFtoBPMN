"""
Base Extractor - базовый абстрактный класс для всех экстракторов

Применение SOLID:
- Interface Segregation: Общий интерфейс для всех форматов
- Open/Closed: Легко добавить новый формат
- Liskov Substitution: Все экстракторы взаимозаменяемы

Автор: PDFtoBPMN Project
Дата: 10.11.2025
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
from pathlib import Path


class BaseExtractor(ABC):
    """
    Базовый класс для всех экстракторов документов
    
    Ответственность:
    - Определить общий интерфейс для извлечения данных
    - Обеспечить унифицированный формат выходных данных
    
    Не отвечает за:
    - Построение IR (это делает IRBuilder)
    - Форматирование в Markdown (это делает MarkdownFormatter)
    """
    
    def __init__(self, 
                 extract_images: bool = True,
                 extract_tables: bool = True):
        """
        Инициализация базового экстрактора
        
        Args:
            extract_images: Извлекать изображения
            extract_tables: Извлекать таблицы
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self._stats = {
            "pages_processed": 0,
            "text_blocks": 0,
            "image_blocks": 0,
            "table_blocks": 0
        }
    
    @abstractmethod
    def extract_document(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Извлечь весь контент из документа
        
        Args:
            file_path: Путь к файлу документа
        
        Returns:
            Список страниц, каждая страница - Dict с ключами:
            {
                "page_num": int,
                "text_blocks": List[TextBlock],
                "image_blocks": List[ImageBlock],
                "table_blocks": List[TableBlock],
                "drawing_blocks": List[DrawingBlock]  # опционально
            }
        
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если формат файла не поддерживается
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Получить список поддерживаемых расширений
        
        Returns:
            Список расширений (например: ['.pdf', '.PDF'])
        """
        pass
    
    def validate_file(self, file_path: str) -> bool:
        """
        Проверить что файл существует и имеет поддерживаемое расширение
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            True если файл валиден
        
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если расширение не поддерживается
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        if path.suffix.lower() not in [ext.lower() for ext in self.get_supported_extensions()]:
            raise ValueError(
                f"Неподдерживаемое расширение: {path.suffix}. "
                f"Поддерживаются: {', '.join(self.get_supported_extensions())}"
            )
        
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """
        Получить статистику обработки
        
        Returns:
            Словарь со статистикой
        """
        return self._stats.copy()
    
    def reset_stats(self):
        """Сбросить статистику"""
        self._stats = {
            "pages_processed": 0,
            "text_blocks": 0,
            "image_blocks": 0,
            "table_blocks": 0
        }

