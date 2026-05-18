"""Quick status check for all platform components.

Usage:
    python scripts/check_status.py
"""
import asyncio
import httpx
import sys
import os

async def check_all():
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8090')
    results = {}

    async with httpx.AsyncClient(timeout=10) as client:
        endpoints = [
            ('/api/v1/health/', 'API Health'),
            ('/api/v1/health/ready', 'DB Readiness'),
            ('/api/v1/config/property-definitions', 'Property Defs'),
            ('/api/v1/config/brands', 'Brands Config'),
        ]
        for path, name in endpoints:
            try:
                r = await client.get(f'{base_url}{path}')
                results[name] = {'status': r.status_code, 'ok': r.status_code == 200}
            except Exception as e:
                results[name] = {'status': 0, 'ok': False, 'error': str(e)}

    print('=== Platform Status ===')
    for name, res in results.items():
        icon = '✓' if res['ok'] else '✗'
        print(f'{icon} {name}: HTTP {res["status"]}')

    all_ok = all(v['ok'] for v in results.values())
    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    asyncio.run(check_all())
