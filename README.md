<div align="center">

# MCP Visual Paradigm

**Интеллектуальный мост между LLM-агентами и САПР Visual Paradigm**

Автоматическое проектирование, генерация и визуальная расстановка 4 видов диаграмм по тексту ТЗ в стандарте **OMG XMI 2.1 (UML 2.x)** для **Visual Paradigm**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-412991?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![Standard](https://img.shields.io/badge/Standard-OMG_XMI_2.1-orange?style=for-the-badge)](https://www.omg.org/spec/XMI/)
[![Target CAD](https://img.shields.io/badge/Target-Visual_Paradigm-00599C?style=for-the-badge)](https://www.visual-paradigm.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

> **MCP Visual Paradigm** позволяет любой модели (Claude, Gemini, GPT, Cursor) на лету превращать неструктурированные требования ТЗ в полноценные инженерные модели данных, диаграммы классов, сценарии использования и конечные автоматы, готовые к открытию в Visual Paradigm одним кликом без ручной вёрстки.

</div>

---

## Оглавление

- [Ключевые возможности](#ключевые-возможности)
- [Два режима использования: Standalone и Live Sync](#два-режима-использования-standalone-и-live-sync)
- [Поддерживаемые типы диаграмм](#поддерживаемые-типы-диаграмм)
  - [1. UML Class Diagram](#1-uml-class-diagram)
  - [2. ER Diagram (Физическая модель БД)](#2-er-diagram-физическая-модель-бд)
  - [3. UML Use Case Diagram](#3-uml-use-case-diagram)
  - [4. UML State Machine Diagram](#4-uml-state-machine-diagram)
- [Таблица типов данных ER-диаграмм](#таблица-типов-данных-er-диаграмм)
- [Быстрый старт](#быстрый-старт)
- [Подключение к MCP-клиентам](#подключение-к-mcp-клиентам)
  - [Универсальная конфигурация (stdio)](#универсальная-конфигурация-stdio)
  - [Настройка в Cursor](#настройка-в-cursor)
  - [Настройка в Claude Desktop](#настройка-в-claude-desktop)
  - [Настройка в Antigravity IDE / VS Code / Windsurf](#настройка-в-antigravity-ide--vs-code--windsurf)
- [Полный справочник инструментов MCP](#полный-справочник-инструментов-mcp)
- [Импорт модели в Visual Paradigm](#импорт-модели-в-visual-paradigm)
- [Нативный Java-плагин (Live Sync и Agent Vision)](#нативный-java-плагин-live-sync-и-agent-vision)
- [Архитектура и движки сервера](#архитектура-и-движки-сервера)
- [Тестирование и валидация](#тестирование-и-валидация)

---

## Два режима использования: Standalone и Live Sync

Архитектура проекта поддерживает два независимых сценария интеграции в зависимости от потребностей пользователя:

### 1. Автономный режим (Только MCP-сервер, без плагинов)
* **Как работает**: Вы подключаете `main.py` к Cursor, Claude Desktop, Antigravity или Windsurf. Плагин в Visual Paradigm устанавливать **не требуется**.
* **Процесс**:
  1. Вы передаете AI-агенту текст технического задания.
  2. Агент строит полную инженерную модель (2D-сетка пакетов, вложенные структуры, классы, таблицы ERD, Use Case, State Machine).
  3. Сервер валидирует архитектурные правила и сохраняет файл формата OMG XMI 2.1 (например, `architecture.xmi`).
  4. Вы открываете файл в Visual Paradigm штатным способом: **`Project` $\rightarrow$ `Import` $\rightarrow$ `XMI...`**.
* **Кому подходит**: Тем, кому нужен быстрый старт без изменений конфигурации САПР или прав администратора.

### 2. Интегрированный режим (MCP-сервер + Java-плагин Live Sync)
* **Как работает**: Устанавливается в 1 клик с помощью файла **`install_plugin.bat`**. В Visual Paradigm появляется панель управления и запускается локальный сокет-сервер (`127.0.0.1:19842`).
* **Процесс (полная автоматизация)**:
  1. Вы держите открытым окно Visual Paradigm.
  2. Агент проектирует систему по ТЗ и вызывает `batch_build_diagrams`.
  3. Модель **мгновенно и автоматически открывается прямо на экране в активном окне Visual Paradigm** (Live Sync без ручных действий).
  4. Включается **Agent Vision**: агент вызывает инструмент `export_diagram_image`, получает отрендеренный PNG открытой диаграммы и осматривает разметку через зрение мультимодальной нейросети, оценивая читаемость и выравнивание.
* **Кому подходит**: Для максимального комфорта и работы в режиме реального времени.

---

## Ключевые возможности

* **Полная совместимость с Visual Paradigm**: Генерация нативных контейнеров метамоделей (`DBTable`, `DBColumn`, `DBForeignKey`, `State2`, `Transition2`, `uml:Component`), исключающая появление "битых" элементов или артефактов импорта.
* **Visual Layout Engine (Встроенный умный лейаут)**: Автоматический расчет 2D-координат ($x, y, w, h$) и геометрии соединителей. Диаграммы импортируются **сразу разложенными по сетке**, без наложения фигур друг на друга.
* **Архитектурный валидатор (Rules Engine)**: Защита от логических ошибок:
  * Проверка циклических зависимостей и наследования ($A \rightarrow B \rightarrow C \rightarrow A$).
  * Запрет приватных членов в интерфейсах (`Interface`).
  * Контроль внешних ключей в ERD (связь `1:N` требует FK-колонку в целевой таблице).
  * Валидация Use Case отношений (`Include`/`Extend` только между прецедентами).
* **Семантический NLP-построитель (`smart_add_relation`)**: Позволяет модели соединять сущности естественным языком (*«заказ состоит из позиций»* $\rightarrow$ `Composition`, *«оплата использует шлюз»* $\rightarrow$ `Dependency`).
* **Open Specification & HTML-документация**: Описания классов, колонок, методов, акторов и переходов прописываются в атрибуты документации Visual Paradigm.
* **Нулевой визуальный шум**: Очистка меток от дублирующихся ролей связей (`ashowFromRoleName='false'`), аккуратные соединители Crow's Foot и чистая типографика.

---

## Поддерживаемые типы диаграмм

### 1. UML Class Diagram
* **Пакеты (Packages)**: Логическая и физическая вложенность (контейнеры пакетов с размещением дочерних классов внутри).
* **Классификаторы**: Обычные классы, абстрактные классы (`isAbstract=True`), интерфейсы (`isInterface=True`).
* **Члены**: Поля и методы с типами, значениями по умолчанию, модификаторами видимости (`public`, `private`, `protected`, `package`).
* **Связи**: `Generalization`, `Realization`, `Association`, `Aggregation` ($1 \rightarrow *$), `Composition` ($1 \rightarrow 1..*$), `Dependency`.
* **Заметки (Notes)**: Блоки комментариев (`Note`) с коннекторами `Anchor` к целевым классам.

### 2. ER Diagram (Физическая модель БД)
* **Нативные таблицы Visual Paradigm**: Формирование `DBTable` в фирменном персиковом оформлении (`#F5B67A`).
* **Колонки (`DBColumn`)**: Отметки Primary Key (`PK`), Foreign Key (`FK`), Unique (`U`), Not Null, ограничения длины и масштаба.
* **Нативные связи `DBForeignKey`**: Отображение соединений в нотации «Воронья лапка» (Crow's Foot) с кратностями `1:1`, `1:N`, `M:N`.

### 3. UML Use Case Diagram
* **Субъекты и сценарии**: Акторы (`uml:Actor`) и Прецеденты (`uml:UseCase`).
* **Системные границы (System Boundary)**: Контейнеры границ системы (`uml:Component`) с визуальным включением вложенных юзкейсов.
* **Отношения**: Ассоциации акторов со сценариями, стандартизированные стереотипы `«Include»` и `«Extend»`.

### 4. UML State Machine Diagram
* **Узлы**: Начальное состояние (`Initial Pseudostate` со сплошной черной заливкой), финальное состояние (`FinalState`), рабочие состояния (`State2`).
* **Внутренние активности**: Поддержка блоков `entry`, `do` и `exit` прямо в теле состояния.
* **Переходы (`Transition2`)**: События-триггеры (`trigger`) и сторожевые условия (`[guard]`).

---

## Таблица типов данных ER-диаграмм

В Visual Paradigm физические ER-диаграммы поддерживают 19 стандартных типов данных из системной палитры, а также основные типы СУБД (PostgreSQL/MySQL):

| Категория | Поддерживаемые типы Visual Paradigm | Дополнительные типы СУБД | Авто-нормализация лишних типов |
| :--- | :--- | :--- | :--- |
| **Целочисленные** | `bigint`, `integer`, `smallint`, `tinyint` | `int8`, `int4`, `int2` | `SERIAL`, `BIGSERIAL` $\rightarrow$ `integer` / `bigint` |
| **С плавающей точкой / Точные** | `decimal`, `numeric`, `double`, `float`, `real` | `float8`, `float4` | `money`, `dec` $\rightarrow$ `decimal` |
| **Символьные / Строковые** | `varchar`, `char`, `clob` | — | `text`, `json`, `jsonb` $\rightarrow$ `clob`; `interval` $\rightarrow$ `varchar` |
| **Бинарные данные** | `binary`, `varbinary`, `blob` | `bytea` | `bytea` $\rightarrow$ `blob` |
| **Логические** | `bit` | `bool`, `boolean` | `bool` сохраняется или сопоставляется с `bit` |
| **Дата и время** | `date`, `time`, `timestamp` | — | `timestamptz` $\rightarrow$ `timestamp`; `timetz` $\rightarrow$ `time` |
| **Идентификаторы** | — | `uuid` | `uuid` сохраняется как отдельный тип |

> [!TIP]
> При указании типов можно использовать как верхний, так и нижний регистр, а также указывать длину: `VARCHAR(255)`, `NUMERIC(10, 2)`, `BIGINT`. Сервер автоматически извлечет длину и сопоставит тип с нативным кодом Visual Paradigm.

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/Larom4ik/mcp-visual-paradigm.git
cd mcp-visual-paradigm
```

### 2. Установка зависимостей

Требуется **Python 3.10+**:

```bash
python -m venv .venv
# Активация окружения:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Проверка работоспособности тестами

```bash
python test_all_diagrams.py
```

> Тест создает полную демонстрационную систему (все 4 диаграммы со связями), генерирует файл `enterprise_system.xmi` и выполняет 100% валидацию XML-дерева по стандартам OMG XMI 2.1.

---

## Подключение к MCP-клиентам

Все современные AI-среды поддерживают протокол MCP через стандартный ввод/вывод (`stdio`). Подключение выполняется единообразно через конфигурационный JSON.

### Универсальная конфигурация (stdio)

```json
{
  "mcpServers": {
    "visual-paradigm": {
      "command": "python",
      "args": ["E:\\mcp-visual-paradigm\\main.py"]
    }
  }
}
```

> [!NOTE]
> Замените `E:\\mcp-visual-paradigm\\main.py` на абсолютный путь к вашему файлу `main.py`. Если используется виртуальное окружение, в поле `command` укажите полный путь к интерпретатору (например, `E:\\mcp-visual-paradigm\\.venv\\Scripts\\python.exe`).

---

<details open>
<summary><b>Настройка в Cursor</b></summary>

1. Перейдите в **Settings** $\rightarrow$ **Features** $\rightarrow$ **MCP Servers**.
2. Нажмите **+ Add New MCP Server**.
3. Заполните поля:
   - **Name**: `visual-paradigm`
   - **Type**: `command`
   - **Command**: `python E:\mcp-visual-paradigm\main.py`
4. Либо откройте/создайте файл `.cursor/mcp.json` в корне рабочего пространства и добавьте блок конфигурации выше.
</details>

<details>
<summary><b>Настройка в Claude Desktop</b></summary>

Откройте файл конфигурации Claude Desktop:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Вставьте:
```json
{
  "mcpServers": {
    "visual-paradigm": {
      "command": "python",
      "args": ["E:\\mcp-visual-paradigm\\main.py"]
    }
  }
}
```
Перезапустите Claude Desktop (на Windows закройте приложение через трей).
</details>

<details>
<summary><b>Настройка в Antigravity IDE / VS Code (Cline / Roo Code / Continue)</b></summary>

В Antigravity IDE добавьте сервер в файл конфигурации `.agents/mcp_config.json` или глобальный `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "visual-paradigm": {
      "command": "python",
      "args": ["E:\\mcp-visual-paradigm\\main.py"]
    }
  }
}
```
Для плагинов VS Code (например, Cline / Roo Code) перейдите в настройки расширения в раздел **MCP Settings** и добавьте ту же секцию.
</details>

---

## Полный справочник инструментов MCP

Сервер предоставляет LLM-агенту **25 специализированных инструментов**, разделенных по архитектурным областям:

### 1. Управление проектом и пакетная сборка
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `batch_build_diagrams` | `spec: dict, filepath: Optional[str] = None` | Основной инструмент для ТЗ: создает сразу все 4 вида диаграмм (пакеты, классы, таблицы ERD, сценарии Use Case, конечные автоматы, заметки) за 1 вызов и автоматически генерирует готовый `.xmi`. |
| `init_project` | `name: str = "ProjectModel"` | Инициализирует новый проект с заданным именем и сбрасывает предыдущее состояние. |
| `sync_with_visual_paradigm` | `filepath: Optional[str] = None` | Отправляет сгенерированную модель напрямую в запущенный Visual Paradigm через фоновый Live Sync плагин. |
| `export_diagram_image` | `diagram_name: Optional[str] = None, output_path: Optional[str] = None` | Экспортирует активную или указанную диаграмму из Visual Paradigm в высоком разрешении (PNG) для визуальной валидации агентом (Agent Vision через `view_file`). |
| `get_project_summary` | — | Возвращает подробное структурированное дерево всех элементов по всем диаграммам (для саморефлексии модели). |
| `set_element_documentation` | `element_name: str, documentation: str` | Добавляет или обновляет подробное описание (Open Specification / HTML-документацию) для любого элемента. |
| `export_xmi` | `filepath: str` | Запускает Visual Layout Engine и сохраняет чистый файл формата OMG XMI 2.1. |

<details>
<summary><b>Пример структуры JSON для <code>batch_build_diagrams</code></b></summary>

```json
{
  "project_name": "ECommerceSystem",
  "packages": [
    {"name": "DomainModel"}
  ],
  "classes": [
    {
      "name": "Order",
      "package": "DomainModel",
      "attributes": [
        {"name": "id", "type": "uuid", "visibility": "private"},
        {"name": "totalAmount", "type": "decimal", "visibility": "private"}
      ],
      "methods": [
        {"name": "calculateTotal", "return_type": "decimal", "visibility": "public", "parameters": []}
      ]
    }
  ],
  "class_relations": [
    {"source": "Order", "target": "OrderItem", "type": "Composition", "source_multiplicity": "1", "target_multiplicity": "1..*"}
  ],
  "entities": [
    {
      "name": "orders",
      "columns": [
        {"name": "id", "type": "uuid", "is_pk": true, "is_nullable": false},
        {"name": "status", "type": "varchar", "length": 50, "is_nullable": false}
      ]
    }
  ],
  "er_relations": [
    {"source": "customers", "target": "orders", "type": "1:N"}
  ],
  "actors": [
    {"name": "Customer", "description": "Покупатель интернет-магазина"}
  ],
  "use_cases": [
    {"name": "CheckoutOrder", "description": "Оформление заказа"}
  ],
  "system_boundary": {
    "name": "E-Commerce System",
    "use_cases": ["CheckoutOrder"]
  },
  "uc_relations": [
    {"source": "Customer", "target": "CheckoutOrder", "type": "Association"}
  ],
  "states": [
    {"name": "Initial", "type": "Initial"},
    {"name": "PendingPayment", "type": "State", "entry": "startTimer()"},
    {"name": "Paid", "type": "State"},
    {"name": "Completed", "type": "Final"}
  ],
  "transitions": [
    {"source": "Initial", "target": "PendingPayment"},
    {"source": "PendingPayment", "target": "Paid", "trigger": "paymentReceived", "guard": "amount > 0"},
    {"source": "Paid", "target": "Completed"}
  ],
  "notes": [
    {"text": "Все цены рассчитываются с учетом НДС", "attached_to": "Order"}
  ]
}
```
</details>

### 2. Диаграмма классов (UML Class Diagram)
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `add_package` | `name: str, parent_package: Optional[str] = None` | Создает пакет для организации пространства имен и визуального контейнера (поддерживает вложенность). |
| `move_class_to_package` | `class_name: str, package_name: str` | Перемещает существующий класс или интерфейс внутрь указанного пакета. |
| `add_class` | `name: str, element_type: str = "Class", is_abstract: bool = False, package: Optional[str] = None, description: str = ""` | Создает обычный класс, абстрактный класс или интерфейс (`element_type="Interface"`). |
| `add_class_attribute`| `class_name: str, name: str, type: str = "String", visibility: str = "public", default_value: Optional[str] = None, description: str = ""` | Добавляет поле с типом, видимостью (`public`, `private`, `protected`) и значением по умолчанию. |
| `add_class_method` | `class_name: str, name: str, return_type: str = "void", visibility: str = "public", parameters: Optional[list] = None, description: str = ""` | Добавляет метод с возвращаемым типом и списком параметров `[{"name": "...", "type": "..."}]`. |
| `add_class_relation` | `src_name: str, tgt_name: str, type: str, src_mult: str = "", tgt_mult: str = ""` | Создает связь (`Generalization`, `Realization`, `Association`, `Aggregation`, `Composition`, `Dependency`) с кратностями. |
| `suggest_relation` | `source: str, target: str, description: str` | Анализирует текстовое описание взаимосвязи двух сущностей и рекомендует наиболее подходящий тип отношения. |
| `smart_add_relation` | `source: str, target: str, relationship_hint: str = "", description: str = ""` | Семантический NLP-построитель: распознает намерение из подсказки на естественном языке и автоматически создает связь. |

### 3. Диаграмма сущностей (ER Diagram)
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `add_er_entity` | `name: str, description: str = ""` | Создает нативную таблицу базы данных Visual Paradigm (`DBTable`). |
| `add_er_column` | `entity_name: str, name: str, type: str = "VARCHAR", length: Optional[int] = None, is_nullable: bool = True, is_pk: bool = False, is_fk: bool = False, is_unique: bool = False, description: str = ""` | Добавляет колонку с ограничениями PK/FK/Unique/NotNull и нативными типами VP (с авто-извлечением длины). |
| `add_er_relation` | `src_name: str, tgt_name: str, type: str` | Создает соединение Crow's Foot (`1:1`, `1:N`, `M:N`) с проверкой наличия внешнего ключа в дочерней таблице. |

### 4. Диаграмма прецедентов (Use Case Diagram)
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `add_actor` | `name: str, description: str = ""` | Создает актора системы (`uml:Actor`). |
| `add_use_case` | `name: str, description: str = ""` | Создает прецедент использования (`uml:UseCase`). |
| `set_system_boundary`| `name: str = "System", use_cases: Optional[str] = None` | Устанавливает визуальный прямоугольный контейнер границы системы (`uml:Component`), охватывающий прецеденты. |
| `add_uc_relation` | `src_name: str, tgt_name: str, type: str` | Создает отношение (`Association` для акторов; `Include` и `Extend` строго между прецедентами по правилам UML 2.5). |

### 5. Диаграмма состояний (State Machine Diagram)
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `add_state` | `name: str, type: str = "State", entry: str = "", do: str = "", exit: str = "", description: str = ""` | Создает состояние (`Initial`, `State`, `Final`) с активностями `entry`, `do`, `exit`. |
| `add_state_behavior`| `state_name: str, entry: str = "", do: str = "", exit: str = "", description: str = ""` | Добавляет или изменяет внутренние действия `entry`, `doActivity`, `exit` или описание у существующего состояния. |
| `add_state_transition`| `src_name: str, tgt_name: str, trigger: str = "", guard: str = ""` | Создает переход (`Transition2`) с событием-триггером и сторожевым условием `[guard]`. |

### 6. Заметки (Notes & Anchors)
| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `add_note` | `text: str, target: Optional[str] = None` | Создает визуальный блок заметки (`Note`) с коннектором привязки `Anchor` к любому элементу диаграммы. |

---

## Импорт модели в Visual Paradigm

После того как модель сгенерировала XMI-файл (например, `output.xmi`):

1. Запустите **Visual Paradigm**.
2. В верхнем главном меню выберите:  
   **`Project` $\rightarrow$ `Import` $\rightarrow$ `XMI...`**
3. В появившемся диалоговом окне:
   - Выберите сгенерированный файл `.xmi`.
   - Оставьте опцию импорта диаграмм включенной.
4. Нажмите **OK**.
5. Все 4 диаграммы появятся в **Diagram Navigator**, а сущности — в **Model Explorer**. При открытии диаграммы все элементы будут визуально разложены и выровнены.

> [!IMPORTANT]
> Если в проекте уже были открыты другие диаграммы, Visual Paradigm добавит новые диаграммы в текущую рабочую область без затирания существующих данных.

---

## Нативный Java-плагин (Live Sync)

Для максимальной автоматизации в каталог `plugin/` включен нативный Java-плагин для Visual Paradigm 18.1+, созданный на базе Visual Paradigm OpenAPI.

### Возможности плагина:
1. **Кнопка в главном меню Visual Paradigm**:
   - Вкладка ленты меню **MCP** $\rightarrow$ группа **Actions** $\rightarrow$ **Import MCP Diagram (XMI)...**
   - Позволяет выбрать и открыть любой сгенерированный XMI-файл в 1 клик.
2. **Встроенный фоновый сервер Live Sync (`127.0.0.1:19842`)**:
   - Автоматически слушает команды от Python MCP-сервера.
   - Когда модель или пользователь вызывает `export_xmi`, `batch_build_diagrams` или `sync_with_visual_paradigm`, диаграммы **мгновенно отрисовываются прямо на экране в активном окне Visual Paradigm** без ручного импорта.
3. **Обратный экспорт диаграмм в PNG (Agent Vision)**:
   - Эндпоинт `/export_image` на базе `ModelConvertionManager.exportDiagramAsImage` генерирует растровое изображение PNG открытой диаграммы.
   - Мультимодальный AI-агент получает путь к файлу и с помощью инструмента `view_file` осматривает результат своими глазами, оценивая сетку, взаимное расположение блоков, читаемость и плотность связей.

### Быстрая установка (в 1 клик):
Дважды запустите файл **`install_plugin.bat`** в корне репозитория (или выполните команду в консоли):
```powershell
powershell -ExecutionPolicy Bypass -File plugin/build.ps1
```
Скрипт компилирует Java-исходники под целевую платформу Java 11 (стандартная среда Visual Paradigm 18.1), собирает `lib/mcp-plugin.jar`, копирует иконки интерфейса и устанавливает плагин в пользовательский каталог `%APPDATA%\VisualParadigm\plugins\com.mcp.visualparadigm\`.

После выполнения команды запустите или перезапустите Visual Paradigm — плагин активируется автоматически.

---

## Архитектура и движки сервера

```
mcp-visual-paradigm/
├── core/
│   ├── models.py           # Строгие Pydantic v2 модели данных (Node с UUID, ограничения, валидаторы)
│   ├── rules.py            # Архитектурный валидатор (циклы наследования, правила FK, интерфейсов)
│   └── state.py            # Потокобезопасное хранилище Singleton (ProjectState)
├── mcp_tools/
│   └── tools.py            # 26 MCP-инструментов с типизацией и валидацией
├── exporters/
│   ├── layout_engine.py    # Двумерная сетка (2D Grid Layout) и иерархическое размещение
│   └── xmi_builder.py      # Ядро генерации OMG XMI 2.1 и интеграции Visual Paradigm
├── plugin/                 # Нативный Java-плагин для Visual Paradigm (Live Sync и Agent Vision)
│   ├── src/                # Исходный код Java (MCPPlugin, MCPSyncServer, Controllers)
│   ├── plugin.xml          # Манифест плагина Visual Paradigm
│   ├── build.ps1           # Скрипт компиляции и развертывания
│   └── README.md           # Документация REST API плагина
├── main.py                 # Точка входа stdio-сервера
├── requirements.txt        # Зависимости проекта
├── test_all_diagrams.py    # E2E тестирование экспорта всех 4 диаграмм
├── test_erd_types.py       # Юнит-тестирование палитры типов данных ERD
└── test_plugin_server.py   # Тест протокола Live Sync
```

1. **State Store (`core/state.py`)**: Потокобезопасный singleton-реестр, хранящий карты классификаторов, сущностей БД, акторов, состояний и связей.
2. **Rules Engine (`core/rules.py`)**: Обеспечивает обратную связь для LLM: при обнаружении некорректного вызова возвращает подробную ошибку валидации вместо падения сервера, позволяя агенту исправить действие на следующем шаге.
3. **XMI Builder & Visual Layout Engine (`exporters/xmi_builder.py`)**:
   - Формирует корректное пространство имен XML: `xmlns:uml="http://schema.omg.org/spec/UML/2.1"`, `xmlns:xmi="http://schema.omg.org/spec/XMI/2.1"`.
   - Включает расширения Visual Paradigm (`xmi:Extension extender="Visual Paradigm"`).
   - Вычисляет абсолютные координаты фигур и точек соединителей (`geometry="x1,y1;x2,y2;"`).
   - Настраивает цветовые палитры (персиковый для DBTable, классический черный для State, чистые контейнеры для системных границ).

---

## Тестирование и валидация

В репозитории предусмотрен комплекс тестов:

```bash
# 1. Тестирование всех 19 типов данных ERD и нормализации
python test_erd_types.py

# 2. Полный сквозной тест создания всех 4 диаграмм и проверка валидности XMI
python test_all_diagrams.py

# 3. Тестирование бизнес-правил валидатора и движка визуального лейаута
python test_rules_and_visual.py
```

Все тесты работают автономно без необходимости запуска САПР и завершаются со статусом 100% успеха.

---

<div align="center">

Разработано для бесшовной автоматизации системного анализа и проектирования архитектуры ПО с помощью AI-агентов.

Если проект оказался вам полезен, вы можете поставить звезду репозиторию на GitHub.

</div>
