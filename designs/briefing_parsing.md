# Briefing: Parsing Architecture

> Source-agnostic parsing with clear separation of concerns

## Cross-Platform Consistency Requirement

**CRITICAL**: The briefing parsing system has both Python and Swift implementations. These MUST produce identical output for the same input.

| Component | Python | Swift |
|-----------|--------|-------|
| NOTAM Parser | `NotamParser` | `NotamParser` |
| Q-code Lookup | `parse_q_code()` | `QCodeLookup` |
| Document References | `DocumentReferenceExtractor` | `DocumentReferenceExtractor` |
| ForeFlight PDF | `ForeFlightSource` | `ForeFlightParser` |

**Shared Resources** (in `Resources/` or `data/`):
- `q_codes.json` - Q-code subject/condition meanings
- `document_references.json` - Provider patterns for AIP supplement links

When modifying parsing logic:
1. Update BOTH implementations
2. Use the same config files
3. Run tests on both platforms
4. Ensure JSON output is compatible

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

## Document Reference Extraction

NOTAMs often reference external documents like AIP Supplements and AICs. The `DocumentReferenceExtractor` extracts these references and generates direct URLs.

### Configuration-Driven Providers

Providers are defined in `document_references.json`. Supports both 2-group patterns (number, year) and 3-group patterns (series, number, year):

```json
{
  "providers": [
    {
      "id": "uk_nats",
      "name": "UK NATS AIP Supplements",
      "trigger_patterns": ["WWW.NATS.AERO/AIS"],
      "reference_pattern": "SUP\\s*(\\d{3})/(\\d{2,4})",
      "document_url_templates": ["...EG_Sup_{year}_{number}_en.pdf"],
      "year_format": "4digit",
      "number_padding": 3
    },
    {
      "id": "uk_nats_aic",
      "name": "UK NATS AIC",
      "trigger_patterns": ["AIC Y", "AIC W", "AIC P"],
      "reference_pattern": "AIC\\s+([A-Z])\\s*(\\d{1,3})/(\\d{2,4})",
      "identifier_format": "AIC {series} {number}/{year}",
      "type": "aic",
      "document_url_templates": ["...EG_Circ_{year}_{series}_{number}_en.pdf"]
    }
  ]
}
```

**Optional provider fields:**
- `identifier_format` - Template with `{series}`, `{number}`, `{year}` placeholders (default: `"SUP {number}/{year}"`)
- `type` - Document type string (default: `"aip_supplement"`)

### How It Works

1. Check if NOTAM text contains any `trigger_patterns`
2. If matched, extract references using `reference_pattern` regex (2 or 3 capture groups)
3. Normalize year (2-digit → 4-digit) and pad number
4. Build identifier from `identifier_format` template (or default)
5. Generate URLs from `document_url_templates` with `{year}`, `{number}`, `{series}` substitution

### Supported Providers

| Provider | Type | Trigger | Example | Output URLs |
|----------|------|---------|---------|-------------|
| UK NATS SUP | `aip_supplement` | `WWW.NATS.AERO/AIS` | `SUP 059/2025` | `EG_Sup_2025_059_en.pdf` |
| UK NATS AIC | `aic` | `AIC Y`, `AIC W`, `AIC P` | `AIC Y 148/2025` | `EG_Circ_2025_Y_148_en.pdf` |
| France SIA | `aip_supplement` | `WWW.SIA.AVIATION-CIVILE.GOUV.FR` | `SUP 009/26` | `lf_sup_2026_009_fr.pdf`, `_en.pdf` |

### Adding New Providers

1. Add entry to `document_references.json` (in BOTH `Resources/` and `data/`)
2. Use `identifier_format` and `type` for non-SUP document types
3. Use 3 capture groups in `reference_pattern` if the document has a series letter
4. No code changes needed - both parsers read the config
5. Test with sample NOTAM text

### Usage

```python
# Python
from euro_aip.briefing.parsers.document_reference_extractor import extract_document_references
refs = extract_document_references(notam_text)
```

```swift
// Swift
let refs = DocumentReferenceExtractor.extract(from: notamText)
```

Output is stored in `Notam.document_references` / `Notam.documentReferences`.

## Q-Code Lookup

Human-readable meanings for Q-codes are loaded from `q_codes.json`:

```python
# Python
from euro_aip.briefing.categorization.q_code import parse_q_code
info = parse_q_code("QMRLC")  # → subject: "Runway", condition: "Closed"
```

```swift
// Swift
let info = QCodeLookup.lookup("QMRLC")  // → displayText: "Runway: Closed"
```

Stored in `Notam.q_code_info` / `Notam.qCodeInfo`.

## Gotchas

- **ForeFlight format may change**: Section headers/layout could shift between versions
- **Abbreviated NOTAMs**: Some sources abbreviate Q-lines - text rules compensate
- **Encoding issues**: PDFs may have weird Unicode, normalize before parsing
- **NOTAM ID uniqueness**: Same NOTAM can appear in multiple briefings
- **Keep parsers in sync**: Changes to Python parser must be mirrored in Swift

## References

- Main briefing doc: [briefing.md](./briefing.md)
- Filtering: [briefing_filtering.md](./briefing_filtering.md)
- Code: `euro_aip/briefing/parsers/`, `euro_aip/briefing/sources/`
