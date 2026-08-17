# Verbindungsaufsicht und Hardware-Autonomie

`application/connection_supervisor.py` verwaltet die letzten Zustände lokaler
und später auch externer Dienste. Fehler verwenden die begrenzte Staffel
1, 2, 5, 10 und höchstens 30 Sekunden. Eine erfolgreiche Prüfung setzt den
Fehlerzähler sofort zurück. Der Supervisor prüft nur Erreichbarkeit und besitzt
keine Berechtigung für Bewegungen, Animationen oder andere Tools.

Beim Anwendungsstart werden WirePod und Vector-SDK derzeit bis zu drei Mal
geprüft. Ollamas bestehender lokaler Start- und Bereitschaftstest meldet seinen
Endzustand ebenfalls an den Supervisor. Strukturierte Ereignisse entstehen nur
bei einem Zustandswechsel und enthalten keine Adressen, Transkripte oder
Zugangsdaten.

## Grenze ohne lokalen Host

Ohne Verbindung zwischen Vector und einem laufenden lokalen Host kann die
Python-Anwendung weder Audio streamen noch SDK-Aktionen senden. Eine
Wiederherstellungsmeldung ist deshalb erst nach erneutem Verbindungsaufbau
möglich. Langfristig reduziert ein dauerhaft laufender WirePod-/Core-Host die
Abhängigkeit vom Entwicklungs-PC.

## Gesprochene Offline-Meldung

Fällt der Cloud-Primäranbieter erstmals aus und Ollama übernimmt erfolgreich,
spricht Vector einmalig lokal: „Ich kann das Kollektiv gerade nicht erreichen.
Ich arbeite vorübergehend lokal weiter.“ Weitere Fragen während desselben
Ausfalls wiederholen den Hinweis nicht. Nach einer erfolgreichen Cloud-Runde
darf ein späterer neuer Ausfall erneut angekündigt werden.

Sind Cloud und lokaler Fallback beide nicht verfügbar, behauptet Vector keinen
lokalen Weiterbetrieb. Er sagt stattdessen: „Ich kann das Kollektiv gerade nicht
erreichen. Offenbar besteht ein Verbindungsproblem.“ Die Meldung funktioniert
nur, solange der lokale TTS- und Audioweg zum Roboter erreichbar ist.

Beide Varianten wurden am physischen Vector nacheinander abgespielt und vom
Benutzer hinsichtlich Aussprache, Tempo und Betonung bestätigt.

## Optionale Firmware-Forschung

Echte Logik direkt auf Vector erfordert einen OSKR-/Dev-Unlock, den individuellen
SSH-Schlüssel, ein kompatibles signiertes OTA-Abbild, gesicherte Recovery-Daten
und eine getrennte Teststrategie. Vor jedem Firmwareversuch müssen aktueller
Firmwarestand, Robotervariante, QSN/ESN, SSH-Zugang und Rückkehrabbild eindeutig
verifiziert werden. Dieser Pfad ist nur dokumentiert; das Projekt verändert
derzeit keine Roboterfirmware.
