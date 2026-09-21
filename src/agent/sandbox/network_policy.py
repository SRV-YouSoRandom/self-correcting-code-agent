from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class NetworkMode(str, Enum):
    NONE = "none"
    BRIDGE = "bridge"


class NetworkPolicy(BaseModel):
    mode: NetworkMode = NetworkMode.NONE
    allowed_domains: list[str] = []

    def docker_network_mode(self) -> str:
        return self.mode.value


def policy_from_contract(requires_network: bool, allowed_domains: list[str]) -> NetworkPolicy:
    if not requires_network:
        return NetworkPolicy(mode=NetworkMode.NONE, allowed_domains=[])
    return NetworkPolicy(mode=NetworkMode.BRIDGE, allowed_domains=allowed_domains)
