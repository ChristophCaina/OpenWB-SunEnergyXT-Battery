#!/usr/bin/env python3
"""SunEnergyXT 500 Series – openWB Gerätekonfiguration."""

from dataclasses import dataclass, field
from typing import List, Optional

from helpermodules.auto_str import auto_str
from modules.common.component_setup import ComponentSetup
from modules.devices.sunenergyxt.sunenergyxt import bat
from modules.devices.sunenergyxt.sunenergyxt.device import (
    SunEnergyXT,
    SunEnergyXTConfiguration,
)


def get_default_config() -> dict:
    return SunEnergyXT().__dict__


COMPONENT_TYPE_TO_MODULE = {
    "bat": bat,
}


def create_device(device_config: SunEnergyXT):
    """Factory: wird von openWB aufgerufen wenn das Gerät instanziiert wird."""

    def updater(component_config):
        component = COMPONENT_TYPE_TO_MODULE[
            component_config.type
        ].SunEnergyXTBat(
            component_config=component_config,
            device_config=device_config,
        )
        return component

    return updater
