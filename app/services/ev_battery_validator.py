from typing import Optional
import structlog
import json
import httpx

logger = structlog.get_logger()

DEEPSEEK_API_URL = "http://144.91.126.111:4000/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"

NEGATIVE_INDICATORS = [
    "12v", "12-volt", "12 volt",
    "starter battery", "starting battery", "start battery",
    "servitude battery", "service battery",
    "conventional battery", "flooded battery",
    "lead-acid", "lead acid", "agm battery", "efb battery",
    "alternator", "brake fluid", "windshield wiper",
    "oil filter", "air filter", "spark plug", "ignition",
]

POSITIVE_INDICATORS = [
    "hv module", "hv_module", "hv battery",
    "high voltage", "high-voltage", "traction battery",
    "ev battery", "electric vehicle battery",
    "battery pack", "battery module", "battery cell",
    "lithium-ion", "lithium ion", "li-ion", "liion",
    "nmc", "ncm", "lfp", "lto", "nca",
    "kwh", "kilowatt hour",
]

EV_BATTERY_PN_TYPES = {
    "pack", "hv_module", "hv_cell", "module", "cell",
    "battery pack", "hv battery", "traction battery",
    "ev battery", "battery module", "battery cell",
}

NON_EV_PN_TYPES = {
    "starter battery", "12v battery", "auxiliary battery",
    "retailer sku", "retailer sku/ean", "manufacturer part number",
    "starter", "alternator", "conventional",
}


class EVBatteryValidator:
    def __init__(self):
        self.logger = logger

    async def validate_with_ai(self, part_data: dict, context: dict = None) -> dict:
        """
        Use DeepSeek to judge if a found part is actually an EV battery component.
        Returns: {is_valid: bool, confidence: float, reason: str, warnings: list}
        """
        prompt = self._build_validation_prompt(part_data, context)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    DEEPSEEK_API_URL,
                    json={
                        "model": DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": "You are an EV battery parts expert. Evaluate whether a found part number is actually an electric vehicle battery component (traction battery, HV battery pack/module/cell) or a different type of battery (starter, auxiliary, service, etc.)."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500,
                    }
                )
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                return self._parse_ai_response(content)

        except Exception as e:
            self.logger.error("ai_validation_failed", error=str(e), part_number=part_data.get("normalized"))
            return {
                "is_valid": False,
                "confidence": 0.0,
                "reason": f"AI validation failed: {str(e)}",
                "warnings": ["AI_VALIDATION_FAILED"]
            }

    def _build_validation_prompt(self, part_data: dict, context: dict = None) -> str:
        normalized = part_data.get("normalized", "")
        brand = part_data.get("brand", "")
        pn_type = part_data.get("pn_type", "")
        name = part_data.get("name", "")
        source_url = part_data.get("source_url", "")
        evidence_quote = part_data.get("evidence_quote", "")

        context_info = ""
        if context:
            context_info = f"\n\nAdditional context found:\n"
            for key, value in context.items():
                context_info += f"- {key}: {value}\n"

        return f"""Evaluate this part number:

Part Number: {normalized}
Brand: {brand}
PN Type: {pn_type}
Name/Description: {name}
Source URL: {source_url}
Evidence Quote: {evidence_quote}
{context_info}

Is this an EV traction battery (HV battery pack, module, or cell)? Answer:
1. YES if it appears to be an EV battery component
2. NO if it appears to be a starter battery, 12V auxiliary battery, service battery, or unrelated part

Consider:
- Does the name/description indicate HV/traction/EV battery?
- Does the source URL show it comes from an EV battery context?
- Are there any contradictory indicators (12V, starter, service, etc.)?

Respond in JSON format:
{{"is_ev_battery": true/false, "confidence": 0.0-1.0, "reason": "brief explanation", "warnings": ["any concerns"]}}"""

    def _parse_ai_response(self, content: str) -> dict:
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            return {
                "is_valid": data.get("is_ev_battery", False),
                "confidence": data.get("confidence", 0.5),
                "reason": data.get("reason", "No reason provided"),
                "warnings": data.get("warnings", [])
            }
        except json.JSONDecodeError:
            content_lower = content.lower()
            is_ev = "yes" in content_lower and "ev" in content_lower
            return {
                "is_valid": is_ev,
                "confidence": 0.5,
                "reason": content[:200],
                "warnings": ["PARSE_FAILED"]
            }

    def validate_rules_based(self, part_data: dict) -> dict:
        """
        Fast rules-based validation before calling AI.
        Returns: {is_valid: bool, reason: str, warnings: list}
        """
        warnings = []
        normalized = (part_data.get("normalized", "") or "").lower()
        brand = (part_data.get("brand", "") or "").lower()
        pn_type = (part_data.get("pn_type", "") or "").lower()
        name = (part_data.get("name", "") or "").lower()
        evidence = (part_data.get("evidence_quote", "") or "").lower()
        source_url = (part_data.get("source_url", "") or "").lower()

        combined_text = f"{normalized} {brand} {pn_type} {name} {evidence} {source_url}"

        for indicator in NEGATIVE_INDICATORS:
            if indicator.lower() in combined_text:
                warnings.append(f"NEGATIVE_INDICATOR: {indicator}")

        if pn_type in NON_EV_PN_TYPES:
            warnings.append(f"NON_EV_PN_TYPE: {pn_type}")

        if warnings:
            return {
                "is_valid": False,
                "reason": f"Rejected by rules: {warnings[0]}",
                "warnings": warnings
            }

        positive_count = sum(1 for ind in POSITIVE_INDICATORS if ind.lower() in combined_text)

        if positive_count >= 2:
            return {
                "is_valid": True,
                "reason": f"Passed rules ({positive_count} positive indicators)",
                "warnings": warnings
            }

        if pn_type in EV_BATTERY_PN_TYPES and positive_count >= 1:
            return {
                "is_valid": True,
                "reason": f"Passed by PnType ({positive_count} positive indicators)",
                "warnings": warnings
            }

        return {
            "is_valid": False,
            "reason": f"Inconclusive - only {positive_count} positive indicators",
            "warnings": warnings + ["INCONCLUSIVE"]
        }

    async def validate_part(self, part_data: dict, context: dict = None) -> dict:
        """
        Full validation: rules first, then AI if rules pass.
        """
        rules_result = self.validate_rules_based(part_data)

        if not rules_result["is_valid"]:
            return rules_result

        if rules_result["warnings"]:
            ai_result = await self.validate_with_ai(part_data, context)
            return ai_result

        return rules_result
