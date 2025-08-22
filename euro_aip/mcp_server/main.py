#!/usr/bin/env python3
"""
MCP Server for Euro AIP Airport Database

This server provides tools for querying airport data, route planning, and flight information
to LLM clients like ChatGPT and Claude.

"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, TypedDict

from fastmcp import FastMCP, Context

from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.airport import Airport

# ---- Types for structured output (optional but nice) -------------------------
class AirportSummary(TypedDict, total=False):
    ident: str
    name: str
    municipality: Optional[str]
    country: Optional[str]
    latitude_deg: Optional[float]
    longitude_deg: Optional[float]
    longest_runway_length_ft: Optional[int]
    point_of_entry: bool

class AirportNearRoute(TypedDict):
    airport: AirportSummary
    distance_nm: float

# ---- Global model storage for FastMCP 2.11 --------------------------------
_model: Optional[EuroAipModel] = None

def get_model() -> EuroAipModel:
    """Get the global model instance."""
    if _model is None:
        raise RuntimeError("Model not initialized. Server not started properly.")
    return _model

# ---- Server with lifespan to manage resources --------------------------------
@asynccontextmanager
async def lifespan(app: FastMCP):
    global _model
    db_path = os.environ.get("AIRPORTS_DB", "airports.db")
    # Let FastMCP handle logging/levels via FASTMCP_LOG_LEVEL, etc.
    db_storage = DatabaseStorage(db_path)
    _model = db_storage.load_model()
    try:
        yield
    finally:
        # Add teardown if needed
        pass

mcp = FastMCP(
    name="euro_aip",
    instructions=(
        "Euro AIP Airport Database MCP Server. Tools for querying airport data, "
        "route planning, and flight information."
    ),
    lifespan=lifespan,
)

# ---- Helpers -----------------------------------------------------------------
def _airport_summary(a: Airport) -> AirportSummary:
    return {
        "ident": a.ident,
        "name": a.name,
        "municipality": a.municipality,
        "country": a.iso_country,
        "latitude_deg": getattr(a, "latitude_deg", None),
        "longitude_deg": getattr(a, "longitude_deg", None),
        "longest_runway_length_ft": getattr(a, "longest_runway_length_ft", None),
        "point_of_entry": bool(getattr(a, "point_of_entry", False)),
    }

def _pretty_airport(a: Airport) -> str:
    lines = [f"**{a.ident} - {a.name}**"]
    loc = f"{a.municipality or 'Unknown'}, {a.iso_country or 'Unknown'}"
    lines.append(f"Location: {loc}")
    if getattr(a, "latitude_deg", None) is not None and getattr(a, "longitude_deg", None) is not None:
        lines.append(f"Coordinates: {a.latitude_deg:.4f}, {a.longitude_deg:.4f}")
    if getattr(a, "longest_runway_length_ft", None) is not None:
        lines.append(f"Runway: {a.longest_runway_length_ft}ft")
    if getattr(a, "point_of_entry", False):
        lines.append("Border crossing point")
    return "\n".join(lines)

# ---- Tools -------------------------------------------------------------------
@mcp.tool(name="search_airports", description="Search by name, ICAO, IATA, or municipality")
def search_airports(query: str, max_results: int = 20, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    q = query.upper().strip()
    matches: List[Airport] = []

    for a in model.airports.values():
        if (
            (q in a.ident)
            or (a.name and q in a.name.upper())
            or (getattr(a, "iata_code", None) and q in a.iata_code)
            or (a.municipality and q in a.municipality.upper())
        ):
            matches.append(a)
            if len(matches) >= max_results:
                break

    items = [_airport_summary(a) for a in matches]
    pretty = "No airports found." if not items else (
        f"Found {len(items)} airports matching '{query}':\n\n" + "\n\n".join(_pretty_airport(a) for a in matches)
    )
    return {"count": len(items), "items": items, "pretty": pretty}

@mcp.tool(name="find_airports_near_route", description="Find airports within max_distance_nm of a direct route")
def find_airports_near_route(from_icao: str, to_icao: str, max_distance_nm: float = 50.0, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    results = model.find_airports_near_route([from_icao.upper(), to_icao.upper()], max_distance_nm)
    if not results:
        return {"count": 0, "items": [], "pretty": f"No airports within {max_distance_nm}nm of {from_icao}->{to_icao}."}

    items: List[AirportNearRoute] = []
    pretty_lines: List[str] = [f"Found {len(results)} airports within {max_distance_nm}nm of route {from_icao} to {to_icao}:\n"]
    for item in results:
        a: Airport = item["airport"]
        items.append({"airport": _airport_summary(a), "distance_nm": float(item["distance_nm"])})
        pretty_lines.append(f"{_pretty_airport(a)} (Distance: {item['distance_nm']:.1f}nm)\n")
    return {"count": len(items), "items": items, "pretty": "\n".join(pretty_lines)}

@mcp.tool(name="get_airport_details", description="Get details by ICAO")
def get_airport_details(icao_code: str, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    icao = icao_code.strip().upper()
    if not icao:
        raise ValueError("ICAO code is required")

    a = model.get_airport(icao)
    if not a:
        return {"found": False, "pretty": f"Airport {icao} not found."}

    details: Dict[str, Any] = {
        "found": True,
        "airport": _airport_summary(a),
        "runways": {
            "count": len(a.runways),
            "longest_ft": getattr(a, "longest_runway_length_ft", None),
            "hard_surface": bool(getattr(a, "has_hard_runway", False)),
        },
        "procedures": {"count": len(a.procedures)},
        "point_of_entry": bool(getattr(a, "point_of_entry", False)),
        "standardized": [
            {"field": e.std_field, "value": e.value}
            for e in (a.get_standardized_entries() or [])
            if getattr(e, "std_field", None) and getattr(e, "value", None)
        ],
    }

    pretty = [
        f"**{a.ident} - {a.name}**",
        f"City: {a.municipality or 'Unknown'}",
        f"Country: {a.iso_country or 'Unknown'}",
    ]
    if getattr(a, "latitude_deg", None) is not None and getattr(a, "longitude_deg", None) is not None:
        pretty.append(f"Coordinates: {a.latitude_deg:.4f}, {a.longitude_deg:.4f}")
    if getattr(a, "elevation_ft", None) is not None:
        pretty.append(f"Elevation: {a.elevation_ft}ft")
    pretty += [
        "",
        f"Runways: {len(a.runways)} (longest {getattr(a, 'longest_runway_length_ft', 'Unknown')}ft)",
        f"Hard surface: {'Yes' if getattr(a,'has_hard_runway', False) else 'No'}",
        "",
        f"Procedures: {len(a.procedures)}",
        "",
        f"Border crossing point: {'Yes' if getattr(a,'point_of_entry', False) else 'No'}",
    ]
    details["pretty"] = "\n".join(pretty)
    return details

@mcp.tool(name="get_border_crossing_airports", description="List airports that are border crossing points (optional country filter)")
def get_border_crossing_airports(country: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    airports = model.get_border_crossing_airports()
    if country:
        c = country.upper()
        airports = [a for a in airports if (a.iso_country or "").upper() == c]

    grouped: Dict[str, List[AirportSummary]] = {}
    for a in airports:
        grouped.setdefault(a.iso_country or "Unknown", []).append(_airport_summary(a))

    pretty_lines: List[str] = [f"**Border Crossing Airports{' in ' + country if country else ''}:**\n"]
    for cc, arr in grouped.items():
        pretty_lines.append(f"**{cc}:**")
        for item in arr:
            label = item["ident"] + " - " + (item["name"] or "")
            city = item.get("municipality")
            pretty_lines.append(f"- {label}" + (f" ({city})" if city else ""))
        pretty_lines.append("")
    return {"count": sum(len(v) for v in grouped.values()), "by_country": grouped, "pretty": "\n".join(pretty_lines)}

@mcp.tool(name="get_airport_statistics", description="Basic stats for airports (optional country)")
def get_airport_statistics(country: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    model = get_model()
    airports = model.get_airports_by_country(country.upper()) if country else list(model.airports.values())
    total = len(airports)
    stats = {
        "total_airports": total,
        "with_customs": sum(1 for a in airports if getattr(a, "point_of_entry", False)),
        "with_avgas": sum(1 for a in airports if getattr(a, "avgas", False)),
        "with_jet_a": sum(1 for a in airports if getattr(a, "jet_a", False)),
        "with_procedures": sum(1 for a in airports if a.procedures),
    }
    pct = lambda n: round((n / total * 100), 1) if total else 0.0
    stats.update({
        "with_customs_pct": pct(stats["with_customs"]),
        "with_avgas_pct": pct(stats["with_avgas"]),
        "with_jet_a_pct": pct(stats["with_jet_a"]),
        "with_procedures_pct": pct(stats["with_procedures"]),
    })

    pretty = [
        f"**Airport Statistics{' for ' + country if country else ''}:**",
        f"Total airports: {stats['total_airports']}",
        f"With customs: {stats['with_customs']} ({stats['with_customs_pct']}%)",
        f"With AVGAS: {stats['with_avgas']} ({stats['with_avgas_pct']}%)",
        f"With Jet A: {stats['with_jet_a']} ({stats['with_jet_a_pct']}%)",
        f"With procedures: {stats['with_procedures']} ({stats['with_procedures_pct']}%)",
    ]
    return {"stats": stats, "pretty": "\n".join(pretty)}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Euro AIP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type: stdio (default) or http (replaces legacy SSE).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)",
    )
    parser.add_argument(
        "--database",
        default="airports.db",
        help="Database file (default: airports.db)",
    )

    args = parser.parse_args()
    if args.database:
        os.environ["AIRPORTS_DB"] = args.database

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()