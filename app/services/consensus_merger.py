from typing import Optional
import structlog
from app.schemas.battery_scrape_payload import BatteryScrapePayload, PartNumberItem, PropertyItem, VehicleItem

logger = structlog.get_logger()


class ConsensusMerger:
    def __init__(self):
        self.logger = logger

    def merge_payloads(self, payloads: list[BatteryScrapePayload]) -> dict:
        if not payloads:
            return {"merged": None, "conflicts": [], "score": 0.0}

        successful = [p for p in payloads if p is not None]
        if not successful:
            return {"merged": None, "conflicts": [], "score": 0.0}

        winning_payload = max(successful, key=lambda p: len(p.part_numbers) + len(p.properties))

        merged_part_numbers = self._merge_part_numbers(successful)
        merged_properties = self._merge_properties(successful)
        merged_vehicles = self._merge_vehicles(successful)
        merged_relationships = self._merge_relationships(successful)

        conflicts = self._detect_conflicts(successful)
        consensus_score = self._compute_consensus_score(successful, conflicts)

        return {
            "merged": {
                "_meta": winning_payload._meta.model_dump(),
                "part_numbers": [pn.model_dump() for pn in merged_part_numbers],
                "properties": {k: v.model_dump() for k, v in merged_properties.items()},
                "relationships": [r.model_dump() for r in merged_relationships],
                "vehicles": [v.model_dump() for v in merged_vehicles],
            },
            "conflicts": conflicts,
            "score": consensus_score,
            "attempts_succeeded": len(successful),
        }

    def _merge_part_numbers(self, payloads: list[BatteryScrapePayload]) -> list[PartNumberItem]:
        seen = {}
        for payload in payloads:
            for pn in payload.part_numbers:
                key = (pn.normalized, pn.brand)
                if key not in seen:
                    seen[key] = pn
                else:
                    existing = seen[key]
                    if pn.evidence_quote and len(pn.evidence_quote) > len(existing.evidence_quote or ""):
                        seen[key] = pn
        return list(seen.values())

    def _merge_properties(self, payloads: list[BatteryScrapePayload]) -> dict[str, PropertyItem]:
        merged = {}
        for payload in payloads:
            for code, prop in payload.properties.items():
                if code not in merged:
                    merged[code] = prop
                else:
                    existing = merged[code]
                    if isinstance(prop.value, (int, float)) and isinstance(existing.value, (int, float)):
                        avg_val = (float(prop.value) + float(existing.value)) / 2
                        merged[code] = PropertyItem(
                            value=avg_val,
                            unit=prop.unit or existing.unit,
                            evidence_quote=prop.evidence_quote or existing.evidence_quote,
                            confidence=max(prop.confidence, existing.confidence),
                        )
                    elif prop.confidence > existing.confidence:
                        merged[code] = prop
        return merged

    def _merge_vehicles(self, payloads: list[BatteryScrapePayload]) -> list[VehicleItem]:
        seen = {}
        for payload in payloads:
            for v in payload.vehicles:
                key = (v.make, v.model, v.variant_code)
                if key not in seen:
                    seen[key] = v
                elif v.evidence_quote and len(v.evidence_quote) > len(seen[key].evidence_quote or ""):
                    seen[key] = v
        return list(seen.values())

    def _merge_relationships(self, payloads: list[BatteryScrapePayload]) -> list:
        all_rels = []
        for payload in payloads:
            all_rels.extend(payload.relationships)
        seen = {(r.type, r.target_pn_or_id) for r in all_rels}
        unique = []
        for rel in all_rels:
            key = (rel.type, rel.target_pn_or_id)
            if key in seen:
                unique.append(rel)
                seen.discard(key)
        return unique

    def _detect_conflicts(self, payloads: list[BatteryScrapePayload]) -> list[dict]:
        conflicts = []
        prop_values_by_code = {}
        for payload in payloads:
            for code, prop in payload.properties.items():
                if code not in prop_values_by_code:
                    prop_values_by_code[code] = []
                prop_values_by_code[code].append(prop.value)

        for code, values in prop_values_by_code.items():
            unique_values = set(str(v) for v in values)
            if len(unique_values) > 1:
                conflicts.append({
                    "field": code,
                    "conflicting_values": list(unique_values),
                    "count": len(unique_values),
                })

        return conflicts

    def _compute_consensus_score(self, payloads: list[BatteryScrapePayload], conflicts: list[dict]) -> float:
        if not payloads:
            return 0.0
        base_score = 0.5
        part_number_bonus = min(len(self._merge_part_numbers(payloads)) / max(len(payloads), 1) * 0.1, 0.2)
        property_bonus = min(len(self._merge_properties(payloads)) / max(sum(len(p.properties) for p in payloads), 1) * 0.2, 0.2)
        conflict_penalty = len(conflicts) * 0.05
        return max(0.0, min(1.0, base_score + part_number_bonus + property_bonus - conflict_penalty))
