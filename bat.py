#!/usr/bin/env python3
"""SunEnergyXT 500 Series – openWB Batteriespeicher-Modul.

Kommunikation:
  - Lesen:    GET  http://<ip>/read   → JSON mit allen Statusfeldern
  - Schreiben: GET  http://<ip>/write?<key>=<value>

Relevante Felder (aus der SunEnergyXT lokalen HTTP-API):
  SC   – Battery SoC in %  (float, z.B. 82.5)
  PB   – Battery power in W, positiv = Laden, negativ = Entladen
  IS   – Max. Inverter-/Speicherleistung in W (Gerätekonfiguration)
  MM   – Self-consumption mode: 0 = aus, 1 = aktiv
  GS   – Grid-Setpoint in W:
           0        = Gerät regelt selbst (MM=1 Selbstverbrauch)
          <0        = Ladeleistung von Netz erzwingen (negativ)
          >0        = Entladeleistung ins Netz erzwingen (positiv, regulatorisch zu prüfen!)
  GP   – Aktuelle Netzleistung in W (positiv = Einspeisung, negativ = Bezug)
  PP   – PV-Leistung in W

openWB Steuerlogik (set_power_limit):
  power_limit = None  → Automatik, GS auf 0 setzen, MM=1 (Selbstverbrauch aktiv)
  power_limit = 0     → Entladung stoppen, GS=0 + MM=0 (kein Selbstverbrauch)
  power_limit > 0     → Entladen mit Zielvorgabe: GS = +power_limit
  power_limit < 0     → Laden mit Zielvorgabe:    GS = -abs(power_limit)

Vorzeichenkonvention openWB (BatState.power):
  positiv = Speicher lädt   (Erzeugung > Verbrauch)
  negativ = Speicher entlädt (Verbrauch > Erzeugung)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

from modules.common.component_state import BatState
from modules.common.component_type import ComponentDescriptor
from modules.common.fault_state import ComponentInfo, FaultState
from modules.common.simcount import SimCounter
from modules.common.store import get_bat_value_store
from modules.devices.sunenergyxt.sunenergyxt.device import SunEnergyXT

log = logging.getLogger(__name__)


@dataclass
class SunEnergyXTBatSetup:
    name: str = "SunEnergyXT Speicher"
    type: str = "bat"
    id: int = 0


class SunEnergyXTBat:
    def __init__(
        self,
        component_config: SunEnergyXTBatSetup,
        device_config: SunEnergyXT,
    ) -> None:
        self.component_config = component_config
        self.device_config = device_config
        self.store = get_bat_value_store(component_config.id)
        self.fault_state = FaultState(
            ComponentInfo.from_component_config(component_config)
        )
        self.sim_counter = SimCounter(
            self.device_config.id,
            self.component_config.id,
            prefix="speicher",
        )
        self._base_url = (
            f"http://{device_config.configuration.ip_address}"
            f":{device_config.configuration.port}"
        )
        self._timeout = device_config.configuration.timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read(self) -> dict:
        """Liest den aktuellen Gerätestatus via GET /read."""
        url = f"{self._base_url}/read"
        resp = requests.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def _write(self, **kwargs) -> None:
        """Schreibt einen oder mehrere Werte via GET /write?key=value."""
        url = f"{self._base_url}/write"
        resp = requests.get(url, params=kwargs, timeout=self._timeout)
        resp.raise_for_status()
        log.debug("SunEnergyXT write %s → %s", kwargs, resp.text)

    # ------------------------------------------------------------------
    # openWB interface
    # ------------------------------------------------------------------

    def update(self) -> None:
        """Liest Batteriestatus und schreibt ihn in den openWB-Store."""
        data = self._read()

        # SoC (float → int, openWB erwartet int)
        soc = int(float(data.get("SC", 0)))

        # Batterieleistung:
        #   PB positiv = Laden, negativ = Entladen (Gerät-Konvention)
        #   openWB erwartet dasselbe Vorzeichen → direkt übernehmen
        power = float(data.get("PB", 0))

        # Simulierte Zählerstände (kumulierte Import/Export-Energie)
        imported, exported = self.sim_counter.sim_count(power)

        bat_state = BatState(
            power=power,
            soc=soc,
            imported=imported,
            exported=exported,
        )
        self.store.set(bat_state)

        log.debug(
            "SunEnergyXT update: SoC=%d%%, PB=%.0fW, GP=%.0fW, PP=%.0fW",
            soc,
            power,
            float(data.get("GP", 0)),
            float(data.get("PP", 0)),
        )

    def set_power_limit(self, power_limit: Optional[int]) -> None:
        """Aktive Speichersteuerung durch openWB.

        openWB ruft diese Methode auf, wenn es den Speicher gezielt
        steuern möchte (z.B. Entladung bei Fahrzeugladung sperren).

        power_limit:
          None → Automatik (Selbstverbrauch): MM=1, GS=0
          0    → Entladung stoppen:           MM=0, GS=0
          >0   → Entladen mit power_limit W:  GS=+power_limit
          <0   → Laden mit |power_limit| W:   GS=-|power_limit|
        """
        max_power = self.device_config.configuration  # für IS-Limit nutzbar

        if power_limit is None:
            # Selbstverbrauch-Modus: Gerät regelt eigenständig am EVU-Punkt
            log.debug("SunEnergyXT: Automatik-Modus (MM=1, GS=0)")
            self._write(MM=1, GS=0)

        elif power_limit == 0:
            # Entladung vollständig stoppen (z.B. während Sofortladen)
            log.debug("SunEnergyXT: Entladung gesperrt (MM=0, GS=0)")
            self._write(MM=0, GS=0)

        elif power_limit > 0:
            # Entladen mit Zielvorgabe (z.B. für Hausverbrauch)
            # Leistung auf Geräte-Maximum begrenzen
            p = int(min(power_limit, 9999))  # Sicherheitsgrenze
            log.debug("SunEnergyXT: Entladen mit %dW (GS=%d)", p, p)
            self._write(MM=0, GS=p)

        else:
            # Laden mit Zielvorgabe (negativer Wert = Netzbezug erzwingen)
            p = int(min(abs(power_limit), 9999))
            log.debug("SunEnergyXT: Laden mit %dW (GS=-%d)", p, p)
            self._write(MM=0, GS=-p)

    def power_limit_controllable(self) -> bool:
        """Gibt an, dass dieser Speicher aktiv gesteuert werden kann."""
        return True


component_descriptor = ComponentDescriptor(
    configuration_factory=SunEnergyXTBatSetup
)
