# Briefing: Filtering & Categorization

> NotamCollection and WeatherCollection fluent APIs, plus pluggable categorization pipeline

## Intent

Provide flexible NOTAM and weather filtering that:
- Works on any NOTAM/weather report regardless of source
- Supports spatial queries (route corridor, radius)
- Handles time windows for flight planning
- Allows custom categorization (rules, LLM)

## NotamCollection API

Follows `QueryableCollection` pattern from euro_aip. All methods return new collections (immutable).

### Filter Categories

| Category | Methods | Use Case |
|----------|---------|----------|
| **Location** | `for_airport()`, `for_fir()`, `for_airports()` | Terminal NOTAMs |
| **Spatial** | `within_radius()`, `along_route()`, `near_airports()` | Enroute, nearby |
| **Time** | `active_at()`, `active_during()`, `active_now()` | Flight planning |
| **Category** | `runway_related()`, `navigation_related()`, `airspace_related()` | Quick filters |
| **Q-code** | `by_q_code()`, `by_q_code_prefix()`, `by_traffic_type()` | ICAO standard |
| **Custom** | `by_custom_category()`, `by_custom_tag()` | After categorization |
| **Content** | `containing()`, `matching()` | Text search |
| **Altitude** | `below_altitude()`, `above_altitude()`, `in_altitude_range()` | FL filtering |

### Usage Pattern
```python
# Chain filters, combine with set ops
departure_critical = (
    notams.for_airport("LFPG").active_now()
) & (
    notams.runway_related() | notams.procedure_related()
)

# Spatial: along route with 25nm corridor
enroute = notams.along_route(route, corridor_nm=25).active_during(dep, arr)

# Score and sort by relevance
sorted_notams = notams.scored(RouteRelevanceScorer(route)).sorted_by_score()
```

## Categorization Pipeline

### Architecture
```
Notam → [QCodeCategorizer] → [TextRuleCategorizer] → [LLMCategorizer] → Result
              ↓                      ↓                      ↓
         confidence=1.0         confidence=0.7         confidence=0.9
```

Pipeline merges results: highest confidence wins for `primary_category`, all categories/tags merged.

### Built-in Categorizers

| Categorizer | Confidence | When to Use |
|-------------|------------|-------------|
| `QCodeCategorizer` | 1.0 | Q-code present (most reliable) |
| `TextRuleCategorizer` | 0.7 | Regex patterns on NOTAM text |
| `LLMCategorizer` | varies | Complex/ambiguous NOTAMs (future) |

### CategorizationResult
```python
@dataclass
class CategorizationResult:
    primary_category: str       # Most relevant category
    categories: Set[str]        # All applicable
    tags: Set[str]              # Granular tags (crane, ils, closed)
    confidence: float           # 0-1
```

### Usage
```python
pipeline = CategorizationPipeline()  # Default: Q-code + text rules
pipeline.categorize_all(briefing.notams)

# Now NOTAMs have custom_categories, custom_tags, primary_category
cranes = briefing.notams_query.by_custom_tag("crane")
runway_issues = briefing.notams_query.by_custom_category("runway")
```

## WeatherCollection API

Follows same `QueryableCollection` pattern. All methods return new collections.

| Category | Methods | Use Case |
|----------|---------|----------|
| **Type** | `metars()`, `tafs()` | Split by report type (metars includes SPECI) |
| **Location** | `for_airport()`, `for_airports()` | Filter by ICAO |
| **Category** | `by_category()`, `worse_than()`, `at_or_worse_than()` | Flight category filtering |
| **Time** | `latest()`, `before()`, `after()`, `between()`, `chronological()` | Time-based queries |
| **Wind** | `crosswind_exceeds(heading, limit_kt)` | Check runway crosswind limits |
| **Grouping** | `group_by_airport()` | Dict[icao, WeatherCollection] |

### Usage Pattern
```python
# Get latest METAR for departure
metar = briefing.weather_query.metars().for_airport("LFPG").latest()

# Find all IFR or worse conditions
bad_wx = briefing.weather_query.at_or_worse_than(FlightCategory.IFR).all()

# Group weather by airport
by_airport = briefing.weather_query.group_by_airport()
```

## Key Choices

| Decision | Rationale |
|----------|-----------|
| `active_during(start, end)` over just `active_now()` | Flight planning needs future windows |
| Categorizers are pluggable | Add LLM later without changing API |
| Confidence scores on results | Know when to trust categorization |
| Custom tags separate from categories | Tags are granular (crane), categories are broad (obstacle) |
| WeatherCollection has no model ref | Weather doesn't need spatial coord lookups like NOTAMs |

## Gotchas

- **Spatial filters need coordinates**: NOTAMs without coords are skipped by `along_route()`, `within_radius()`
- **Set operations create new collections**: `a & b` doesn't modify `a`
- **Time overlap logic**: `active_during()` includes NOTAMs active for ANY part of window
- **Permanent NOTAMs**: `is_permanent=True` means no end date, always included in future windows
- **WeatherCollection.latest()**: Returns single report (not collection), based on `observation_time`

## References

- Main briefing doc: [briefing.md](./briefing.md)
- Weather module: [briefing_weather.md](./briefing_weather.md)
- Parsing details: [briefing_parsing.md](./briefing_parsing.md)
- Code: `euro_aip/briefing/collections/notam_collection.py`, `euro_aip/briefing/weather/collection.py`
