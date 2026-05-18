"""Scrapling MCP Server for OpenCode agent-time probing.

This MCP server exposes a scrapling-based web probing tool that can be used
by OpenCode agents during conversations to fetch and analyze battery data
from web pages without running a full enrichment workflow.

Usage:
    python -m app.mcp_server.scrapling_mcp

Requires the MCP SDK:
    pip install mcp[cli]
"""
import os
import sys
import json
from typing import Optional
import asyncio

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.stdio import stdio_server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    Server = None

import structlog
logger = structlog.get_logger()


SCRAPLING_TOOL_DESCRIPTION = """
Scrape a web page using Scrapling (adaptive, browser-grade Python web extractor).

Use this when you need to quickly probe a battery parts page during analysis.
Scrapling automatically detects and handles JavaScript-rendered pages,
lazy-loaded content, and anti-bot protections.

Input:
  - url: The URL to scrape
  - selector (optional): CSS selector to extract specific elements
  - wait_for (optional): CSS selector to wait for before extracting

Output:
  - HTML content, visible text, detected part numbers, vehicle mentions
"""


async def scrape_with_scrapling(url: str, selector: Optional[str] = None, wait_for: Optional[str] = None) -> dict:
    try:
        from scrapling import Adaptor

        adaptor = Adaptor(url)
        await adaptor.fetch(wait_for=wait_for)

        if selector:
            target = adaptor.css(selector)
            visible_text = target.text if target else ""
            html = target.html if target else ""
        else:
            visible_text = adaptor.visible_text or ""
            html = adaptor.html

        import re
        pncodes_re = re.compile(r'\b[A-Z]{2,4}\d{2,4}[A-Z0-9]{2,8}\b')
        detected_pns = pncodes_re.findall(visible_text + html)

        battery_keywords = ['battery', 'pack', 'module', 'cell', 'HV', 'voltage', 'capacity', 'kWh', 'Ah', 'lithium', 'NCM', 'NMC', 'LFP']
        battery_mentions = [kw for kw in battery_keywords if kw.lower() in visible_text.lower()]

        vehicle_re = re.compile(r'\b(Taycan|Cayenne|Panamera|911|718|Macan|Taycan|Discovery|Range Rover|Defender)\b', re.IGNORECASE)
        detected_vehicles = vehicle_re.findall(visible_text)

        return {
            "status": "success",
            "url": url,
            "html_length": len(html),
            "visible_text_length": len(visible_text),
            "detected_part_numbers": list(set(detected_pns))[:20],
            "battery_keywords_found": list(set(battery_mentions)),
            "detected_vehicles": list(set(detected_vehicles)),
            "visible_text_snippet": visible_text[:2000],
            "html_snippet": html[:1000],
        }
    except Exception as e:
        logger.error("scrapling_mcp_scrape_failed", url=url, error=str(e))
        return {
            "status": "error",
            "url": url,
            "error": str(e),
        }


async def main():
    if not HAS_MCP:
        print("ERROR: MCP SDK not installed. Run: pip install mcp[cli]", file=sys.stderr)
        sys.exit(1)

    server = Server("ev-battery-scrapling-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="scrape_page",
                description=SCRAPLING_TOOL_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to scrape"},
                        "selector": {"type": "string", "description": "CSS selector (optional)"},
                        "wait_for": {"type": "string", "description": "CSS selector to wait for (optional)"},
                    },
                    "required": ["url"],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "scrape_page":
            result = await scrape_with_scrapling(
                url=arguments["url"],
                selector=arguments.get("selector"),
                wait_for=arguments.get("wait_for"),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        raise ValueError(f"Unknown tool: {name}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
