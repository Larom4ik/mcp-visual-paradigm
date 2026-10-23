# mcp-visual-paradigm

Production-ready локальный MCP-сервер (Model Context Protocol) на Python, выступающий мостом между LLM-агентами (Cursor, Claude Desktop, Windsurf) и САПР **Visual Paradigm**.

Сервер накапливает данные диаграмм в оперативной памяти (Singleton State) и генерирует безупречный XML-файл в стандарте **OMG XMI 2.1 (UML 2.x)** для построения 4 типов диаграмм:
1. **UML Class Diagram** (Классы, Атрибуты, Методы, Наследование, Ассоциации, Композиции, Зависимости, Реализации)
2. **ER Diagram** (Сущности/Таблицы БД, Колонки с PK/FK стереотипами, Связи 1:1, 1:N, M:N)
3. **UML Use Case Diagram** (Акторы, Прецеденты использования, Include, Extend, Связи)
4. **UML State Machine Diagram** (Конечный автомат: Initial Pseudostate, State, FinalState, Переходы с событиями)

---

## Архитектура проекта

```
mcp-visual-paradigm/
├── core/
│   ├── __init__.py
│   ├── models.py           # Строгие Pydantic-модели данных (BaseNode c xmi:id)
│   └── state.py            # Потокобезопасное хранилище Singleton (ProjectState)
├── mcp_tools/
│   ├── __init__.py
│   └── tools.py            # 15 MCP-инструментов с подробными docstrings
├── exporters/
│   ├── __init__.py
│   └── xmi_builder.py      # Ядро генерации XMI 2.1 (OMG UML 2.x)
├── main.py                 # Инициализация FastMCP/MCPServer и запуск stdio
├── requirements.txt        # Зависимости
├── test_all_diagrams.py    # E2E тесты всех 4 диаграмм и валидация XMI
└── README.md               # Документация
```

---

## Установка и запуск

### 1. Установка зависимостей

Требуется Python 3.10+:

```bash
pip install -r requirements.txt
```

### 2. Запуск автоматических тестов

```bash
python test_all_diagrams.py
```

Скрипт проверяет создание всех 4 типов диаграмм, строит связи и валидирует XMI-файл на соответствие стандарту OMG UML 2.x.

---

## Подключение к MCP-клиентам (stdio)

### Cursor (`.cursor/mcp.json`)

В Cursor откройте **Settings > Features > MCP > Add New MCP Server** или добавьте в `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "visual-paradigm": {
      "command": "python",
      "args": ["E:/mcp-visual-paradigm/main.py"]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "visual-paradigm": {
      "command": "python",
      "args": ["E:/mcp-visual-paradigm/main.py"]
    }
  }
}
```

---

## Справочник инструментов MCP (15 Tools)

### Управление проектом
- `init_project(name: str)`: Очищает память и инициализирует проект с заданным именем.
- `export_xmi(filepath: str)`: Генерирует валидный XMI 2.1 файл по указанному пути.
- `get_project_summary()`: Возвращает текстовое дерево всех элементов и связей.

### 1. UML Class Diagram
- `add_class(name: str)`: Создает класс с уникальным ID.
- `add_class_attribute(class_name: str, name: str, type: str, visibility: str = "public")`: Добавляет атрибут (`public`, `private`, `protected`).
- `add_class_method(class_name: str, name: str, return_type: str = "void", params: list = None)`: Добавляет метод с параметрами и направлением (`in`, `out`, `return`).
- `add_class_relation(src_name: str, tgt_name: str, type: str)`: Добавляет связь (`Association`, `Generalization`, `Composition`, `Aggregation`, `Dependency`, `Realization`).

### 2. ER Diagram (Database)
- `add_er_entity(name: str)`: Создает сущность (таблицу) с eAnnotation Stereotype.
- `add_er_column(entity_name: str, name: str, type: str, is_pk: bool = False, is_fk: bool = False)`: Добавляет колонку с отметками Primary Key (`PK`) и Foreign Key (`FK`).
- `add_er_relation(src_name: str, tgt_name: str, type: str)`: Создает связь сущностей с кратностями (`1:1`, `1:N`, `M:N`).

### 3. Use Case Diagram
- `add_actor(name: str)`: Создает актора (`uml:Actor`).
- `add_use_case(name: str)`: Создает прецедент использования (`uml:UseCase`).
- `add_uc_relation(src_name: str, tgt_name: str, type: str)`: Создает связь (`Association`, `Include`, `Extend`).

### 4. State Machine Diagram
- `add_state(name: str, type: str = "State")`: Создает состояние (`Initial`, `State`, `Final`).
- `add_state_transition(src_name: str, tgt_name: str, trigger: str = "")`: Создает переход между состояниями с событием триггера.

---

## Импорт в Visual Paradigm

1. Откройте **Visual Paradigm**.
2. В главном меню: **Project** > **Import** > **XMI...**
3. Укажите сгенерированный файл `.xmi`.
4. Нажмите **OK**. Все сущности, классы, связи, сценарии использования и машины состояний появятся в **Model Explorer** и готовы к размещению на диаграммах.
