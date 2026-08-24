# Codequalität und Projektregeln

Die Qualitätsregeln wurden aus den gemeinsam festgelegten Lernunterlagen auf
Python übertragen. Sie gelten für produktiven Code in `application/`, `brain/`,
`config/`, `diagnostics/`, `memory/`, `tools/`, `vector/`, `voice/` und
`main.py`.

## Verbindliche Leitplanken

- Jedes Modul und jede Funktion besitzt eine klar erkennbare Verantwortung.
- Jede produktive Funktion und Methode erhält einen kurzen deutschen Docstring.
- Abhängigkeiten werden explizit zusammengesetzt und bleiben testbar.
- Wiederverwendete Grenzwerte stehen als benannte Konstanten oder Settings.
- Fehler werden an Systemgrenzen abgefangen, ohne Secrets offenzulegen.
- Lokale Sprach-, Memory- und Dokumentdaten werden nicht versioniert.
- Reservierte Module bleiben nur erhalten, wenn sie einen dokumentierten
  Architekturpfad darstellen.
- Jede Strukturänderung wird durch Regressionstests abgesichert.

## Funktionsgröße

Ungefähr 14 Zeilen bleiben die bevorzugte Zielgröße. Eine Funktion darf länger
sein, wenn die zusammengehörige Logik dadurch klarer bleibt. Der automatische
Qualitätstest verwendet 35 Zeilen als harte Rückfallgrenze. So erzwingt er keine
sinnlosen Kleinstfunktionen, verhindert aber erneut entstehende Monolithen.

## Deutsche Funktionsdokumentation

Docstrings erklären unmittelbar unter der jeweiligen `def`- oder `async def`-
Zeile knapp, was die Funktion in ihrer aktuellen Verantwortung tut. Das gilt
für öffentliche APIs, private Hilfsfunktionen, Konstruktoren, Properties und
Protokollmethoden im produktiven Code.

- Die Beschreibung beginnt mit einem aktiven deutschen Verb wie `Liest`,
  `Prüft`, `Erzeugt`, `Liefert`, `Speichert` oder `Verbindet`.
- Sie beschreibt beobachtbares Verhalten oder die konkrete interne Aufgabe,
  nicht bloß den Funktionsnamen.
- Parameter und Rückgabewerte werden nur erläutert, wenn ihre Bedeutung nicht
  bereits durch Typen und Namen eindeutig ist.
- Sicherheits-, Datenschutz- und Fehlergrenzen werden erwähnt, wenn sie für die
  Verantwortung der Funktion wesentlich sind.
- Kommentare innerhalb einer Funktion bleiben besonderen Entscheidungen und
  nicht offensichtlichen Gründen vorbehalten.
- Testmethoden benötigen keine zusätzlichen Docstrings, wenn ihr eindeutiger
  `test_...`-Name das geprüfte Verhalten bereits vollständig beschreibt.

Die deutschen Docstrings sind in VS Code über Signaturhilfe und
Hover-Informationen sichtbar. Sie ersetzen keine Architektur- oder
Sicherheitsdokumentation, sondern bilden die kleinste Erklärungsebene direkt am
Code.

## Modulgröße

Produktive Python-Module bleiben strikt unter 400 physischen Zeilen. Nähert
sich ein Modul dieser Grenze, werden zusammengehörige Verantwortungen in
benannte Fachmodule ausgelagert. Öffentliche Schnittstellen und beobachtbares
Verhalten bleiben dabei stabil; eine reine Aufteilung rechtfertigt keine
fachliche Verhaltensänderung.

## Automatische Kontrolle

`tests/test_code_quality.py` prüft dauerhaft:

- fehlende Verantwortungs-Docstrings an Produktivmodulen,
- fehlende deutsche Docstrings an allen produktiven synchronen und asynchronen
  Funktionen und Methoden,
- Funktionen oberhalb der harten Größenbegrenzung,
- Python-Produktivmodule mit 400 oder mehr Zeilen,
- versehentlich eingecheckte Git-Konfliktmarker,
- ignorierte private Laufzeitdaten,
- dokumentierte Verweise für zentrale Architekturmodule.

Die Dateisuche erfolgt rekursiv, damit dieselben Leitplanken auch für später
ergänzte Unterpakete gelten. Die Vollständigkeitssperre umfasst öffentliche und
private Funktionen, Methoden, Konstruktoren, Properties und Protokollmethoden.
Eine zusätzliche Prüfung blockiert die früher verwendeten englischen
Standardformulierungen. Damit fallen undokumentierte oder in den alten Stil
zurückfallende Funktionen unmittelbar in der Testsuite auf.

Der feste Sprachbefehl `Codequalität Status` verwendet dieselben dokumentierten
Grenzen für eine rein lokale, argumentlose Bestandsprüfung. Die Registry gibt
nur Modul-, Funktions- und Verstoßzähler weiter; Dateinamen, Funktionsnamen,
Pfade, Docstrings und Quelltexte bleiben innerhalb der Prüfung. Dieser Status
ersetzt keinen vollständigen Testlauf, sondern meldet ausschließlich die
statisch prüfbaren Leitplanken.

## Verbindlicher Regressionstest-Ablauf

Jeder neu gefundene Fehler wird vor seiner Korrektur reproduzierbar beschrieben und
durch einen möglichst kleinen automatisierten Test abgesichert. Der Test muss gegen
den noch fehlerhaften Stand nachweislich fehlschlagen. Erst danach wird die konkrete
Ursache behoben; eine bloße Umgehung des beobachteten Symptoms genügt nicht.

Der verbindliche Ablauf lautet:

> Fehler reproduzieren → Regressionstest → Ursache beheben → Einzeltest → vollständige Testsuite → Live- oder Vector-Test

Die fehlgeschlagene Vorher-Ausführung wird während der Bearbeitung kontrolliert und
im Arbeitsbefund festgehalten. Fehlerausgaben, Benutzerinhalte, Providerantworten,
Secrets und lokale Laufzeitdaten werden dafür nicht committed. Nach der Korrektur
muss zunächst genau der neue Regressionstest bestehen. Anschließend folgen die
vollständige Unit-Test-Suite, Python-Kompilierung, strikter MkDocs-Build und
`git diff --check`.

Reproduzierbare Tests bleiben vollständig von Live- und Hardwaretests getrennt.
Provider-Live-Tests werden nur bei fachlichem Bedarf gestartet und ersetzen keinen
Regressionstest. Physische Vector-Tests erfolgen ausschließlich nach ausdrücklicher
Bestätigung des Nutzers. Die ausführliche Teststrategie und die zugehörigen Befehle
stehen in [`docs/testing.md`](testing.md).

Die vollständige Abnahme erfolgt mit:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q .
.venv\Scripts\python.exe -m mkdocs build --strict
git diff --check
git status --short
```

Physische Robotertests bleiben zusätzlich erforderlich, wenn SDK-Verbindung,
Audioübertragung, Lautstärke oder das tatsächliche Sprachbild verändert werden.
