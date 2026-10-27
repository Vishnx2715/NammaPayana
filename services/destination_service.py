"""
Destination data service for Namma Payana.
Loads, validates, indexes, and queries verified Karnataka destination records.
"""
import json
import os
import logging
from typing import List, Dict, Optional, Any
from services.validation import DestinationRecord
import config

logger = logging.getLogger(__name__)

class DestinationService:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(config.DATA_DIR, "destinations.json")
        self._destinations: Dict[str, Dict[str, Any]] = {}
        self._last_mtime: float = 0.0
        self.load_and_validate()

    def _check_reload(self) -> None:
        try:
            mtime = os.path.getmtime(self.data_path)
            if mtime > self._last_mtime:
                self.load_and_validate()
        except Exception:
            pass

    def load_and_validate(self) -> None:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Destinations dataset not found at {self.data_path}")

        self._last_mtime = os.path.getmtime(self.data_path)
        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError("destinations.json root must be a JSON array of records")

        if len(raw_data) < 20:
            raise ValueError(f"Dataset must contain at least 20 verified destinations, found {len(raw_data)}")

        validated: Dict[str, Dict[str, Any]] = {}
        seen_ids = set()

        for idx, item in enumerate(raw_data):
            try:
                record = DestinationRecord(**item)
            except Exception as e:
                logger.error(f"Startup validation failed on destination #{idx} ({item.get('id', 'unknown')}): {e}")
                raise ValueError(f"Invalid destination record in dataset: {e}") from e

            if record.id in seen_ids:
                raise ValueError(f"Duplicate destination ID found: {record.id}")

            seen_ids.add(record.id)
            validated[record.id] = record.model_dump()

        self._destinations = validated
        logger.info(f"Loaded and verified {len(self._destinations)} Karnataka destinations successfully.")

    def get_all(
        self,
        region: Optional[str] = None,
        category: Optional[str] = None,
        max_hours: Optional[float] = None,
        max_fee: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        self._check_reload()
        results = list(self._destinations.values())

        if region:
            region_clean = region.strip().lower()
            results = [d for d in results if d.get("region", "").lower() == region_clean]

        if category:
            cat_clean = category.strip().lower()
            results = [
                d for d in results
                if any(c.lower() == cat_clean for c in d.get("categories", []))
            ]

        if max_hours is not None:
            results = [d for d in results if d.get("visit_hours", 0) <= max_hours]

        if max_fee is not None:
            results = [
                d for d in results
                if (d.get("entry_fee_inr", {}).get("value") or 0) <= max_fee
            ]

        return results

    def get_by_id(self, dest_id: str) -> Optional[Dict[str, Any]]:
        self._check_reload()
        return self._destinations.get(dest_id)

    def destination_exists(self, dest_id: str) -> bool:
        self._check_reload()
        return dest_id in self._destinations

    def get_all_ids(self) -> List[str]:
        self._check_reload()
        return list(self._destinations.keys())

    def validate_ids(self, ids: List[str]) -> bool:
        return all(did in self._destinations for did in ids)

# Global singleton instance
destination_service = DestinationService()
