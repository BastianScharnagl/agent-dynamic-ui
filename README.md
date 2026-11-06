# Agent Dynamic UI

Ein Demo-Projekt für einen KI-Agenten mit statisch im Backend definierten Datenbank- und UI-Tools. Bei Bedarf kann der Agent interaktive Formulare an ein React-Frontend streamen. Backend und Frontend kommunizieren über eine FastAPI-SSE-Schnittstelle.

## Inhalt

- [Überblick](#überblick)
- [Architektur](#architektur)
- [Voraussetzungen](#voraussetzungen)
- [Start mit Docker Compose](#start-mit-docker-compose)
- [Lokale Entwicklung](#lokale-entwicklung)
- [Konfiguration](#konfiguration)
- [API](#api)
- [Server-Sent Events](#server-sent-events)
- [Tools](#tools)
- [Dynamische Formulare](#dynamische-formulare)
- [Datenbank](#datenbank)
- [Fehlerbehebung](#fehlerbehebung)
- [Sicherheit und bekannte Einschränkungen](#sicherheit-und-bekannte-einschränkungen)

## Überblick

Der Agent kann:

- mit `render_custom_gui` Formulare erzeugen und als `UI_RENDER`-Event an das Frontend senden.
- Tabellen mit angegebenen Spalten anlegen und Einträge hinzufügen.
- Textantworten und Statusereignisse über eine Streaming-HTTP-Verbindung ausgeben.

Das Projekt ist ein Prototyp. Die verfügbaren Agentenfunktionen und Sicherheitsgrenzen sind im Abschnitt [Sicherheit und bekannte Einschränkungen](#sicherheit-und-bekannte-einschränkungen) beschrieben.

## Architektur

```text
Browser (React + Vite)
        |
        | POST /api/agent/stream
        | JSON-Anfrage / SSE-Antwort
        v
FastAPI (backend/main.py)
        |
        +-- DatabaseToolAgent (backend/agent/loop.py)
        |       +-- Google Gen AI
        |       +-- statische Funktionsdeklarationen
        |       +-- render_custom_gui
        |
        +-- psycopg2
                |
                v
           PostgreSQL
```

- **Frontend:** React, TypeScript und Vite. `DynamicForm` stellt die Formularfelder dar und validiert Eingaben.
- **Backend:** FastAPI nimmt Chat- und Formularanfragen entgegen. `StreamingResponse` liefert die Agentenereignisse als Server-Sent Events.
- **Agent:** `DatabaseToolAgent` verwaltet Chats pro Session-ID im Arbeitsspeicher und führt die statisch deklarierten Funktionsaufrufe aus.
- **Datenbank:** PostgreSQL speichert die Tabellen und Datensätze, die über die Datenbank-Tools angelegt werden.

## Voraussetzungen

Für den Docker-Start:

- Docker Engine oder Docker Desktop
- Docker Compose v2
- ein gültiger Google-Gen-AI-API-Key

Für die lokale Entwicklung ohne Docker zusätzlich:

- Python 3.12 oder neuer
- Node.js 20 oder neuer und npm
- eine erreichbare PostgreSQL-Instanz

## Start mit Docker Compose

1. Repository klonen und in das Projektverzeichnis wechseln.
2. Im Projektstamm eine lokale, nicht versionierte Datei `.env` mit dem API-Key anlegen:

   ```dotenv
   GEMINI_API_KEY=<Google-Gen-AI-API-Key>
   ```

   `.env` wird von Git ignoriert. Docker Compose liest die Datei zur Variablenauflösung ein und übergibt den Wert an den Backend-Container.
3. Container bauen und starten:

   ```powershell
   docker compose up --build
   ```

4. Die Dienste öffnen:

   - Frontend: <http://localhost:5173>
   - Backend: <http://localhost:8000>
   - FastAPI-Dokumentation: <http://localhost:8000/docs>
   - PostgreSQL: Port `5434` auf dem Host (im Compose-Netzwerk Port `5432`)

Das Backend initialisiert keine Tabellen und lädt keine Tooldefinitionen aus PostgreSQL. Die Datenbank-Tools können Tabellen auf Anforderung des Agenten anlegen.

Logs anzeigen:

```powershell
docker compose logs -f backend
```

Container stoppen:

```powershell
docker compose down
```

Die PostgreSQL-Daten liegen in einem Docker-Volume. Um die Container zu stoppen und **auch alle PostgreSQL-Daten zu löschen**, kann folgender Befehl verwendet werden:

```powershell
docker compose down --volumes
```

Vorsicht: Dadurch gehen die gespeicherten Daten unwiderruflich verloren.

## Lokale Entwicklung

### Backend

PowerShell-Beispiel:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Vor dem Start müssen `GEMINI_API_KEY` und `DATABASE_URL` in der Umgebung des Backend-Prozesses gesetzt sein. `DATABASE_URL` muss auf PostgreSQL zeigen; das Backend verwendet `psycopg2`.

Beispiel für die Prozessumgebung (Werte an die eigene PostgreSQL-Konfiguration anpassen):

```powershell
$env:GEMINI_API_KEY = "<Google-Gen-AI-API-Key>"
$env:DATABASE_URL = "postgresql://<user>:<password>@localhost:<port>/<database>"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

In einem zweiten Terminal:

```powershell
cd frontend
npm install
npm run dev
```

Das Frontend verwendet in `src/App.tsx` derzeit `http://localhost:8000/api/agent/stream` als Backend-Adresse.

Produktionsbuild:

```powershell
npm run build
```

## Konfiguration

| Variable | Verwendung |
|---|---|
| `GEMINI_API_KEY` | Zugangsschlüssel für den Google-Gen-AI-Client |
| `DATABASE_URL` | PostgreSQL-Verbindungszeichenfolge für `psycopg2` |

Beispiel für eine PostgreSQL-Verbindungszeichenfolge:

```text
postgresql://<user>:<password>@<host>:<port>/<database>
```

Innerhalb von Docker Compose muss der Hostname der PostgreSQL-Service sein; bei lokaler Ausführung muss der Hostname auf die vom Host erreichbare Datenbankadresse zeigen.

## API

### `POST /api/agent/stream`

Akzeptiert JSON und gibt `text/event-stream` zurück.

Neue Agentenanfrage:

```json
{
  "sessionId": "demo-session-1",
  "prompt": "Erstelle eine neue Tabelle users mit den Spalten id, name und email."
}
```

Antwort auf ein gerendertes Formular:

```json
{
  "sessionId": "demo-session-1",
  "toolResponse": {
    "toolName": "render_custom_gui",
    "callId": "<call-id-aus-dem-UI_RENDER-event>",
    "output": {
      "decision": "approved"
    }
  }
}
```

`prompt` und `toolResponse` sind optional, aber für eine Anfrage muss eines davon angegeben sein. Der `callId` wird vom Frontend mitgeschickt, im aktuellen Backend jedoch nicht zur Zuordnung oder Validierung verwendet.

## Server-Sent Events

Jedes Event besteht aus einem Eventnamen und einem JSON-Datenfeld:

```text
event: TEXT_MESSAGE
data: {"text":"Die Tabelle wurde erstellt."}
```

Das Backend kann folgende Ereignisse ausgeben:

| Ereignis | Zweck | Typische Daten |
|---|---|---|
| `RUN_STARTED` | Beginn einer Agentenantwort | `sessionId` |
| `STATUS_UPDATE` | Status während der Bearbeitung | `status` |
| `UI_RENDER` | Ein dynamisches Formular anzeigen | `callId`, `toolName`, `component` |
| `TEXT_MESSAGE` | Textausgabe des Agenten | `text` |
| `RUN_COMPLETED` | Ende des aktuellen Durchlaufs | `sessionId` |

Das Frontend liest den Stream, aktualisiert den Status, hängt Textnachrichten an und übergibt `component` aus einem `UI_RENDER`-Event an `DynamicForm`.

## Tools

Alle Tool-Schemas sind statisch im Backend definiert. Änderungen an Toolnamen, Beschreibungen, Parametern oder Implementierungen erfordern eine Codeänderung und einen Neustart des Backends. Einträge in einer etwaigen PostgreSQL-Tool-Registry werden nicht gelesen oder ausgeführt.

### Verfügbare Tools

- `select`, `insert`, `update`, `delete`: einfache Datenbankoperationen.
- `create_table`: Tabelle mit einer expliziten Liste von Spalten anlegen.
- `alter_table_add_column`: einer Tabelle eine Spalte hinzufügen.
- `calculate_vat`: Umsatzsteuer und Bruttobetrag berechnen.
- `render_custom_gui`: dynamisches Formular erzeugen.

Für `create_table` muss das Modell die Spalten als Array unter `columns` übergeben, zum Beispiel:

```json
{
  "table_name": "users",
  "columns": ["id", "name", "email"]
}
```

Die derzeitige Implementierung legt alle so angegebenen Spalten als `TEXT` an. Sie akzeptiert einfache SQL-Bezeichner und weist ungültige oder doppelte Spaltennamen zurück. Datentypen, Primärschlüssel und Constraints können über dieses Tool derzeit nicht konfiguriert werden.

Der Agent verarbeitet Funktionsaufrufe manuell. Zur Diagnose sind der empfangene Funktionsname und dessen Argumente maßgeblich.

## Dynamische Formulare

`render_custom_gui` liefert ein Formularobjekt mit:

- `form_id`, `headline`, optional `description`
- `elements`: Liste der Felder
- `submit_label`: Beschriftung der Absenden-Schaltfläche

Unterstützte Feldtypen:

| Typ | Darstellung |
|---|---|
| `text_input` | Einzeiliges Texteingabefeld |
| `number_input` | Zahleneingabe |
| `textarea` | Mehrzeiliges Texteingabefeld |
| `select` | Auswahlfeld mit `options` |
| `date_picker` | Datumsauswahl |
| `checkbox` | Kontrollkästchen |

Beispiel für ein Formularfeld:

```json
{
  "id": "email",
  "element": "text_input",
  "label": "E-Mail-Adresse",
  "placeholder": "name@example.com",
  "required": true,
  "validation": {
    "pattern": "^[^@]+@[^@]+\\.[^@]+$",
    "error_message": "Bitte eine gültige E-Mail-Adresse eingeben."
  }
}
```

Felder können `required`, `default_value`, Validierungsregeln (`min`, `max`, `pattern`) und bedingte Sichtbarkeit (`visibility`) enthalten. Ein Auswahlfeld muss `options` bereitstellen. Die UI-Eingaben werden als `toolResponse.output` an den Agenten zurückgesendet.

## Datenbank

Das Backend führt beim Start keine Schema- oder Tabelleninitialisierung durch. Die von den Datenbank-Tools verarbeiteten Tabellen liegen in der über `DATABASE_URL` konfigurierten PostgreSQL-Datenbank. `create_table` legt Tabellen explizit an.

Die laufenden Agent-Chats werden im Dictionary `DatabaseToolAgent.chats` im Backend-Prozess gehalten. Ein Prozessneustart löscht daher die aktiven Chatverläufe.

## Fehlerbehebung

### Backend meldet einen fehlenden API-Key

Prüfen, ob `GEMINI_API_KEY` tatsächlich in der Umgebung des Backend-Prozesses bzw. Containers gesetzt ist. Ein lokales `.env` wird nicht automatisch in jeden Prozess geladen; die Compose-Service-Umgebung muss korrekt eingerichtet sein.

### Datenbankverbindung schlägt fehl

Prüfen:

1. PostgreSQL läuft.
2. `DATABASE_URL` enthält Host, Port, Datenbank und Benutzer der gewünschten Instanz.
3. Bei Docker Compose wird der interne Service-Hostname verwendet; vom Host aus wird der veröffentlichte Host-Port verwendet.
4. Die Datenbank ist erreichbar, wenn ein Datenbank-Tool ausgeführt wird.

### Tabelle wird ohne Spalten erstellt oder das Tool schlägt fehl

Für `create_table` muss der Aufruf sowohl `table_name` als auch eine nichtleere `columns`-Liste enthalten. Im Backend-Log sollten der Funktionsname und die vollständigen Argumente nachvollziehbar sein. Bei `columns: []` wird die Tabelle abgewiesen.

### Keine Formularoberfläche sichtbar

Das Frontend zeigt ein Formular nur, wenn der Stream ein `UI_RENDER`-Event mit einem gültigen `component` enthält. Eine normale `TEXT_MESSAGE`-Antwort wird als Text und nicht als Formular angezeigt. Browser-Netzwerkansicht und Backend-Logs prüfen, ob `UI_RENDER` tatsächlich gesendet wurde.

## Sicherheit und bekannte Einschränkungen

- Dies ist ein Demo-/Prototyp und nicht für den öffentlichen Produktivbetrieb gehärtet.
- Die API hat aktuell keine Authentifizierung oder Autorisierung.
- CORS ist in der aktuellen Backend-Konfiguration für alle Origins freigegeben.
- SQL-Werkzeuge wie `select`, `insert`, `update`, `delete` und `alter_table_add_column` bauen SQL-Teile aus Funktionsargumenten zusammen. Sie dürfen nicht mit nicht vertrauenswürdigen Benutzern oder beliebigen Datenbankberechtigungen exponiert werden.
- `create_table` behandelt Tabellen- und Spaltennamen restriktiver und verwendet SQL-Identifier-Escaping; alle Spalten erhalten den Typ `TEXT`.
- API-Schlüssel und Passwörter dürfen nicht in Quellcode, README-Beispiele oder versionierte Compose-Dateien eingetragen werden. Für einen echten Einsatz gehören Geheimnisse in eine sichere Laufzeitkonfiguration.
- Der Chatstatus ist pro Backend-Prozess im Arbeitsspeicher gespeichert. Mehrere Worker, Neustarts und horizontale Skalierung sind damit nicht zuverlässig abgedeckt.
- Der aktuelle Agent verarbeitet Funktionsaufrufe manuell. Bei mehreren gleichzeitig angeforderten Funktionen kann der Codepfad nur den ersten Aufruf bearbeiten.
