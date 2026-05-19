# EV Battery Intelligence Platform

> Version 3.0 | Implementation based on ev_battery_platform_implementation_plan_v3.md

## Overview

A self-hosted battery data enrichment, cross-reference, and knowledge system for European automotive battery packs, HV modules, HV cells, and supporting controllers.

### Primary Users
- **Recycling and Second-Life Operators** — fast part number lookup, chemistry identification, capacity data
- **Fleet and Maintenance Operations** — vehicle-to-battery cross-references, supersession chains
- **R&D and Cross-Brand Analysis** — supplier commonality, configuration patterns, energy density trends

### Phase 1 Brands
Porsche (teile.com), Mercedes-Benz (teile.com), JLR (topix.jaguarlandrover.com), Stellantis, batterydesign.net seed

## Architecture

- **Hatchet** workflow orchestration (replaces Temporal)
- **Staggered parallel scraping** — 3-wave fetch with quorum-based escalation
- **Evidence-first data model** — every property carries source, evidence, confidence
- **ConsensusMerger** — deduplicates and merges multi-wave scrape results

## Deployment

```bash
# Deploys automatically on push to main via GitHub Actions
# Required secrets:
# - HATCHET_CLIENT_TOKEN
# - SERVER2_HOST
# - SERVER2_SSH_PASSWORD
# - SECRET_KEY
```

## Getting Started

```bash
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_property_definitions.py
```

## API

- Swagger: `http://144.91.126.111:8090/docs`
- Health: `http://144.91.126.111:8090/api/v1/health/`
