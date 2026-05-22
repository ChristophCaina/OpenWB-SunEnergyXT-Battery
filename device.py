#!/usr/bin/env python3
"""SunEnergyXT 500 Series – openWB device module."""

from dataclasses import dataclass, field
from typing import Optional

from modules.common.component_setup import ComponentSetup


@dataclass
class SunEnergyXTConfiguration:
    ip_address: str = "192.168.1.100"
    port: int = 80
    # Poll interval in seconds (openWB controls the actual loop)
    timeout: int = 5


@dataclass
class SunEnergyXT:
    name: str = "SunEnergyXT 500 Series"
    type: str = "sunenergyxt"
    id: int = 0
    configuration: SunEnergyXTConfiguration = field(
        default_factory=SunEnergyXTConfiguration
    )
