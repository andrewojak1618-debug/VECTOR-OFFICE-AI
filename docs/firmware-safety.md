# Firmware-Sicherheit und kontrollierte Freigabe

Diese Richtlinie regelt alle Arbeiten an der Firmware des physischen Vector.
Sie erlaubt noch keine Installation. Das Projekt bleibt auf dem bestätigten
Ausgangsstand, bis jede nachfolgende Sicherheitskarte abgeschlossen und der
konkrete Installationsschritt ausdrücklich freigegeben wurde.

## Geltungsbereich und Ausgangszustand

Der am 25. August 2026 ausgelesene Ausgangsstand lautet:

| Merkmal | Bestätigter Wert |
|---|---|
| Installierte Firmware | `2.0.1.6076ep` |
| Geprüfte Zielfirmware | `2.0.1.6085ep` |
| WirePod | `v1.2.18` |
| Projektzweig | `main` |
| Vorbereitendes Backup | `F:\VECTOR-OFFICE-AI-BACKUPS\2026-08-25-pre-firmware-6076ep` |
| Firmwarequarantäne | `F:\VECTOR-OFFICE-AI-BACKUPS\firmware-quarantine\2.0.1.6085ep` |

Das Backup enthält vertrauliche Konfiguration und darf weder veröffentlicht
noch in Git aufgenommen werden. Eine Sicherung der Projekt- und
WirePod-Konfiguration ersetzt keine rückspielbare Firmware.

## Verbindliche Grundregel

> Bei jeder unbekannten, negativen oder möglicherweise systemschädigenden
> Abweichung gilt `No-Go`. Vor Beginn des Firmware-Schreibvorgangs wird der
> Ablauf abgebrochen und der bestätigte Betriebszustand wiederhergestellt.
> Nach Beginn des Schreibvorgangs wird Vector nicht ausgeschaltet; stattdessen
> wird der vorgesehene A/B- oder Recovery-Pfad kontrolliert beendet.

Sicherheit hat Vorrang vor Fortschritt. Warnungen werden nicht übergangen,
Fehler nicht durch spontane Wiederholungen verdeckt und fehlende Nachweise
nicht durch Annahmen ersetzt.

## Phasen und erlaubte Reaktion

| Phase | Veränderung an Vector | Reaktion auf eine Abweichung |
|---|---|---|
| Lokale Vorprüfung | keine | Sofort abbrechen, Ursache dokumentieren und keine Verbindung zum Updater herstellen. |
| Verbindungsaufbau und Auswahl | noch keine bestätigte Installation | Abbrechen, Updateoberfläche schließen und zuvor gestoppte Projektdienste wiederherstellen. |
| Update von Vector angenommen | inaktiver Slot kann bereits verändert werden | Nicht ausschalten, nicht von der Ladestation nehmen und den Updateprozess kontrolliert bis Erfolg oder eigenständigem Fehlerzustand laufen lassen. |
| Neustart und Nachprüfung | Zielslot kann aktiv sein | Version und Grundfunktionen prüfen; bei Fehlern keine Wiederholung starten, sondern den vorbereiteten Recovery-Pfad verwenden. |

Die Grenze zur möglichen Veränderung beginnt mit der endgültigen Bestätigung
des Updates in der Updateoberfläche. Genau dieser Schritt benötigt unmittelbar
zuvor eine ausdrückliche Freigabe des Nutzers.

## Harte Abbruchkriterien

Vor der endgültigen Installationsfreigabe wird der Ablauf beendet, sobald
mindestens eines dieser Merkmale vorliegt:

- Signatur, SHA-256-Prüfsumme, Dateigröße oder Manifest stimmen nicht überein.
- Quelle, Dateiname, Zielversion oder Seriennummer weichen vom Prüfbericht ab.
- Die Firmware meldet einen unerwarteten Entwicklungs- oder Gerätetyp.
- Der Rückweg zur Ausgangsfirmware oder ein gleichwertiger Recovery-Weg ist
  nicht nachvollziehbar verfügbar.
- Vector ist nicht ausreichend geladen oder steht nicht sicher auf der
  Ladestation.
- WLAN, Bluetooth, Stromversorgung oder Laptopbetrieb sind instabil.
- Windows plant einen Neustart oder wechselt möglicherweise in den
  Energiesparmodus.
- WirePod, SDK oder Updateoberfläche zeigen einen unbekannten Fehler.
- Eine benötigte Sicherung fehlt oder ihre Integritätsprüfung schlägt fehl.
- Vector zeigt bereits vor dem Update ein ungeklärtes Fehlverhalten.
- Ein Arbeitsschritt verlangt eine ungeplante Firmware, Quelle oder
  Systemänderung.

Ein abgebrochener Versuch wird nicht automatisch neu gestartet. Zuerst werden
Phase, sichtbarer Fehlercode und sichere technische Metadaten dokumentiert.
Benutzerinhalte, Zugangsdaten, Zertifikate und API-Schlüssel bleiben aus
Berichten und Versionsverwaltung ausgeschlossen.

## Verhalten innerhalb der Schreibphase

Nach der endgültigen Installationsfreigabe ist ein erzwungener Abbruch keine
sichere Rückkehrstrategie. Während Vector das Update verarbeitet, gelten daher
zusätzlich diese Regeln:

- Vector bleibt auf der Ladestation und wird nicht bewegt.
- Laptop, Router und WirePod werden nicht absichtlich neu gestartet.
- WLAN und Bluetooth werden nicht manuell getrennt.
- Tasten werden nur betätigt, wenn der geprüfte Ablauf dies ausdrücklich
  verlangt.
- Ein scheinbarer Stillstand führt nicht zu einem harten Ausschalten.
- Ein zweiter Installationsversuch beginnt erst nach Fehleranalyse und neuer
  Freigabe.

Der veröffentlichte Vector-Updateprozess schreibt in einen inaktiven A/B-Slot
und aktiviert ihn erst nach erfolgreichen internen Prüfungen. Diese
Schutzfunktion verringert das Risiko, ersetzt aber weder Recovery-Nachweis noch
stabile Stromversorgung.

## Freigabesperren

Die Installation von `2.0.1.6085ep` bleibt gesperrt, bis mindestens folgende
Nachweise vollständig vorliegen:

1. [Karte 2](firmware-recovery.md) bestätigt einen realistischen Rückweg zu
   `2.0.1.6076ep` oder einen gleichwertigen Recovery-Weg.
2. Projekt-, WirePod-, SDK- und Zertifikatsbackup sind vorhanden und geprüft.
3. Die Quarantänedatei besteht unmittelbar vor dem Einsatz erneut alle
   Signatur-, Hash- und Größenprüfungen.
4. Stromversorgung, Ladezustand, WLAN, Bluetooth und Windows-Betrieb sind
   stabil.
5. Die Updateoberfläche zeigt die erwartete Seriennummer und Zielversion.
6. Der Nutzer bestätigt den letzten verändernden Schritt ausdrücklich.

Kein Skript und kein automatischer Diagnosebefehl darf diese Sperren umgehen
oder eine Firmwareinstallation selbstständig starten.

## Nachweis der geprüften Zielfirmware

Die Datei `2.0.1.6085ep.ota` wurde ausschließlich in der Firmwarequarantäne
untersucht und noch nicht an Vector übertragen. Der Download stammt von einem
Community-Spiegel; seine technische Authentizität wird deshalb nicht aus dem
Servernamen, sondern aus der Signaturkette abgeleitet.

| Nachweis | Ergebnis |
|---|---|
| OTA-Größe | `201287680` Bytes |
| OTA-SHA-256 | `fd423f1bc28e35a382cc3377d5f5460530f9f7ed7a7317a1d40d8fa8a2cfe59a` |
| Manifestversion | `0.9.2` |
| Manifest-Zielversion | `2.0.1.6085ep` |
| Firmwaretyp | Produktion, `ankidev=0` |
| RSA-Signatur mit offiziellem OTA-Schlüssel | `Verified OK` |
| Boot-SHA-256 | `1df124291b788d2636d8ebf8e46262f72127e4a009c2f38de7a86e5e77187a50` |
| Boot-Größe | `13000704` Bytes |
| System-SHA-256 | `ba9c65dad8d72a1da7905e2ba7686fa716f774d445741ca4fd238340d281e8cd` |
| System-Größe | `608743424` Bytes |
| Windows-Defender-Prüfung | keine Bedrohung gefunden |

Boot- und Systemwerte wurden nach Entschlüsselung und Dekomprimierung gegen das
gültig signierte Manifest geprüft. Die vollständige OTA-Prüfsumme ist unser
lokaler Fingerabdruck; sie ist kein separat veröffentlichter Herstellerwert.

## Wiederherstellung des Betriebszustands

Wird vor der Installationsfreigabe abgebrochen, umfasst die Rückkehr zum
Ausgangszustand nur zuvor tatsächlich veränderte Betriebsbestandteile:

1. Updateoberfläche ohne Installationsbestätigung schließen.
2. Temporär gestoppte Projekt- und WirePod-Dienste kontrolliert starten.
3. Vector-Verbindung und weiterhin installierte Version `2.0.1.6076ep` prüfen.
4. Keine Quarantäne- oder Sicherungsdatei löschen oder überschreiben.
5. Ursache dokumentieren und die betroffene Karte offen lassen.

Nach Beginn der Firmwareinstallation ist eine Rückkehr erst über den in Karte 2
bestätigten A/B- oder Recovery-Ablauf zulässig. Ein Zurückkopieren des
Projektbackups verändert die Firmware nicht.

## Freigabeprotokoll

Jede spätere Durchführung hält mindestens diese Angaben fest:

- Datum und verantwortliche Person,
- Ausgangs- und Zielversion,
- SHA-256 der eingesetzten OTA,
- Ergebnis aller Vorprüfungen,
- Zeitpunkt der ausdrücklichen Freigabe,
- erreichte Updatephase,
- sichere Fehlercodes oder Erfolgsmeldung,
- Ergebnis der Firmware-, WirePod- und Projektabnahme.

Ein fehlender Protokollpunkt führt vor der Installation zu `No-Go`. Das
Protokoll enthält keine Secrets, Gesprächsinhalte, Providerantworten oder
Dokumentdaten.

## Abschlusskriterium für Karte 1

Karte 1 ist abgeschlossen, sobald diese Richtlinie über die Projektdokumentation
auffindbar ist und die Installation technisch wie organisatorisch bis zum
Abschluss von Karte 2 gesperrt bleibt. Diese Dokumentation verändert weder die
Firmware noch das Laufzeitverhalten von Vector Office AI.
