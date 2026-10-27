"""
Routing provider abstraction for Namma Payana.
Default: HaversineProvider (offline, always available).
Optional: OSRMProvider (configurable URL, falls back to Haversine on timeout/error).
"""
import math
import time
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from functools import lru_cache
import config

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


class RoutingProvider(ABC):
    @abstractmethod
    def route(
        self, lat1: float, lon1: float, lat2: float, lon2: float, transport: str = "bus"
    ) -> Tuple[float, float, str]:
        """Returns (road_km, hours, leg_basis_label)."""

    @abstractmethod
    def health_check(self) -> dict:
        """Returns a health status dict for the routing backend."""


class HaversineProvider(RoutingProvider):
    def route(self, lat1, lon1, lat2, lon2, transport="bus"):
        hav = haversine_km(lat1, lon1, lat2, lon2)
        road_km = round(hav * config.ROAD_DETOUR_FACTOR, 1)
        speed = config.AVG_SPEED_KMPH.get(transport, 40.0)
        hours = round(road_km / speed if speed > 0 else 0.0, 2)
        return road_km, hours, "estimated road network (haversine × detour factor)"

    def health_check(self) -> dict:
        return {"status": "ok", "provider": "HaversineProvider", "offline": True}


class OSRMProvider(RoutingProvider):
    """
    Calls a self-hosted OSRM server. Falls back to HaversineProvider on any error.
    Configure via OSRM_BASE_URL env var (e.g. http://router.project-osrm.org).
    """
    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._fallback = HaversineProvider()

    @lru_cache(maxsize=512)
    def _cached_route(self, lat1, lon1, lat2, lon2, transport):
        import urllib.request, json
        profile = "driving" if transport in ("car",) else "driving"
        url = f"{self.base_url}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=false"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            route = data["routes"][0]
            road_km = round(route["distance"] / 1000, 1)
            hours = round(route["duration"] / 3600, 2)
            return road_km, hours, "OSRM road network routing"
        except Exception as e:
            logger.warning("OSRM routing failed (%s), falling back to haversine", e)
            return None

    def route(self, lat1, lon1, lat2, lon2, transport="bus"):
        result = self._cached_route(lat1, lon1, lat2, lon2, transport)
        if result:
            return result
        road_km, hours, _ = self._fallback.route(lat1, lon1, lat2, lon2, transport)
        return road_km, hours, "estimated road network (haversine fallback)"

    def health_check(self) -> dict:
        """Returns provider status. Used by /api/health endpoint.
        Bypasses _cached_route (which swallows exceptions and returns None)
        so that OSRM unreachability is correctly surfaced as status: error.
        """
        import urllib.request, json as _json_health
        url = f"{self.base_url}/route/v1/driving/77.5946,12.9716;77.5946,12.9716?overview=false"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = _json_health.loads(resp.read())
            if data.get("routes") is None:
                return {"status": "error", "provider": "OSRMProvider",
                        "url": self.base_url, "error": "No routes in response"}
            return {"status": "ok", "provider": "OSRMProvider", "url": self.base_url}
        except Exception as e:
            return {"status": "error", "provider": "OSRMProvider",
                    "url": self.base_url, "error": str(e)}


def get_routing_provider() -> RoutingProvider:
    """Returns the configured provider. Defaults to HaversineProvider."""
    import os
    osrm_url = os.environ.get("OSRM_BASE_URL", "").strip()
    if osrm_url:
        return OSRMProvider(base_url=osrm_url)
    return HaversineProvider()


# Module-level singleton — instantiated once at startup
routing_provider: RoutingProvider = get_routing_provider()
