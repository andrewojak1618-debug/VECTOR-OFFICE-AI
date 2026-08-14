# Codequalität und Projektregeln

Die Qualitätsregeln wurden aus den gemeinsam festgelegten Lernunterlagen auf
Python übertragen. Sie gelten für produktiven Code in `application/`, `brain/`,
`config/`, `diagnostics/`, `memory/`, `tools/`, `vector/`, `voice/` und
`main.py`.

## Verbindliche Leitplanken

- Jedes Modul und jede Funktion besitzt eine klar erkennbare Verantwortung.
- Öffentliche Klassen und Funktionen erhalten kurze englische Docstrings.
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

## Modulgröße

Produktive Python-Module bleiben strikt unter 400 physischen Zeilen. Nähert
sich ein Modul dieser Grenze, werden zusammengehörige Verantwortungen in
benannte Fachmodule ausgelagert. Öffentliche Schnittstellen und beobachtbares
Verhalten bleiben dabei stabil; eine reine Aufteilung rechtfertigt keine
fachliche Verhaltensänderung.

## Automatische Kontrolle

`tests/test_code_quality.py` prüft:

- fehlende Verantwortungs-Docstrings an Produktivmodulen,
- fehlende Docstrings an öffentlichen synchronen und asynchronen Python-APIs,
- Funktionen oberhalb der harten Größenbegrenzung,
- Python-Produktivmodule mit 400 oder mehr Zeilen,
- versehentlich eingecheckte Git-Konfliktmarker,
- ignorierte private Laufzeitdaten,
- dokumentierte Verweise für zentrale Architekturmodule.

Die Dateisuche erfolgt rekursiv, damit dieselben Leitplanken auch für später
ergänzte Unterpakete gelten.

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
