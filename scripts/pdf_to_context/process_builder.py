"""
Process Builder - построитель процесса из нескольких документов

Объединяет контексты из множественных документов (PDF, DOCX, XLSX)
в единый процесс с RACI, Pipeline, BPMN и документацией.

Логика объединения:
1. Анализ всех _OCR.md файлов
2. Извлечение ролей, задач, связей из каждого документа
3. Объединение в единую структуру процесса
4. Построение RACI матрицы (все уникальные роли)
5. Создание Pipeline (последовательность задач)
6. Генерация BPMN (каждый документ → SubProcess)
7. Создание итоговой документации

Применение SOLID:
- Single Responsibility: Только объединение процессов
- Open/Closed: Легко добавить новые стратегии объединения
- KISS: Простая последовательная логика

Автор: PDFtoBPMN Project
Дата: 10.11.2025
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import re


class ProcessBuilder:
    """
    Построитель единого процесса из нескольких документов
    
    Использование:
    ```python
    builder = ProcessBuilder()
    
    result = builder.build_process(
        ocr_files=[
            "output/Регламент_процесса/Регламент_процесса_OCR.md",
            "output/Роли/Роли_OCR.md",
            "output/Метрики/Метрики_OCR.md"
        ],
        process_name="Управление_качеством",
        output_dir="output/Управление_качеством"
    )
    ```
    """
    
    def __init__(self):
        """Инициализация построителя процессов"""
        self._stats = {
            "documents_processed": 0,
            "roles_found": 0,
            "tasks_found": 0,
            "sections_found": 0
        }
    
    def build_process(self,
                      ocr_files: List[str],
                      process_name: str,
                      output_dir: str) -> Dict[str, str]:
        """
        Построить единый процесс из нескольких документов
        
        Args:
            ocr_files: Список путей к _OCR.md файлам
            process_name: Название итогового процесса
            output_dir: Папка для сохранения результатов
        
        Returns:
            Словарь с путями к созданным файлам:
            {
                "raci_path": "...",
                "pipeline_path": "...",
                "bpmn_path": "...",
                "doc_path": "..."
            }
        """
        print(f"\n🏗️  ПОСТРОЕНИЕ ПРОЦЕССА: {process_name}")
        print(f"📁 Входные документы: {len(ocr_files)}")
        
        # Создаем выходную папку
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Шаг 1: Анализ всех OCR документов
        print("\n📊 ШАГ 1: Анализ документов...")
        documents_data = []
        for ocr_file in ocr_files:
            doc_data = self._analyze_ocr_file(ocr_file)
            documents_data.append(doc_data)
            print(f"   ✓ {doc_data['name']}: {doc_data['sections']} разделов")
        
        self._stats["documents_processed"] = len(documents_data)
        
        # Шаг 2: Объединение ролей
        print("\n👥 ШАГ 2: Объединение ролей...")
        all_roles = self._merge_roles(documents_data)
        print(f"   ✓ Найдено уникальных ролей: {len(all_roles)}")
        self._stats["roles_found"] = len(all_roles)
        
        # Шаг 3: Объединение задач
        print("\n📋 ШАГ 3: Объединение задач...")
        all_tasks = self._merge_tasks(documents_data)
        print(f"   ✓ Найдено задач: {len(all_tasks)}")
        self._stats["tasks_found"] = len(all_tasks)
        
        # Шаг 4: Построение RACI матрицы
        print("\n🎭 ШАГ 4: Построение RACI матрицы...")
        raci_path = output_path / f"{process_name}_RACI.md"
        self._create_raci_matrix(all_roles, all_tasks, documents_data, raci_path)
        print(f"   ✓ Создан: {raci_path.name}")
        
        # Шаг 5: Создание текстового Pipeline
        print("\n🔄 ШАГ 5: Создание Pipeline...")
        pipeline_path = output_path / f"{process_name}_Pipeline.md"
        self._create_pipeline(all_tasks, documents_data, pipeline_path)
        print(f"   ✓ Создан: {pipeline_path.name}")
        
        # Шаг 6: Генерация BPMN (placeholder - требует AI)
        print("\n🎨 ШАГ 6: Генерация BPMN...")
        bpmn_path = output_path / f"{process_name}.bpmn"
        self._create_bpmn_placeholder(process_name, documents_data, bpmn_path)
        print(f"   ✓ Создан шаблон: {bpmn_path.name}")
        
        # Шаг 7: Создание документации
        print("\n📝 ШАГ 7: Создание документации...")
        doc_path = output_path / f"{process_name}.md"
        self._create_documentation(process_name, documents_data, all_roles, all_tasks, doc_path)
        print(f"   ✓ Создан: {doc_path.name}")
        
        # Итоговая статистика
        print(f"\n✅ ПРОЦЕСС ПОСТРОЕН: {process_name}")
        print(f"   📂 Выходная папка: {output_dir}")
        print(f"   📊 Статистика:")
        print(f"      - Документов: {self._stats['documents_processed']}")
        print(f"      - Ролей: {self._stats['roles_found']}")
        print(f"      - Задач: {self._stats['tasks_found']}")
        
        return {
            "raci_path": str(raci_path),
            "pipeline_path": str(pipeline_path),
            "bpmn_path": str(bpmn_path),
            "doc_path": str(doc_path)
        }
    
    def _analyze_ocr_file(self, ocr_file: str) -> Dict[str, Any]:
        """
        Анализ OCR файла для извлечения структуры
        
        Args:
            ocr_file: Путь к _OCR.md файлу
        
        Returns:
            Словарь с данными документа
        """
        file_path = Path(ocr_file)
        
        if not file_path.exists():
            raise FileNotFoundError(f"OCR файл не найден: {ocr_file}")
        
        content = file_path.read_text(encoding='utf-8')
        
        # Извлекаем название документа
        doc_name = file_path.stem.replace('_OCR', '')
        
        # Анализ структуры (простая эвристика)
        sections = self._extract_sections(content)
        roles = self._extract_roles(content)
        tasks = self._extract_tasks(content)
        
        return {
            "name": doc_name,
            "path": str(file_path),
            "content": content,
            "sections": len(sections),
            "section_titles": sections,
            "roles": roles,
            "tasks": tasks
        }
    
    def _extract_sections(self, content: str) -> List[str]:
        """Извлечь заголовки разделов из документа"""
        # Ищем заголовки уровня 1-3 (# ## ###)
        pattern = r'^#{1,3}\s+(.+)$'
        matches = re.findall(pattern, content, re.MULTILINE)
        return [match.strip() for match in matches]
    
    def _extract_roles(self, content: str) -> List[str]:
        """Извлечь упоминания ролей из документа (эвристика)"""
        # Ищем упоминания должностей/ролей
        role_keywords = [
            r'руководитель',
            r'специалист',
            r'менеджер',
            r'ответственный',
            r'исполнитель',
            r'директор',
            r'начальник',
            r'инженер'
        ]
        
        roles = set()
        for keyword in role_keywords:
            pattern = rf'(\w+\s+{keyword}|\{keyword}\s+\w+)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            roles.update([match.strip() for match in matches])
        
        return list(roles)[:10]  # Ограничиваем топ-10
    
    def _extract_tasks(self, content: str) -> List[str]:
        """Извлечь упоминания задач из документа (эвристика)"""
        # Ищем глаголы действия (простая эвристика)
        task_patterns = [
            r'(подготовить|подготовка)\s+([а-яА-Я\s]+)',
            r'(согласовать|согласование)\s+([а-яА-Я\s]+)',
            r'(проверить|проверка)\s+([а-яА-Я\s]+)',
            r'(утвердить|утверждение)\s+([а-яА-Я\s]+)',
            r'(создать|создание)\s+([а-яА-Я\s]+)',
        ]
        
        tasks = []
        for pattern in task_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    task = ' '.join(match).strip()
                else:
                    task = match.strip()
                if len(task) > 5:  # Фильтруем слишком короткие
                    tasks.append(task[:100])  # Обрезаем длинные
        
        return list(set(tasks))[:20]  # Уникальные, топ-20
    
    def _merge_roles(self, documents_data: List[Dict]) -> List[str]:
        """Объединить роли из всех документов"""
        all_roles = set()
        for doc in documents_data:
            all_roles.update(doc.get('roles', []))
        return sorted(list(all_roles))
    
    def _merge_tasks(self, documents_data: List[Dict]) -> List[str]:
        """Объединить задачи из всех документов"""
        all_tasks = []
        for doc in documents_data:
            tasks = doc.get('tasks', [])
            all_tasks.extend([(task, doc['name']) for task in tasks])
        return all_tasks
    
    def _create_raci_matrix(self, roles: List[str], tasks: List[tuple], 
                           documents_data: List[Dict], output_path: Path):
        """Создать RACI матрицу"""
        content = f"# RACI Матрица: {output_path.stem}\n\n"
        content += "## Объединенная матрица ответственности\n\n"
        content += f"**Источники:** {', '.join([doc['name'] for doc in documents_data])}\n\n"
        
        # Заголовок таблицы
        content += "| Задача / Activity | " + " | ".join(roles[:5]) + " |\n"
        content += "|" + "----|" * (len(roles[:5]) + 1) + "\n"
        
        # Заполнение таблицы (placeholder)
        for task, source_doc in tasks[:10]:
            content += f"| {task} ({source_doc}) | " + " | ".join(["?" for _ in roles[:5]]) + " |\n"
        
        content += "\n**Примечание:** ⚠️ RACI роли требуют ручной доработки на основе анализа документов.\n"
        
        output_path.write_text(content, encoding='utf-8')
    
    def _create_pipeline(self, tasks: List[tuple], documents_data: List[Dict], output_path: Path):
        """Создать текстовый Pipeline"""
        content = f"# Pipeline: {output_path.stem}\n\n"
        content += "## Последовательность задач процесса\n\n"
        
        for idx, (task, source_doc) in enumerate(tasks[:20], 1):
            content += f"### {idx}. {task}\n\n"
            content += f"**Источник:** {source_doc}\n\n"
            content += "**Статус:** ⚠️ Требует детального описания (7 пунктов)\n\n"
            content += "---\n\n"
        
        output_path.write_text(content, encoding='utf-8')
    
    def _create_bpmn_placeholder(self, process_name: str, documents_data: List[Dict], output_path: Path):
        """Создать BPMN placeholder (требует AI для полной генерации)"""
        bpmn_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  
  <bpmn:collaboration id="Collaboration_1">
    <bpmn:participant id="Participant_1" name="{process_name}" processRef="Process_1" />
  </bpmn:collaboration>
  
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" name="Старт процесса">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    
    <!-- TODO: Добавить SubProcess для каждого документа -->
"""
        
        for idx, doc in enumerate(documents_data, 1):
            bpmn_template += f"""    
    <!-- SubProcess {idx}: {doc['name']} -->
    <bpmn:subProcess id="SubProcess_{idx}" name="{doc['name']}">
      <!-- TODO: Детальная структура SubProcess -->
    </bpmn:subProcess>
"""
        
        bpmn_template += """
    <bpmn:endEvent id="EndEvent_1" name="Конец процесса">
      <bpmn:incoming>Flow_End</bpmn:incoming>
    </bpmn:endEvent>
    
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="EndEvent_1" />
  </bpmn:process>
  
  <!-- TODO: Добавить визуализацию (BPMNDiagram) -->
  
</bpmn:definitions>
"""
        
        output_path.write_text(bpmn_template, encoding='utf-8')
    
    def _create_documentation(self, process_name: str, documents_data: List[Dict],
                             roles: List[str], tasks: List[tuple], output_path: Path):
        """Создать документацию процесса"""
        content = f"# Документация процесса: {process_name}\n\n"
        
        content += "## Обзор\n\n"
        content += f"Процесс построен на основе {len(documents_data)} документов:\n\n"
        for doc in documents_data:
            content += f"- **{doc['name']}** ({doc['sections']} разделов)\n"
        
        content += "\n## Роли\n\n"
        for role in roles[:10]:
            content += f"- {role}\n"
        
        content += "\n## Задачи\n\n"
        for task, source in tasks[:15]:
            content += f"- {task} *(источник: {source})*\n"
        
        content += "\n---\n\n"
        content += "⚠️ **Примечание:** Документация требует доработки с использованием AI для детального анализа.\n"
        
        output_path.write_text(content, encoding='utf-8')
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику построения"""
        return self._stats.copy()

