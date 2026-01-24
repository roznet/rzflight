# Briefing: Parsing Architecture

> Source-agnostic parsing with clear separation of concerns

## Intent

Separate **extraction** (getting text from PDF/API) from **parsing** (converting text to models).

This allows:
- Same parsers work on any source
- Easy to add new sources without touching parsing
- Unit test parsers without source dependencies
- Consistent data structures regardless of origin

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  BriefingSource │     │    Parsers      │     │   Enrichment    │
│  (extraction)   │────▶│  (standalone)   │────▶│   (optional)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
   ForeFlight PDF         NotamParser            CategorizationPipeline
   AVWX API               MetarParser            Q-code decoder
   FAA API                TafParser
```

## Standalone Parsers

Parsers are **class methods** that work on raw text - no source dependency.

```python
from euro_aip.briefing.parsers import NotamParser, MetarParser, TafParser

# Parse single item
notam = NotamParser.parse(notam_text)
metar = MetarParser.parse(metar_text)

# Parse multiple from a block
notams = NotamParser.parse_many(text_with_many_notams)
```

### NotamParser Details

Parses ICAO NOTAM format:
- Extracts ID (A1234/24), location, Q-line
- Decodes Q-code → category, traffic type, scope, altitude limits
- Extracts effective dates, coordinates, radius
- Sets `parse_confidence` (0-1) based on how much was successfully parsed

### What Sources Do

Sources handle extraction only, then delegate to parsers:

```python
class ForeFlightSource(BriefingSource):
    def parse(self, pdf_path) -> Briefing:
        text = self._extract_text(pdf_path)  # PDF → text

        # Delegate to standalone parsers
        notams = NotamParser.parse_many(self._get_notam_section(text))
        metars = MetarParser.parse_many(self._get_metar_section(text))

        return Briefing(notams=notams, metars=metars, ...)
```

## BriefingSource Interface

```python
class BriefingSource(ABC):
    @abstractmethod
    def parse(self, data: Any) -> Briefing:
        """Parse source data into Briefing."""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """e.g., ['pdf'] for ForeFlight"""
        pass
```

## Adding a New Source

1. Create `euro_aip/briefing/sources/my_source.py`
2. Implement `BriefingSource` interface
3. Extract text/data from your format
4. Use existing parsers: `NotamParser.parse_many()`, etc.
5. Return `Briefing` object

The parsers handle the hard work - your source just extracts text.

## Key Choices

| Decision | Rationale |
|----------|-----------|
| Parsers are class methods | No instantiation needed, stateless |
| Sources inherit CachedSource | Reuse caching from euro_aip |
| parse_confidence on models | Know when parsing was incomplete |
| Separate section extraction | ForeFlight has specific sections; isolate that logic |

## Gotchas

- **ForeFlight format may change**: Section headers/layout could shift between versions
- **Abbreviated NOTAMs**: Some sources abbreviate Q-lines - text rules compensate
- **Encoding issues**: PDFs may have weird Unicode, normalize before parsing
- **NOTAM ID uniqueness**: Same NOTAM can appear in multiple briefings

## References

- Main briefing doc: [briefing.md](./briefing.md)
- Filtering: [briefing_filtering.md](./briefing_filtering.md)
- Code: `euro_aip/briefing/parsers/`, `euro_aip/briefing/sources/`
