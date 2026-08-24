# Provider-Zuverlässigkeit und Architekturgrenzen

Dieses Dokument legt die verbindlichen Leitplanken für die schrittweise
Verbesserung externer und lokaler Dienste fest. Als Anregung dienen die
Prinzipien Provider-Isolation, begrenzte Laufzeiten, Fallbacks, Validierung und
Healthchecks. Die bestehende Vector-Architektur bleibt dabei maßgeblich; eine
Übernahme fremder Projektstrukturen oder Implementierungen ist nicht vorgesehen.

## Bestehende Architektur

`main.py` startet die Anwendung über `application/runtime.py`. Die Laufzeit
setzt Konfiguration, Diagnostik, Verbindungsaufsicht, Brain, Memory, Tool
Registry, Voice-Eingabe, Sprachausgabe und Vector-Steuerung explizit zusammen.
Die fachlichen Grenzen bleiben in ihren bestehenden Paketen erhalten:

| Pfad | Erhaltene Verantwortung |
| --- | --- |
| `application/` | Laufzeit, Gesprächssteuerung und Verbindungsaufsicht |
| `brain/` | Agent, Providerwahl, Kontext, Persönlichkeit und Reflexion |
| `memory/` | Kurzzeitkontext, bestätigtes Langzeitgedächtnis und Dokumentwissen |
| `tools/` | Registrierung, Berechtigung, Validierung und Audit von Werkzeugen |
| `voice/` | kontrollierte Übernahme lokaler WirePod-Transkripte |
| `vector/` | Vector-SDK, BehaviorControl, Aktionen und deutsche TTS-Ausgabe |
| `diagnostics/` | inhaltsfreie Zustands- und Abnahmediagnose |

Neue Zuverlässigkeitsfunktionen werden zunächst an diesen Grenzen ergänzt. Eine
Verschiebung funktionierender Module ist keine Voraussetzung für weitere
Provider.

## Verbindliche Leitprinzipien

### Provider-Isolation

Ein Fehler bei OpenAI, Ollama, ElevenLabs, WirePod, Embeddings oder einem
späteren externen Dienst darf nicht unkontrolliert andere Komponenten beenden.
Jede Systemgrenze fängt erwartbare Transport-, Timeout- und Antwortfehler ab und
liefert einen sicheren, fachlich begrenzten Zustand zurück. Provider erhalten
keine Berechtigung, Tools oder andere Provider selbstständig aufzurufen.

### Zeitlimits und Wiederholungen

Jeder Netzwerk- oder Hardwarezugriff besitzt ein konfigurierbares, validiertes
Zeitlimit. Wiederholungen bleiben begrenzt und sind nur für sichere,
idempotente Lesezugriffe zulässig. Verändernde oder gefährliche Aktionen werden
niemals automatisch wiederholt. Ein abgelaufenes Zeitlimit wird als eigener
Fehlerzustand behandelt und darf keine endlose Warteschleife auslösen.

Die Providerfristen werden zentral in `config/settings.py` validiert:

| Einstellung | Standard | Bereich | Verwendung |
| --- | ---: | ---: | --- |
| `WIREPOD_REQUEST_TIMEOUT` | 5 s | 1 bis 30 s | Status und lokale Transkriptabfrage |
| `OPENAI_REQUEST_TIMEOUT` | 120 s | 1 bis 600 s | OpenAI-Antwortgenerierung |
| `OLLAMA_REQUEST_TIMEOUT` | 120 s | 1 bis 600 s | Ollama-Chat und Modellvorladen |
| `ELEVENLABS_TIMEOUT` | 15 s | 1 bis 60 s | ElevenLabs-Spracherzeugung |
| `OLLAMA_EMBEDDING_TIMEOUT` | 60 s | 1 bis 600 s | lokale semantische Vektoren |

Die getrennten Standardwerte erhalten das bisherige Laufzeitverhalten. Der
WirePod-Timeout wird von Statusprüfung und Voice-Eingabe gemeinsam verwendet;
der Embedding-Timeout bleibt bewusst unabhängig von Ollama-Chat. Timeoutfehler
werden ohne Anfrageinhalte oder Transportdetails als eigener Fehlergrund
gemeldet.

### Fallbacks

Fallbacks erhalten eine feste, nachvollziehbare Reihenfolge. Der bestehende
Wechsel von OpenAI zu lokalem Ollama und von ElevenLabs zur lokalen deutschen
Stimme bleibt erhalten. Ein Fallback darf Datenschutzregeln, Toolrechte oder
die lokale Sperre von Dokumentwissen für Cloud-Provider nicht umgehen. Sind
alle zulässigen Wege ausgefallen, erhält der Benutzer eine kurze und ehrliche
Fehlermeldung statt einer erfundenen Antwort.

Ein fortlaufender Ausfall erzeugt nur beim ersten Übergang einen Offline-Hinweis.
Eine spätere Wiederherstellung wird als eigener Zustandswechsel erkannt und
höchstens einmal angekündigt. Gleichzeitige LLM- und TTS-Ausfälle werden vor
der Ausgabe zu genau einer priorisierten Meldung zusammengeführt. Die
Auslieferung eines Hinweises oder einer Antwort besitzt keinerlei Berechtigung,
einen bestätigten verändernden Tool-Aufruf erneut auszuführen.

### Healthchecks

Healthchecks liefern ausschließlich begrenzte Zustände wie `healthy`,
`degraded`, `unavailable` oder `disabled`. Sie dürfen keine kostenpflichtigen
Modellanfragen, Robot-Aktionen oder Datenänderungen auslösen. Diagnoseausgaben
enthalten weder Benutzerinhalte noch API-Schlüssel, Tokens, Dokumente,
Erinnerungen oder vollständige Providerantworten.

### Validierung vor Ausgabe

Externe Ergebnisse gelten zunächst als nicht vertrauenswürdige Daten. Leere
Antworten, interne Fehlermeldungen, ungültige Strukturen, fehlende Pflichtfelder
und erkennbare Widersprüche werden vor der TTS-Ausgabe abgefangen. Inhalte eines
Providers oder Dokuments dürfen niemals als verborgene System- oder
Toolanweisung ausgeführt werden.

`brain/response_quality.py` bildet dafür eine providerunabhängige Grenze. Das
Modul bewahrt die interne Herkunft einer akzeptierten Antwort, markiert sie als
externe Daten und gibt ausschließlich normalisierten Text weiter. Strukturierte
künftige Providerresultate benötigen exakt `text`, `source` und den Status
`success`; Fehlerstatus, zusätzliche Anweisungsfelder und abweichende Herkunft
werden verworfen. Bestehende reine Textprovider bleiben kompatibel und erhalten
ihre Herkunft über den lokalen Adapter.

Die Prüfung erkennt konservativ leere Werte, falsche Datentypen, interne
Fehlerseiten, deutliche Prompt-Injection-Muster und gleichzeitig gegensätzliche
Tatsachenbehauptungen. Der verworfene Inhalt wird weder in eine
Korrekturanweisung noch in eine Fehlermeldung übernommen. Die bestehende
Persönlichkeits- und Reflexionsprüfung läuft erst nach dieser Datenprüfung
unverändert weiter.

Kann eine Antwort nicht zuverlässig freigegeben werden, spricht Vector nur:

> Ich konnte diese Information gerade nicht zuverlässig abrufen.

`application/response_delivery.py` und die Ausdrucksausgabe prüfen zusätzlich
direkt an ihren TTS-Grenzen. Damit können auch ungültige direkte Ausgabetexte
nicht versehentlich an eine lokale oder externe Stimme gelangen.

## Sicherheitsgrenze der Tool Registry

`tools/registry.py` bleibt die einzige vorgesehene Ausführungsgrenze für
kontrollierte Werkzeuge. Registrierung, Parameterschema, Berechtigungsstufe,
Bestätigung, Ergebnisnormalisierung, Redaktion und Audit dürfen durch neue
Provider nicht umgangen werden. Nicht registrierte Tools bleiben blockiert;
gefährliche und verändernde Aktionen benötigen weiterhin die dafür festgelegte
Freigabe.

## Bewusst ausgeschlossene Umbauten

Für die aktuelle Entwicklungsphase gelten folgende Entscheidungen:

- Es erfolgt kein vollständiger Umzug in einen neuen `app/`-Projektbaum.
- Es erfolgt keine vollständige Migration der Anwendung auf `asyncio`.
- Bestehende Memory-, Voice-, Vector-, TTS- und Tool-Pfade werden nicht ohne
  konkreten fachlichen Bedarf ersetzt.
- Ein allgemeiner Provider Manager wird nicht vorsorglich eingeführt.
- FastAPI ist eine spätere Option für einen klar abgegrenzten lokalen API-Fall.
- Docker ist eine spätere Option für hardwareunabhängige Komponenten oder einen
  Homeserver; Windows-TTS und Vector-Hardware werden derzeit nicht verlagert.
- FareWeave bleibt eine mögliche externe, standardmäßig deaktivierte
  Reisedatenquelle und wird weder kopiert noch fest mit dem Core gekoppelt.

Diese Entscheidungen dürfen nur durch eine neue, dokumentierte Karte mit
Risikoanalyse, Rückbauweg und eigener Abnahme geändert werden.

## Regeln für folgende Provider-Karten

Jede weitere Karte zur Provider-Zuverlässigkeit muss:

1. bestehendes Verhalten und öffentliche Schnittstellen erhalten,
2. vor Änderungen den Git-Status prüfen,
3. genau eine klar abgegrenzte Verantwortung bearbeiten,
4. Timeouts und Fehlerzustände deterministisch testen,
5. Datenschutz und Toolberechtigungen unverändert durchsetzen,
6. keine Secrets oder privaten Inhalte protokollieren,
7. einen sicheren Rückfall oder eine verständliche Fehlermeldung vorsehen,
8. Dokumentation und Regressionstests gemeinsam aktualisieren,
9. die vollständige lokale Qualitätsabnahme ausführen und
10. physische Tests nur bei tatsächlicher Änderung des Robot-Verhaltens
    verlangen.

## Qualitätsstandard

Für neuen produktiven Python-Code gelten weiterhin `docs/quality.md` und damit
deutsche Funktions- und Methodendocstrings, höchstens 35 Funktionszeilen sowie
weniger als 400 physische Zeilen je Produktivmodul. Kleine Adapter und explizite
Komposition werden gegenüber verdeckter automatischer Registrierung bevorzugt.
Die Abnahme umfasst Unit-Tests, Python-Kompilierung, den strikten MkDocs-Build,
`git diff --check` und die abschließende Kontrolle des Git-Status.
