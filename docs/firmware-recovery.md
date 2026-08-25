# Firmware-Rückweg und Recovery-Grenzen

Diese Seite dokumentiert Karte 2 der kontrollierten Firmwarevorbereitung. Sie
prüft, wie der bestätigte Ausgangsstand `2.0.1.6076ep` nach einem späteren
Update erreichbar bleiben kann. Keine der beschriebenen Untersuchungen hat
einen Recovery-Modus, eine Datenlöschung oder einen Firmwaretransfer auf dem
physischen Vector ausgelöst.

Die übergeordnete Abbruch- und Freigaberegel steht unter
[`docs/firmware-safety.md`](firmware-safety.md). Bei widersprüchlichen Angaben
gilt stets die strengere Sicherheitsgrenze.

## Aktueller Sicherheitsbefund

Die vollständige `6076ep` ist lokal vorhanden und kryptografisch geprüft. Sie
ist dennoch **kein bestätigter normaler Downgrade-Pfad**: Die veröffentlichte
Produktions-Updateengine lehnt eine niedrigere Versionsnummer ausdrücklich ab.
Ein Rückweg von erfolgreich gestarteter `6085ep` zu `6076ep` darf deshalb erst
als verfügbar gelten, wenn der Recovery-Slot des konkreten Roboters ohne
Installation kontrolliert geprüft wurde.

Der Status für eine Installation von `6085ep` bleibt damit `No-Go`.

## Lokaler Recovery-Kandidat

Die Datei liegt ausschließlich in der lokalen Firmwarequarantäne:

```text
F:\VECTOR-OFFICE-AI-BACKUPS\firmware-quarantine\2.0.1.6076ep\vicos-2.0.1.6076ep.ota
```

WirePod verweist für seine Firmwarebereitstellung auf das Internet-Archive-Objekt
`vector-pod-firmware`. Der Spiegel ist keine offizielle DDL-Quelle. Die
Authentizität des Inhalts wird daher über das von Digital Dream Labs
veröffentlichte OTA-Schlüsselpaar und das signierte Manifest nachgewiesen,
nicht über den Namen des Downloadservers.

Quelle des Kandidaten:

```text
https://archive.org/download/vector-pod-firmware/vicos-2.0.1.6076ep.ota
```

## Vollständige Integritätsprüfung

| Nachweis | Ergebnis |
|---|---|
| Dateigröße | `179763200` Bytes |
| SHA-256 | `02f7014274be2891c8e6a235b638f9c291a1c1b63f25b42175118e7f4068a76a` |
| SHA-1 | `d4f1f7b55a31fdb0af35ff40cf7129d7bea1aca7` |
| MD5 | `a9efd3102f76ed0053779aa0713a42f3` |
| Archiv-SHA-1 und -MD5 | stimmen mit der öffentlichen Inventarliste überein |
| Manifestversion | `0.9.2` |
| Manifest-Zielversion | `2.0.1.6076ep` |
| Firmwaretyp | Produktion, `ankidev=0` |
| RSA-Signatur mit offiziellem OTA-Schlüssel | `Verified OK` |
| Boot-SHA-256 | `7ad785e5851e3187401fde285530279cec5a8a5756c2d3a216e084764fbd86fd` |
| Boot-Größe | `12869632` Bytes |
| System-SHA-256 | `edfb52f1df320499b8b5c958ec258bc7a7c942548bf75df2878a843bf241fc37` |
| System-Größe | `608743424` Bytes |
| Windows-Defender-Prüfung | keine Bedrohung gefunden |

Boot und System wurden im Datenstrom entschlüsselt und dekomprimiert. Ihre
SHA-256-Werte und Größen stimmen exakt mit dem gültig signierten Manifest
überein. SHA-1 und MD5 dienen hier nur dem Abgleich des Downloads mit der
Archivmetadatei; die kryptografische Freigabe beruht auf RSA und SHA-256.

Der offizielle DDL-Schlüssel und der aktuelle WireOS-Schlüssel sind
byteidentisch. Ihre lokale SHA-256 lautet:

```text
de3fd6a7c15cb30a8eedcb47cc16b13a9daeae2d06423f4a90d3a326bba7f537
```

## Nachgewiesenes A/B-Verhalten

Die veröffentlichte Vector-Updateengine liest den aktiven Slot aus
`androidboot.slot_suffix`:

| Aktiver Slot | Updateziel |
|---|---|
| `_a` | `b` |
| `_b` | `a` |
| Recovery `_f` | `a` |

Vor dem Schreiben markiert die Updateengine den Zielslot als nicht bootfähig
und überschreibt seinen Anfang zusätzlich mit Nullen. Erst wenn Manifest,
Firmwaretyp, dekomprimierte Abbilder, SHA-256-Werte, Größen und Datenträgersync
erfolgreich waren, wird der Zielslot mit `bootctl set_active` aktiviert.

Dieser Ablauf schützt den zuvor aktiven Slot während eines normalen Updates.
Aus dem veröffentlichten Python-Code allein folgt jedoch nicht sicher, wie
viele fehlgeschlagene Startversuche der konkrete Bootloader zulässt und ob er
danach selbstständig auf den bisherigen Slot zurückschaltet. Ein automatischer
Rollback wird deshalb nicht als bestätigte Eigenschaft vorausgesetzt.

## Downgrade-Sperre

`validate_new_os_version` lehnt eine niedrigere Zielversion mit Fehler `216`
ab. Die Umgebungsvariable `UPDATE_ENGINE_ALLOW_DOWNGRADE` umgeht diese Prüfung
nur auf einem Robot, dessen Kernelkommandozeile `anki.dev` enthält.

Die geprüften `6076ep`- und `6085ep`-Manifeste tragen beide `ankidev=0`. Für den
vorhandenen Produktions-Vector wird deshalb verbindlich angenommen:

- Ein normaler OTA-Aufruf von `6085ep` zurück auf `6076ep` ist gesperrt.
- Die lokale `6076ep` darf nicht als einfacher Downgrade beworben werden.
- Ein Rückweg benötigt den bestätigten bisherigen Slot oder den Recovery-Slot.
- Eine ungeprüfte Manipulation von Versionsnummer, Manifest oder Signatur ist
  ausgeschlossen.

## Noch unbekannter Slotzustand

Die vorhandenen lokalen Backups bestätigen die Firmware `2.0.1.6076ep`,
enthalten aber keine Kernelkommandozeile und damit keinen belastbaren aktiven
Slot. Der aktuelle Slot wird nicht geraten.

Die spätere rein lesende Prüfung soll:

1. Vector kontrolliert in den Recovery-Modus starten,
2. keine Benutzerdaten löschen,
3. keine OTA-Übertragung starten,
4. nur per Bluetooth koppeln,
5. die Diagnoseprotokolle herunterladen,
6. `androidboot.slot_suffix` und Recovery-Version lokal auswerten,
7. Vector anschließend ohne Update normal neu starten.

Dieser physische Test benötigt eine gesonderte Bestätigung des Nutzers. Bis zu
seinem erfolgreichen Abschluss bleibt der Recovery-Pfad unbestätigt.

## Recovery-Modus ohne Installation

Die offizielle DDL-Anleitung beschreibt den Recovery-Start auf der Ladestation
durch ungefähr 15 Sekunden gedrückt gehaltene Rückentaste. Das allein ist noch
keine Freigabe für unseren Robot. Vor der praktischen Prüfung werden die
sichtbaren Bildschirmzustände und der sichere Ausstieg noch einmal anhand der
konkret verwendeten Setupoberfläche abgeglichen.

Während der Prüfung sind insbesondere verboten:

- `CLEAR USER DATA` auswählen oder bestätigen,
- `ota-start` ausführen,
- eine Update- oder Aktivierungsschaltfläche bestätigen,
- den Robot während eines unerwarteten Schreibvorgangs ausschalten,
- unbekannte Konsolenbefehle ausprobieren.

Erscheint eine unerwartete Meldung, wird keine weitere Eingabe vorgenommen. Der
Bildschirmzustand wird dokumentiert und der Nutzer entscheidet über das weitere
Vorgehen.

## Lokal gesicherte Werkzeuge

Die unveränderte Quelle von `digital-dream-labs/vector-web-setup` ist als
Referenz auf Commit
`0637cf72b61bafdabde2f1a2b5776ec03daf405a` lokal gesichert:

```text
F:\VECTOR-OFFICE-AI-BACKUPS\firmware-quarantine\2.0.1.6076ep\recovery-tools\vector-web-setup
```

Ein Installationsversuch der historischen Node-Abhängigkeiten meldete bekannte
Sicherheitslücken, unter anderem in der festgelegten Axios-Version. Nach der
Firmware-Sicherheitsregel wurde dieser Pfad sofort abgebrochen. Erzeugte
Abhängigkeiten, Cache und Lockdatei wurden entfernt; die Git-Arbeitskopie ist
wieder unverändert.

Diese Quellkopie ist daher **nicht zur Ausführung freigegeben**. Sie dient nur
zur nachvollziehbaren Referenz. Vor einem lokalen Recoverywerkzeug muss entweder
eine gepflegte, geprüfte Oberfläche gefunden oder eine eng begrenzte lokale
Variante separat entwickelt und getestet werden. Sie darf ausschließlich auf
`127.0.0.1` lauschen und keine externe Firmware nachladen.

## Verfügbarkeit ohne externe Webseite

Bereits lokal und unabhängig vom späteren Zustand einer Webseite vorhanden
sind:

- die vollständig geprüfte `6076ep`-OTA,
- das signierte Manifest,
- die offiziellen, miteinander abgeglichenen OTA-Prüfschlüssel,
- die zur Offlineprüfung erforderlichen Metadaten,
- die unveränderte DDL-Werkzeugquelle als nicht ausführbare Referenz,
- das Backup von Projekt, WirePod und SDK-Konfiguration.

Noch nicht unabhängig und ausführbar abgesichert ist die lokale
Bluetooth-/Recovery-Oberfläche. Dieser offene Punkt verhindert die Freigabe
der Firmwareinstallation.

## Status der Karte 2

| Prüfschritt | Status |
|---|---|
| Verifizierte `6076ep` lokal sichern | bestanden |
| Manifest, Boot und System prüfen | bestanden |
| Normale Downgradefähigkeit prüfen | gesperrt, Fehler `216` erwartet |
| A/B-Updateprinzip nachvollziehen | bestanden |
| Aktiven Slot des konkreten Vector bestimmen | offen, physischer Lesetest |
| Recovery-Modus ohne Installation prüfen | offen, physischer Test |
| Sicheres lokales Setupwerkzeug bereitstellen | offen, historisches Werkzeug abgelehnt |
| Wiederherstellung vollständig freigeben | gesperrt |

Karte 2 ist erst abgeschlossen, wenn der aktive Slot und der sichere
Recovery-Start praktisch bestätigt sind und eine geprüfte lokale
Setupoberfläche ohne bekannte kritische Alt-Abhängigkeiten verfügbar ist. Bis
dahin bleibt Karte 7 und damit jede Installation von `6085ep` gesperrt.

## Quellen

- [Digital Dream Labs: Vector-Updateengine](https://github.com/digital-dream-labs/vector/blob/main/platform/update-engine/update-engine.py)
- [Digital Dream Labs: öffentlicher OTA-Schlüssel](https://github.com/digital-dream-labs/vector/blob/main/platform/config/etc/ota.pub)
- [Digital Dream Labs: Recovery- und Unlock-Checkliste](https://github.com/digital-dream-labs/oskr-owners-manual/blob/master/doc/unlock_checklist.md)
- [WirePod: Firmwareproxy zum Archiv](https://github.com/kercre123/wire-pod/blob/main/chipper/pkg/wirepod/config-ws/webserver.go)
- [Internet Archive: Firmwareinventar](https://archive.org/metadata/vector-pod-firmware)
