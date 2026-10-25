# MCP Visual Paradigm Java Plugin

Нативный Java-плагин для САПР Visual Paradigm 18.1+, обеспечивающий прямую двустороннюю интеграцию между AI/MCP-сервером и рабочей областью Visual Paradigm.

## Возможности

1. **Кнопка в главном меню Visual Paradigm**:
   - Пункт меню `MCP AI > Import MCP Diagram (XMI)...`
   - Открывает стандартный диалог выбора файла с фильтром по `.xmi` и `.xml` и мгновенно импортирует диаграмму в активный проект без ручного блуждания по длинным меню.

2. **Встроенный фоновый сервер Live Sync (`http://127.0.0.1:19842`)**:
   - Автоматически запускается вместе с Visual Paradigm.
   - Позволяет внешним процессам (нашему Python MCP-серверу, curl, скриптам) посылать команды на импорт XMI на лету.
   - Все операции с моделью и диаграммами безопасно делегируются в основной UI-поток Visual Paradigm (Swing Event Dispatch Thread).

## REST API Live Sync Сервера

### 1. Проверка состояния
* **Запрос**: `GET http://127.0.0.1:19842/health` (или `/status`)
* **Ответ**:
  ```json
  {"status":"ok","app":"Visual Paradigm","project":"MyProject"}
  ```

### 2. Мгновенный импорт XMI
* **Запрос**: `POST http://127.0.0.1:19842/import?file=C:\path\to\model.xmi`
* **Или через тело запроса**:
  ```bash
  curl -X POST http://127.0.0.1:19842/import -H "Content-Type: application/json" -d "{\"file\":\"E:\\\\mcp-visual-paradigm\\\\enterprise_system.xmi\"}"
  ```
* **Ответ**:
  ```json
  {"success":true,"message":"Import initiated for enterprise_system.xmi"}
  ```

## Сборка и установка

Плагин собирается с помощью PowerShell-скрипта `build.ps1`, компилирующего исходный код под целевую версию Java 11 (стандартная среда исполнения Visual Paradigm 18.1):

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Скрипт автоматически:
1. Компилирует классы против `openapi.jar` из каталога Visual Paradigm.
2. Собирает архив `lib/mcp-plugin.jar`.
3. Устанавливает плагин в каталог плагинов пользователя:
   `%APPDATA%\VisualParadigm\plugins\com.mcp.visualparadigm\`
4. Формирует дистрибутивный zip-архив `dist/mcp-visualparadigm-plugin.zip`.

## Активация плагина

После выполнения `build.ps1` достаточно запустить или перезапустить Visual Paradigm. В главном меню появится вкладка **MCP AI**, а в правом нижнем углу всплывет уведомление о запуске Live Sync Server.
