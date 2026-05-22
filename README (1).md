# SunEnergyXT 500 Series – openWB Modul

Dieses Modul integriert den **SunEnergyXT 500 / 500 PRO** Batteriespeicher
in openWB (software2 / core).

## Kommunikation

Das Gerät bietet eine **lokale HTTP-API** (kein Modbus, kein Cloud-Zwang):

| Endpunkt | Methode | Funktion |
|---|---|---|
| `http://<IP>/read` | GET | Alle Statusfelder als JSON |
| `http://<IP>/write?KEY=VALUE` | GET | Einzelne Parameter schreiben |

## Gelesene Felder

| Feld | Bedeutung | Einheit |
|---|---|---|
| `SC` | Battery State of Charge | % |
| `PB` | Batterieleistung (+ = Laden, − = Entladen) | W |
| `PP` | PV-Leistung | W |
| `GP` | Netzleistung (+ = Einspeisung, − = Bezug) | W |
| `IS` | Max. Inverterleistung | W |

## Aktive Steuerung (set_power_limit)

Das Modul unterstützt **aktive Speichersteuerung** durch openWB.

openWB schreibt dabei zwei Felder:
- `MM` – Self-consumption mode (0 = manuell, 1 = automatisch)
- `GS` – Grid Setpoint in Watt

| openWB-Anforderung | MM | GS | Effekt am Gerät |
|---|---|---|---|
| `None` – Automatik | 1 | 0 | Gerät regelt selbst am EVU-Punkt |
| `0` – Entladung stoppen | 0 | 0 | Speicher inaktiv |
| `> 0` – Entladen (N Watt) | 0 | +N | Gezielte Entladung für Hausverbrauch |
| `< 0` – Laden (N Watt) | 0 | −N | Laden aus Netz (z.B. Überschuss-Umleitung) |

### Steuer-Use-Cases in openWB

1. **Sofortladen (EV):** openWB ruft `set_power_limit(0)` → Speicher nicht entladen,
   Auto lädt aus PV/Netz
2. **Nur für Hausverbrauch entladen:** openWB ruft `set_power_limit(N)` mit aktuellem
   Hausverbrauch → Speicher deckt genau den Haus-Grundlast-Anteil
3. **PV-Überschuss-Laden:** openWB ruft `set_power_limit(None)` → Gerät regelt
   mit internem PID-Regler selbst

## Konfiguration in openWB

- **IP-Adresse**: IP des SunEnergyXT-Geräts im lokalen Netz
- **Port**: Standard `80`
- **Timeout**: HTTP-Timeout in Sekunden (Standard: 5)

## Hinweise

- Das Gerät erlaubt nur **eine gleichzeitige Verbindung** auf der HTTP-API.
  Wenn die HA-Integration parallel aktiv ist, empfiehlt sich der
  [SunEnergyXT Modbus-Proxy](https://github.com/ChristophCaina/modbus-proxy)
  oder eine Deaktivierung der HA-Integration während openWB aktiv ist.
- `discharge_to_grid` (GS > 0) ist technisch möglich, aber regulatorisch
  in Deutschland zu prüfen (§ 9 EEG, Einspeisemanagement).
