# EV Battery Intelligence Platform

> Version 3.0 | Implementation based on ev_battery_platform_implementation_plan_v3.md

## Overview

A self-hosted battery data enrichment, cross-reference, and knowledge system for European automotive battery packs, HV modules, HV cells, and supporting controllers.

### Phase 1 Brands
Porsche, Mercedes-Benz, JLR, Stellantis (PSA/FCA), batterydesign.net seed

## Getting Started

```bash
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_property_definitions.py
```
