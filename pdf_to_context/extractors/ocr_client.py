"""
OCR Client - HTTP клиент для DeepSeek-OCR микросервиса

Взаимодействует с vLLM-based DeepSeek-OCR сервисом через HTTP API.
Отправляет изображения страниц/блоков и получает структурированный Markdown.

HTTP Contracts (из архитектурного анализа):
- POST /ocr/page - OCR всей страницы
- POST /ocr/figure - OCR отдельного графического элемента

Принципы SOLID:
- Single Responsibility: Только HTTP взаимодействие с OCR
- Dependency Inversion: Зависимость от абстракций (OCRMode, OCRResponse)
"""

import requests
import base64
from typing import Optional, Dict, Any, List
import io
from PIL import Image
import fitz  # PyMuPDF

from ..models.data_models import (
    OCRMode,
    OCRResponse,
    OCRBlock,
    BBox,
    ContentType
)


class OCRClient:
    """
    HTTP клиент для DeepSeek-OCR микросервиса
    
    Ответственность:
    - HTTP запросы к OCR сервису
    - Конвертация изображений в base64
    - Парсинг ответов OCR
    - Обработка ошибок и retry логика
    
    Не отвечает за:
    - Извлечение контента из PDF (это делает NativeExtractor)
    - Построение IR (это делает IRBuilder)
    - Решение о маршрутизации (это делает ContentRouter)
    """
    
    # Промпты для DeepSeek-OCR (из README)
    PROMPT_LAYOUT_MARKDOWN = (
        "Convert the entire page/image into Markdown format. "
        "Preserve layout structure: headings, paragraphs, lists, tables, figures. "
        "For tables, use Markdown table syntax. For figures, use ![alt](path)."
    )
    
    PROMPT_FIGURE_PARSING = (
        "Extract and describe the figure/diagram/chart in detail. "
        "Include any text labels, legends, and structural information."
    )
    
    def __init__(self, base_url: str = "http://localhost:8000",
                 timeout: int = 60,
                 max_retries: int = 3):
        """
        Инициализация OCR клиента
        
        Args:
            base_url: URL базового адреса OCR микросервиса
            timeout: Таймаут HTTP запросов (секунды)
            max_retries: Максимальное количество попыток при ошибках
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
    
    def ocr_page(self, page: fitz.Page, 
                 mode: OCRMode = OCRMode.BASE,
                 prompt: Optional[str] = None) -> OCRResponse:
        """
        OCR всей страницы PDF
        
        Args:
            page: Объект страницы PyMuPDF
            mode: Режим OCR (Tiny/Small/Base/Large/Gundam)
            prompt: Кастомный промпт (по умолчанию PROMPT_LAYOUT_MARKDOWN)
        
        Returns:
            OCRResponse: Результат OCR с Markdown и блоками
        """
        # Рендерим страницу в изображение
        pix = page.get_pixmap(dpi=150)  # 150 DPI для баланса качества/размера
        img_bytes = pix.tobytes("png")
        
        # Кодируем в base64
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Формируем запрос
        payload = {
            "image": img_base64,
            "mode": mode.value,
            "prompt": prompt or self.PROMPT_LAYOUT_MARKDOWN,
            "page_id": page.number
        }
        
        # Отправляем запрос
        response_data = self._make_request("/ocr/page", payload)
        
        # Парсим ответ
        return self._parse_ocr_response(response_data, page.number)
    
    def ocr_image(self, image_data: bytes, 
                  page_num: int,
                  bbox: Optional[BBox] = None,
                  mode: OCRMode = OCRMode.BASE,
                  prompt: Optional[str] = None) -> OCRResponse:
        """
        OCR отдельного изображения/фигуры
        
        Args:
            image_data: Байты изображения (PNG/JPEG)
            page_num: Номер страницы (для метаданных)
            bbox: BBox элемента на странице
            mode: Режим OCR
            prompt: Кастомный промпт (по умолчанию PROMPT_FIGURE_PARSING)
        
        Returns:
            OCRResponse: Результат OCR
        """
        # Кодируем в base64
        img_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Формируем запрос
        payload = {
            "image": img_base64,
            "mode": mode.value,
            "prompt": prompt or self.PROMPT_FIGURE_PARSING,
            "page_id": page_num
        }
        
        if bbox:
            payload["bbox"] = bbox.to_tuple()
        
        # Отправляем запрос
        response_data = self._make_request("/ocr/figure", payload)
        
        # Парсим ответ
        return self._parse_ocr_response(response_data, page_num)
    
    def ocr_region(self, page: fitz.Page, bbox: BBox,
                   mode: OCRMode = OCRMode.BASE,
                   prompt: Optional[str] = None) -> OCRResponse:
        """
        OCR отдельной области страницы
        
        Args:
            page: Объект страницы PyMuPDF
            bbox: BBox области для OCR
            mode: Режим OCR
            prompt: Кастомный промпт
        
        Returns:
            OCRResponse: Результат OCR
        """
        # Вырезаем область страницы
        rect = fitz.Rect(*bbox.to_tuple())
        pix = page.get_pixmap(clip=rect, dpi=150)
        img_bytes = pix.tobytes("png")
        
        return self.ocr_image(
            image_data=img_bytes,
            page_num=page.number,
            bbox=bbox,
            mode=mode,
            prompt=prompt
        )
    
    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос к OCR сервису с retry логикой
        
        Args:
            endpoint: Endpoint API (например "/ocr/page")
            payload: JSON payload
        
        Returns:
            Dict с ответом сервера
        
        Raises:
            RuntimeError: При ошибке после всех попыток
        """
        url = f"{self.base_url}{endpoint}"
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._session.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                # Проверяем статус
                response.raise_for_status()
                
                # Парсим JSON
                return response.json()
            
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout после {self.timeout}s"
                continue
            
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                continue
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code >= 500:
                    # Server error - можно retry
                    last_error = f"Server error {status_code}"
                    continue
                else:
                    # Client error - retry бесполезен
                    raise RuntimeError(f"OCR request failed: {e}")
            
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                continue
        
        # Если все попытки исчерпаны
        raise RuntimeError(
            f"OCR request failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    def _parse_ocr_response(self, response_data: Dict[str, Any], 
                           page_num: int) -> OCRResponse:
        """
        Парсинг ответа от OCR сервиса
        
        Ожидаемый формат (из архитектурного анализа):
        {
            "markdown": "...",
            "blocks": [
                {
                    "id": "block_1",
                    "type": "heading",
                    "content": "...",
                    "bbox": [x0, y0, x1, y1],
                    "confidence": 0.95
                },
                ...
            ],
            "vision_tokens": 256,
            "text_tokens": 1024,
            "mode": "Base"
        }
        
        Args:
            response_data: JSON ответ от сервиса
            page_num: Номер страницы
        
        Returns:
            OCRResponse
        """
        # Извлекаем основные поля
        markdown = response_data.get("markdown", "")
        blocks_data = response_data.get("blocks", [])
        vision_tokens = response_data.get("vision_tokens", 0)
        text_tokens = response_data.get("text_tokens", 0)
        mode_str = response_data.get("mode", "Base")
        
        # Парсим режим
        try:
            mode = OCRMode(mode_str)
        except ValueError:
            mode = OCRMode.BASE
        
        # Парсим блоки
        ocr_blocks = []
        confidences = []
        
        for block_data in blocks_data:
            block_id = block_data.get("id", "")
            type_str = block_data.get("type", "paragraph")
            content = block_data.get("content", "")
            bbox_tuple = block_data.get("bbox", [0, 0, 0, 0])
            confidence = block_data.get("confidence", 1.0)
            
            # Парсим тип контента
            try:
                content_type = ContentType(type_str)
            except ValueError:
                content_type = ContentType.PARAGRAPH
            
            bbox = BBox(*bbox_tuple)
            
            ocr_block = OCRBlock(
                id=block_id,
                type=content_type,
                content=content,
                bbox=bbox,
                page_num=page_num,
                confidence=confidence,
                source="ocr",
                metadata=block_data.get("metadata", {})
            )
            
            ocr_blocks.append(ocr_block)
            confidences.append(confidence)
        
        # Средняя уверенность
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        
        return OCRResponse(
            markdown=markdown,
            blocks=ocr_blocks,
            page_id=page_num,
            vision_tokens_used=vision_tokens,
            text_tokens_generated=text_tokens,
            mode=mode,
            confidence_avg=avg_confidence
        )
    
    def health_check(self) -> bool:
        """
        Проверка доступности OCR сервиса
        
        Returns:
            bool: True если сервис доступен
        """
        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Закрыть HTTP сессию"""
        self._session.close()
    
    def __enter__(self):
        """Context manager: вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: выход"""
        self.close()
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"OCRClient(base_url={self.base_url})"


