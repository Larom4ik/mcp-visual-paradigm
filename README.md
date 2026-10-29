<div align="center">

# MCP Visual Paradigm

**Интеллектуальный мост между LLM-агентами и САПР Visual Paradigm**

Автоматическое проектирование, генерация и визуальная расстановка 6 видов диаграмм по тексту ТЗ в стандарте **OMG XMI 2.1 (UML 2.x)** для **Visual Paradigm**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-412991?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![Standard](https://img.shields.io/badge/Standard-OMG_XMI_2.1-orange?style=for-the-badge)](https://www.omg.org/spec/XMI/)
[![Target CAD](https://img.shields.io/badge/Target-Visual_Paradigm-00599C?style=for-the-badge)](https://www.visual-paradigm.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

> **MCP Visual Paradigm** позволяет современным моделям (Claude, Gemini, GPT, Cursor, Windsurf) преобразовывать технические требования в строгие архитектурные модели данных, диаграммы классов, сценарии использования, конечные автоматы, диаграммы процессов (деятельности) и топологии инфраструктуры развертывания с автоматической компоновкой элементов в Visual Paradigm.

</div>

---

## Содержание

- [Архитектура и режимы работы](#архитектура-и-режимы-работы)
  - [1. Автономный режим (Standalone XMI)](#1-автономный-режим-standalone-xmi)
  - [2. Интегрированный режим (Live Sync Plugin)](#2-интегрированный-режим-live-sync-plugin)
- [Поддерживаемые типы диаграмм](#поддерживаемые-типы-диаграмм)
  - [1. UML Class Diagram](#1-uml-class-diagram)
  - [2. ER Diagram (Реляционная модель БД)](#2-er-diagram-реляционная-модель-бд)
  - [3. UML Use Case Diagram](#3-uml-use-case-diagram)
  - [4. UML State Machine Diagram](#4-uml-state-machine-diagram)
  - [5. UML Activity Diagram](#5-uml-activity-diagram)
  - [6. UML Deployment Diagram](#6-uml-deployment-diagram)
- [Связи в ER-диаграммах и идентифицируемость](#связи-в-er-диаграммах-и-идентифицируемость)
- [Поддержка типов данных PostgreSQL и ANSI SQL](#поддержка-типов-данных-postgresql-и-ansi-sql)
- [Быстрый старт](#быстрый-старт)
- [Подключение к MCP-клиентам](#подключение-к-mcp-клиентам)
  - [Cursor](#cursor)
  - [Claude Desktop](#claude-desktop)
  - [Antigravity IDE / VS Code / Windsurf](#antigravity-ide--vs-code--windsurf)
- [Справочник MCP-инструментов](#справочник-mcp-инструментов)
- [Нативный Java-плагин для Visual Paradigm](#нативный-java-плагин-для-visual-paradigm)
- [Инженерные модули и валидация](#инженерные-модули-и-валидация)
- [Тестирование](#тестирование)

---

## Архитектура и режимы работы

Сервер реализован на базе спецификации **Model Context Protocol (MCP)** и поддерживает два сценария взаимодействия с Visual Paradigm:

```
[ AI-агент / IDE ]
        │ (MCP stdio protocol)
        ▼
┌────────────────────────────────────────────────────────┐
│              MCP Visual Paradigm Server                │
│  - Rules Engine (проверка UML 2.5 / ERD ограничений)   │
│  - Visual Layout Engine (расчет 2D-координат и связей) │
│  - XMI 2.1 Generator (нативная метамодель VP)          │
└──────────────────────────────────────┬─────────────────┘
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        ▼                                                             ▼
[ 1. Standalone Режим ]                                   [ 2. Live Sync Режим ]
Генерация файла OMG XMI 2.1                               HTTP REST API (порт 19842)
Импорт через меню Visual Paradigm:                        Фоновый сокет Java-плагина
Project → Import → XMI...                                 Отрисовка в реальном времени
                                                          Agent Vision (обратный экспорт PNG)
```

### 1. Автономный режим (Standalone XMI)

* **Принцип работы**: Сервер функционирует независимо от Visual Paradigm. Установка сторонних плагинов или прав администратора не требуется.
* **Рабочий процесс**:
  1. AI-агент получает спецификацию требований или ТЗ.
  2. Модель формирует структуру диаграмм через специализированные строители или инструмент `batch_build_diagrams`.
  3. Движок валидации правил (`Rules Engine`) проверяет корректность типов, цикличность связей и ограничения внешних ключей.
  4. Движок визуального лейаута (`Visual Layout Engine`) рассчитывает 2D-координаты сущностей, геометрию соединителей и точки изломов.
  5. Генерируется стандартизированный файл OMG XMI 2.1 (например, `output.xmi`).
  6. Пользователь открывает полученный файл через штатный интерфейс Visual Paradigm: **`Project` → `Import` → `XMI...`**.

### 2. Интегрированный режим (Live Sync Plugin)

* **Принцип работы**: В среду Visual Paradigm устанавливается нативный Java-плагин, запускающий локальный HTTP/REST сервис на порту `127.0.0.1:19842`.
* **Управление сервером**:
  * На ленте **Plugin** и в меню **MCP** размещены кнопки управления:
    * **Connect** — запускает локальный слушатель сокетов плагина.
    * **Disconnect** — останавливает сервер плагина и освобождает сетевой порт.
    * **Import XMI** — диалоговое окно быстрого импорта XMI в один клик.
  * Реализована взаимоисключающая логика состояния (Mutual Exclusivity): активный сервер переводит кнопку **Connect** в неактивное состояние, оставляя доступной только кнопку **Disconnect**, что исключает конфликты сокетов.
* **Рабочий процесс**:
  1. При вызове агентом `sync_with_visual_paradigm` или `batch_build_diagrams` сгенерированная модель транслируется в запущенный сеанс Visual Paradigm по локальному сокету.
  2. Диаграммы открываются в рабочей области САПР автоматически без ручных операций импорта.
  3. Доступен инструмент обратной связи **Agent Vision** (`export_diagram_image`): плагин рендерит активную диаграмму в формат PNG, передает ее агенту для мультимодального анализа геометрии, взаимного перекрытия блоков и читаемости связей.

---

## Поддерживаемые типы диаграмм

### 1. UML Class Diagram

* **Пакеты (Packages)**: Логическая и физическая организация пространства имен с поддержкой вложенности и корректным визуальным содержанием дочерних классификаторов внутри границ пакета.
* **Классификаторы**: Обычные классы, абстрактные классы (`isAbstract=True`), интерфейсы (`isInterface=True`).
* **Члены классификаторов**:
  * Атрибуты с типизацией, значениями по умолчанию и модификаторами видимости (`public`, `private`, `protected`, `package`).
  * Методы со списком типизированных параметров и сигнатурой возвращаемого значения.
* **Отношения между классами**:
  * Наследование / Генерализация (`Generalization`).
  * Реализация интерфейсов (`Realization`).
  * Ассоциация (`Association`) с настройкой кратностей на концах связей.
  * Агрегация (`Aggregation`, `1 → *`).
  * Композиция (`Composition`, `1 → 1..*`).
  * Зависимость (`Dependency`).
* **Заметки (Notes)**: Элементы комментариев `Note` с соединителями `Anchor`, привязанными к целевым классам.

### 2. ER Diagram (Реляционная модель БД)

* **Нативные таблицы Visual Paradigm**: Формирование специализированных метамоделей `DBTable` и `DBColumn` с сохранением свойств в блоке `vpumlChildModels`.
* **Управление ключами и ограничениями**:
  * Строгий контроль первичного ключа: валидатор пресекает случайное дублирование PK.
  * Подавление избыточных маркеров: исключается дублирование флагов уникальности на первичном ключе (чистый индикатор `[PK]` вместо `[PK, U1]`).
  * Автоматическое распознавание внешних ключей (`is_fk=True`, эвристика суффикса `_id`).
  * Поддержка ограничений `Unique`, `Not Null`, длины и числового масштаба.
* **Сбалансированная сетка 2D-компоновки**: Таблицы группируются в сбалансированный двумерный массив с вертикальным позиционированием дочерних таблиц для минимизации пересечения линий.

### 3. UML Use Case Diagram

* **Субъекты и варианты использования**: Акторы (`uml:Actor`) и прецеденты (`uml:UseCase`) с пропорциональным масштабированием геометрии.
* **Границы системы (System Boundary)**: Контейнеры подсистем (`uml:Component`) с группировкой входящих сценариев.
* **Отношения**:
  * Ассоциации между акторами и прецедентами.
  * Отношения включения (`Include`) и расширения (`Extend`) с соблюдением правил UML 2.5 (строго между прецедентами) и адаптивным расчетом габаритов меток стереотипов (`captionBounds`).

### 4. UML State Machine Diagram

* **Узлы автомата**:
  * Начальное псевдосостояние (`Initial Pseudostate`).
  * Рабочие состояния (`State2`).
  * Финальное состояние (`FinalState`).
* **Внутренние активности**: Разделы `entry`, `do` и `exit` внутри тела состояния.
* **Переходы (`Transition2`)**: События-триггеры (`trigger`) и сторожевые условия (`[guard]`).

### 5. UML Activity Diagram (Диаграмма деятельности)

* **Дорожки и зоны ответственности (Partitions / Swimlanes)**: Вертикальные и горизонтальные дорожки (`uml:ActivityPartition`) для разделения зон ответственности между пользователями, сервисами и внешними шлюзами.
* **Узлы потока управления**:
  * Начальный узел (`InitialNode`).
  * Действия и шаги процесса (`Action` / `OpaqueAction`).
  * Узлы принятия решений (`DecisionNode`) и слияния альтернативных путей (`MergeNode`).
  * Узлы параллелизма: разделение (`ForkNode`) и синхронизация (`JoinNode`).
  * Финальные узлы завершения процесса (`ActivityFinalNode`) и потока (`FlowFinalNode`).
* **Потоки управления и данных**:
  * Соединители потоков управления (`ControlFlow`) и потоков данных/объектов (`ObjectFlow`).
  * Поддержка сторожевых условий (`[guard]`), отображаемых вдоль соединительной линии.
* **Автоматический алгоритмический лейаут (`ActivityFlowLayout`)**:
  * Расчет топологических уровней графа (DAG) от истока к стокам.
  * Автоматическое выравнивание элементов по соответствующим полосам Swimlane с точным вложением геометрии (`parentDiagramElement`).

### 6. UML Deployment Diagram (Диаграмма развертывания)

* **Узлы вычислительной инфраструктуры**:
  * Физические серверы и хосты (`Node`).
  * Аппаратные устройства и рабочие станции клиентов (`Device`).
  * Среды исполнения (`ExecutionEnvironment`: контейнеры Docker, Kubernetes, JVM, виртуальные машины, движки СУБД).
  * Поддержка вложенности сред исполнения внутрь физических хостов.
* **Программные артефакты (`Artifact`)**:
  * Исполняемые файлы, сборки (`.jar`, `.war`, `.exe`), файлы конфигурации, образы контейнеров и SQL-скрипты.
  * Визуальное размещение артефактов внутри соответствующих узлов развертывания.
* **Сетевые соединения и пути взаимодействия**:
  * Коммуникационные пути (`CommunicationPath`) с явным указанием сетевых протоколов и портов (например, `HTTPS (Port 443)`, `gRPC (Port 50051)`, `TCP/IP (Port 5432)`).
  * Отношения явного развертывания (`Deployment`, стереотип `«deploy»`).
* **Ярусная топологическая компоновка (`DeploymentTopologyLayout`)**:
  * Автоматическая классификация инфраструктуры по архитектурным ярусам: `Client Tier` → `Gateway / Ingress Tier` → `Application Tier` → `Database / Cache Tier`.
  * Эстетичная визуализация нативной палитры Visual Paradigm (синий градиент `#7ACFF5` для узлов и теплый бежевый для артефактов).

---

## Связи в ER-диаграммах и идентифицируемость

В генераторе реализована поддержка полной матрицы кардинальностей и типов реляционных связей:

| Тип связи | Обозначение | Описание и требования к метамодели |
| :--- | :--- | :--- |
| **Один к одному** | `1:1` | Родительская сущность связывается с уникальной записью дочерней сущности. В дочерней таблице требуется внешний ключ (`is_fk=True`). |
| **Один ко многим** | `1:N` | Классическое отношение "родитель → потомки". Внешний ключ размещается в целевой таблице (`tgt_name`). |
| **Многие к одному** | `N:1` | Обратное отношение "потомок → родитель". Внешний ключ размещается в исходной таблице (`src_name`), что подтверждается валидатором. |
| **Многие ко многим** | `M:N` | Ассоциативное отношение между равноправными сущностями (с поддержкой связующих таблиц). |

### Идентифицирующие и неидентифицирующие связи

Visual Paradigm разделяет физические связи по критерию участия внешнего ключа в составе первичного ключа дочерней таблицы:

* **Идентифицирующая связь (Identifying, `identifying="true"`)**:
  * Возникает, когда колонка внешнего ключа одновременно является частью составного первичного ключа (`is_pk=True` и `is_fk=True`).
  * Дочерняя сущность не может существовать без родительской (зависимость по идентификатору).
  * В интерфейсе Visual Paradigm отображается сплошной линией.
* **Неидентифицирующая связь (Non-Identifying, `identifying="false"`)**:
  * Колонка внешнего ключа не входит в первичный ключ дочерней таблицы (`is_pk=False`, `is_fk=True`).
  * Дочерняя сущность обладает собственным независимым идентификатором.
  * В интерфейсе Visual Paradigm отображается пунктирной линией.

Генератор `XMI Builder` анализирует флаги колонок целевой сущности и автоматически выставляет атрибут `identifying` в дескрипторе `uml:dbForeignKey`.

---

## Поддержка типов данных PostgreSQL и ANSI SQL

При проектировании реляционных схем в Visual Paradigm через меню:
**`Tools` → `DB` → `Database Configuration`** в качестве целевой СУБД может быть выбран профиль **PostgreSQL**.

Генератор XMI поддерживает как стандартную палитру ANSI SQL, так и нативные типы данных диалекта PostgreSQL, предотвращая нежелательную замену типов:

| Категория данных | Нативные типы PostgreSQL в Visual Paradigm | Стандартные типы ANSI SQL | Поведение нормализации |
| :--- | :--- | :--- | :--- |
| **Целочисленные** | `int4` (основной тип), `int2`, `int8` | `integer`, `smallint`, `bigint`, `tinyint` | `SERIAL` → `int4`, `BIGSERIAL` → `int8` |
| **С плавающей точкой** | `float4`, `float8`, `numeric` | `float`, `double`, `real`, `decimal` | Точные типы `numeric(p, s)` сохраняют размерность |
| **Текстовые / Строковые** | `text`, `varchar`, `char` | `varchar`, `char`, `clob` | Тип `text` сохраняется как нативный PostgreSQL `text` (без конвертации в `clob`) |
| **Дата и время** | `timestamp`, `timestamp with time zone`, `time`, `date` | `timestamp`, `time`, `date` | Псевдонимы `timestamptz` сопоставляются с `timestamp with time zone` |
| **Бинарные данные** | `bytea`, `bit` | `binary`, `varbinary`, `blob` | Тип `bytea` сохраняется в нативном формате |
| **Специализированные** | `uuid`, `bool` | `boolean` | `uuid` и `bool` регистрируются напрямую в реестре типов |

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/Larom4ik/mcp-visual-paradigm.git
cd mcp-visual-paradigm
```

### 2. Настройка виртуального окружения

Требуется **Python 3.10+**:

```bash
python -m venv .venv

# Активация окружения в Windows PowerShell:
.venv\Scripts\Activate.ps1

# Активация окружения в Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Проверка тестами

```bash
python test_all_diagrams.py
```

---

## Подключение к MCP-клиентам

Сервер взаимодействует с клиентами через стандартные потоки ввода-вывода (`stdio`).

### Cursor

Добавьте конфигурацию в файл `.cursor/mcp.json` в корне рабочего каталога:

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

Либо добавьте сервер через графический интерфейс: **`Settings` → `Features` → `MCP Servers` → `+ Add New MCP Server`**.

### Claude Desktop

Отредактируйте конфигурационный файл Claude Desktop:
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

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

### Antigravity IDE / VS Code / Windsurf

В Antigravity IDE добавьте секцию в файл `.agents/mcp_config.json`:

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

---

## Справочник MCP-инструментов

Сервер предоставляет 39 специализированных инструментов для управления архитектурной моделью:

### 1. Чтение ТЗ и комплексная сборка
* `read_requirements_file(filepath)` — чтение технического задания (`.docx`, `.txt`, `.md`, `.json`).
* `batch_build_diagrams(spec, append, filepath)` — пакетная сборка всех диаграмм в одном вызове.
* `build_class_diagram(spec, append, diagram_name, filepath)` — генерация диаграммы классов.
* `build_erd_diagram(spec, append, diagram_name, filepath)` — генерация реляционной схемы БД.
* `build_use_case_diagram(spec, append, diagram_name, filepath)` — генерация диаграммы вариантов использования.
* `build_state_diagram(spec, append, diagram_name, filepath)` — генерация диаграммы состояний.
* `build_activity_diagram(spec, append, diagram_name, filepath)` — генерация диаграммы деятельности (процессов).
* `build_deployment_diagram(spec, append, diagram_name, filepath)` — генерация диаграммы развертывания (инфраструктуры).
* `init_project(name)` — инициализация чистого контекста проекта.
* `sync_with_visual_paradigm(filepath)` — отправка модели в активный Visual Paradigm через фоновый плагин.
* `export_diagram_image(diagram_name, output_path)` — экспорт активной диаграммы в PNG (Agent Vision).
* `get_project_summary()` — получение структурированного дампа текущей модели.
* `export_xmi(filepath)` — экспорт модели в файл OMG XMI 2.1.
* `set_element_documentation(element_name, documentation)` — заполнение Open Specification / описания элемента.

### 2. Диаграмма классов (Class Diagram)
* `add_package(name, parent_package)` — создание пакета с поддержкой иерархии.
* `move_class_to_package(class_name, package_name)` — перемещение классификатора в пакет.
* `add_class(name, element_type, is_abstract, package, description)` — добавление класса или интерфейса.
* `add_class_attribute(class_name, name, type, visibility, default_value, description)` — добавление поля.
* `add_class_method(class_name, name, return_type, visibility, parameters, description)` — добавление метода.
* `add_class_relation(src_name, tgt_name, type, src_mult, tgt_mult)` — создание отношения между классами.
* `suggest_relation(source, target, description)` — рекомендация типа связи на основе описания.
* `smart_add_relation(source, target, relationship_hint, description)` — создание связи по текстовой подсказке.

### 3. Реляционная схема (ER Diagram)
* `add_er_entity(name, description)` — создание таблицы БД (`DBTable`).
* `add_er_column(entity_name, name, type, length, is_nullable, is_pk, is_fk, is_unique, description)` — добавление колонки.
* `add_er_relation(src_name, tgt_name, type)` — создание связи (`1:1`, `1:N`, `N:1`, `M:N`) с проверкой внешних ключей.

### 4. Диаграмма прецедентов (Use Case Diagram)
* `add_actor(name, description)` — создание актора.
* `add_use_case(name, description)` — создание прецедента.
* `set_system_boundary(name, use_cases)` — создание границы системы (`System Boundary`).
* `add_uc_relation(src_name, tgt_name, type)` — создание связи (`Association`, `Include`, `Extend`).

### 5. Диаграмма состояний (State Machine Diagram)
* `add_state(name, type, entry, do, exit, description)` — создание состояния.
* `add_state_behavior(state_name, entry, do, exit, description)` — настройка активностей состояния.
* `add_state_transition(src_name, tgt_name, trigger, guard)` — создание перехода с триггером и сторожевым условием.

### 6. Диаграмма деятельности (Activity Diagram)
* `add_activity_partition(name, description)` — создание дорожки / зоны ответственности (`ActivityPartition` / Swimlane).
* `add_activity_node(name, type, partition, description)` — создание узла действия, решения, слияния, ветвления или завершения.
* `add_control_flow(src_name, tgt_name, guard, flow_type)` — создание потока управления (`ControlFlow`) или объекта (`ObjectFlow`) со сторожевым условием.

### 7. Диаграмма развертывания (Deployment Diagram)
* `add_deployment_node(name, node_type, parent_node, description)` — создание вычислительного узла (`Node`, `Device`, `ExecutionEnvironment`).
* `add_artifact(name, deployed_on_node, file_name, description)` — создание программного артефакта (`Artifact`), привязанного к хосту.
* `add_communication_path(src_node, tgt_node, protocol, description)` — создание коммуникационного пути с сетевым протоколом и портом.
* `add_deployment_link(artifact_name, node_name, description)` — создание явной зависимости развертывания (`«deploy»`).

### 8. Аннотации и комментарии
* `add_note(text, target)` — создание визуального блока `Note` с коннектором `Anchor`.

---

## Нативный Java-плагин для Visual Paradigm

Для обеспечения синхронизации в реальном времени разработан плагин на базе OpenAPI Visual Paradigm 18.1+.

### Архитектура плагина
* **Встроенный HTTP-сервер (`MCPSyncServer`)**: обслуживает локальный порт `127.0.0.1:19842` и обрабатывает команды импорта XMI и экспорта графики.
* **Панель управления**: кнопки **Connect**, **Disconnect** и **Import XMI** интегрируются в панель ленты и главное меню.
* **Автоматическое открытие диаграмм**: после передачи XMI плагин автоматически открывает созданные диаграммы в активной рабочей области.
* **Agent Vision**: эндпоинт `/export_image` генерирует растровое изображение текущей диаграммы для верификации нейросетью.

### Установка плагина

Запустите командный файл:

```cmd
install_plugin.bat
```

Либо выполните скрипт сборки напрямую:

```powershell
powershell -ExecutionPolicy Bypass -File plugin/build.ps1
```

Скрипт компилирует исходные тексты Java, собирает `lib/mcp-plugin.jar` и копирует манифест в каталог:
`%APPDATA%\VisualParadigm\plugins\com.mcp.visualparadigm\`.

---

## Инженерные модули и валидация

1. **State Store (`core/state.py`)**: Потокобезопасный реестр проекта, инкапсулирующий списки классификаторов, сущностей, акторов, состояний и связей.
2. **Rules Engine (`core/rules.py`)**: Архитектурный валидатор, предотвращающий формирование некорректных структур:
   * Проверка циклических зависимостей в наследовании (`A → B → C → A`).
   * Запрет объявления приватных полей и методов в интерфейсах.
   * Контроль целостности ERD: проверка наличия хотя бы одной колонки внешнего ключа (`is_fk=True`) в зависимой таблице при создании связей `1:N` и `N:1`.
   * Контроль правил UML 2.5 для связей прецедентов: отношения `Include` и `Extend` разрешены строго между сущностями `UseCase`.
3. **Visual Layout Engine (`exporters/layout_engine.py` и `exporters/xmi_builder.py`)**:
   * Расчет двумерных координат и габаритов фигур.
   * Вычисление геометрии соединительных линий и точек изломов.
   * Генерация метамоделей Visual Paradigm (`DBTable`, `DBForeignKey`, `State2`, `Transition2`).
   * Подавление паразитных подписей ролей связей для сохранения чистоты диаграмм.

---

## Тестирование

Комплекс тестов обеспечивает автономную проверку всех подсистем без необходимости запуска внешних приложений:

```bash
# 1. Проверка палитры типов данных ERD (ANSI SQL и PostgreSQL)
python test_erd_types.py

# 2. Сквозное тестирование генерации всех 4 видов диаграмм и валидация XMI 2.1
python test_all_diagrams.py

# 3. Проверка архитектурных правил валидатора и движка визуального лейаута
python test_rules_and_visual.py
```
