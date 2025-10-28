"""
DeepSeek-OCR Microservice - vLLM + FastAPI

HTTP API для OCR обработки с использованием DeepSeek-OCR модели.

Endpoints:
- POST /ocr/page - OCR всей страницы
- POST /ocr/figure - OCR отдельного графического элемента
- GET /health - Проверка здоровья сервиса

Использует vLLM для inference с custom NGramPerReqLogitsProcessor.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import base64
import io
from PIL import Image
import uuid

# vLLM imports (будут доступны в окружении с vLLM)
try:
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import LogitsProcessor
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    print("⚠️  vLLM не установлен. Микросервис работает в stub-режиме.")


# ============================================================================
# Pydantic Models
# ============================================================================

class OCRRequest(BaseModel):
    """Запрос на OCR"""
    image: str  # base64 encoded image
    mode: str = "Base"  # Tiny, Small, Base, Large, Gundam
    prompt: str = "Convert the entire page/image into Markdown format."
    page_id: int = 0
    bbox: Optional[List[float]] = None


class OCRBlockResponse(BaseModel):
    """Блок в ответе OCR"""
    id: str
    type: str
    content: str
    bbox: List[float]
    confidence: float
    metadata: Dict[str, Any] = {}


class OCRResponse(BaseModel):
    """Ответ от OCR"""
    markdown: str
    blocks: List[OCRBlockResponse]
    page_id: int
    vision_tokens: int
    text_tokens: int
    mode: str


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="DeepSeek-OCR Microservice",
    description="OCR сервис на базе vLLM + DeepSeek-OCR",
    version="0.1.0"
)


# ============================================================================
# DeepSeek-OCR Engine
# ============================================================================

class DeepSeekOCREngine:
    """
    Движок для DeepSeek-OCR на базе vLLM
    
    Загружает модель DeepSeek-OCR и обрабатывает запросы.
    """
    
    # Vision tokens по режимам (из DeepSeek-OCR README)
    MODE_TOKENS = {
        "Tiny": 64,
        "Small": 100,
        "Base": 256,
        "Large": 400,
        "Gundam": None  # Dynamic
    }
    
    def __init__(self, model_path: str = "deepseek-ai/deepseek-ocr"):
        """
        Инициализация движка
        
        Args:
            model_path: Путь к модели DeepSeek-OCR
        """
        self.model_path = model_path
        self.llm = None
        
        if VLLM_AVAILABLE:
            self._load_model()
        else:
            print("⚠️  Stub режим: OCR будет возвращать заглушки")
    
    def _load_model(self):
        """Загрузка модели через vLLM"""
        try:
            print(f"🔄 Загрузка модели: {self.model_path}")
            
            self.llm = LLM(
                model=self.model_path,
                trust_remote_code=True,  # Требуется для DeepSeek-OCR
                gpu_memory_utilization=0.9,
                max_model_len=4096,
            )
            
            print("✅ Модель загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            raise
    
    def process_image(self, image_bytes: bytes, mode: str, prompt: str) -> Dict[str, Any]:
        """
        Обработка изображения через OCR
        
        Args:
            image_bytes: Байты изображения
            mode: Режим OCR (Tiny/Small/Base/Large/Gundam)
            prompt: Промпт для модели
        
        Returns:
            Dict с результатами OCR
        """
        if not VLLM_AVAILABLE or not self.llm:
            # Stub режим
            return self._stub_ocr(image_bytes, mode)
        
        try:
            # Загружаем изображение
            image = Image.open(io.BytesIO(image_bytes))
            
            # Формируем inputs для vLLM
            # (точный формат зависит от реализации DeepSeek-OCR)
            
            # Sampling parameters с custom logits processor
            sampling_params = SamplingParams(
                temperature=0.0,  # Детерминированный вывод для OCR
                max_tokens=2048,  # Максимум токенов для вывода
                # logits_processors=[NGramPerReqLogitsProcessor(...)],  # Если доступен
            )
            
            # Inference
            outputs = self.llm.generate(
                prompts=[prompt],
                sampling_params=sampling_params,
                # image=image,  # Передача изображения (API vLLM)
            )
            
            # Извлекаем результат
            generated_text = outputs[0].outputs[0].text
            
            # Парсим Markdown и создаем блоки
            blocks = self._parse_markdown_to_blocks(generated_text)
            
            # Подсчет токенов
            vision_tokens = self.MODE_TOKENS.get(mode, 256)
            text_tokens = len(outputs[0].outputs[0].token_ids)
            
            return {
                "markdown": generated_text,
                "blocks": blocks,
                "vision_tokens": vision_tokens,
                "text_tokens": text_tokens,
                "mode": mode
            }
        
        except Exception as e:
            print(f"❌ Ошибка OCR: {e}")
            raise
    
    def _stub_ocr(self, image_bytes: bytes, mode: str) -> Dict[str, Any]:
        """
        Заглушка для OCR (когда vLLM недоступен)
        
        Возвращает минимальный валидный ответ для тестирования.
        """
        # Извлекаем базовую информацию об изображении
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        
        stub_markdown = f"""# Stub OCR Result

This is a stub response (vLLM not available).

Image size: {width}x{height}
Mode: {mode}

**Note:** This is placeholder text. Deploy vLLM with DeepSeek-OCR for actual OCR.
"""
        
        blocks = [
            {
                "id": f"stub_{uuid.uuid4().hex[:8]}",
                "type": "paragraph",
                "content": "Stub OCR content",
                "bbox": [0, 0, float(width), float(height)],
                "confidence": 1.0,
                "metadata": {"stub": True}
            }
        ]
        
        return {
            "markdown": stub_markdown,
            "blocks": blocks,
            "vision_tokens": self.MODE_TOKENS.get(mode, 256),
            "text_tokens": len(stub_markdown.split()),
            "mode": mode
        }
    
    def _parse_markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Парсинг Markdown в структурированные блоки
        
        Простая эвристика для разбиения на блоки.
        Для продакшена можно использовать markdown parser.
        
        Args:
            markdown: Markdown текст
        
        Returns:
            Список блоков
        """
        blocks = []
        lines = markdown.split('\n')
        
        block_counter = 0
        for line in lines:
            if not line.strip():
                continue
            
            block_counter += 1
            block_id = f"block_{block_counter}_{uuid.uuid4().hex[:8]}"
            
            # Определяем тип блока
            if line.startswith('#'):
                block_type = "heading"
            elif line.startswith('- ') or line.startswith('* '):
                block_type = "list"
            elif line.startswith('|'):
                block_type = "table"
            else:
                block_type = "paragraph"
            
            blocks.append({
                "id": block_id,
                "type": block_type,
                "content": line,
                "bbox": [0, 0, 0, 0],  # TODO: Extract from OCR if available
                "confidence": 0.95,
                "metadata": {}
            })
        
        return blocks


# ============================================================================
# Global Engine Instance
# ============================================================================

# Инициализируем движок при старте
ocr_engine = None

@app.on_event("startup")
async def startup_event():
    """Загрузка модели при старте сервиса"""
    global ocr_engine
    
    # TODO: Получить model_path из environment variables
    model_path = "deepseek-ai/deepseek-ocr"
    
    try:
        ocr_engine = DeepSeekOCREngine(model_path=model_path)
    except Exception as e:
        print(f"❌ Не удалось загрузить модель: {e}")
        print("⚠️  Сервис будет работать в stub-режиме")
        ocr_engine = DeepSeekOCREngine(model_path="stub")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "vllm_available": VLLM_AVAILABLE,
        "model_loaded": ocr_engine is not None and ocr_engine.llm is not None
    }


@app.post("/ocr/page", response_model=OCRResponse)
async def ocr_page(request: OCRRequest):
    """
    OCR всей страницы PDF
    
    Args:
        request: OCRRequest с base64 изображением
    
    Returns:
        OCRResponse с Markdown и блоками
    """
    if not ocr_engine:
        raise HTTPException(status_code=503, detail="OCR engine not initialized")
    
    try:
        # Декодируем base64
        image_bytes = base64.b64decode(request.image)
        
        # Обрабатываем через OCR
        result = ocr_engine.process_image(
            image_bytes=image_bytes,
            mode=request.mode,
            prompt=request.prompt
        )
        
        # Формируем ответ
        return OCRResponse(
            markdown=result["markdown"],
            blocks=[OCRBlockResponse(**b) for b in result["blocks"]],
            page_id=request.page_id,
            vision_tokens=result["vision_tokens"],
            text_tokens=result["text_tokens"],
            mode=result["mode"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing error: {str(e)}")


@app.post("/ocr/figure", response_model=OCRResponse)
async def ocr_figure(request: OCRRequest):
    """
    OCR отдельной фигуры/изображения
    
    Аналогичен /ocr/page, но с другим дефолтным промптом.
    """
    if not ocr_engine:
        raise HTTPException(status_code=503, detail="OCR engine not initialized")
    
    try:
        image_bytes = base64.b64decode(request.image)
        
        result = ocr_engine.process_image(
            image_bytes=image_bytes,
            mode=request.mode,
            prompt=request.prompt
        )
        
        return OCRResponse(
            markdown=result["markdown"],
            blocks=[OCRBlockResponse(**b) for b in result["blocks"]],
            page_id=request.page_id,
            vision_tokens=result["vision_tokens"],
            text_tokens=result["text_tokens"],
            mode=result["mode"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing error: {str(e)}")


# ============================================================================
# Main (для локального запуска)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

