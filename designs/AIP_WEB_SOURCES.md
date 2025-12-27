# AIP Web Sources Documentation

This document describes the web sources for fetching AIP (Aeronautical Information Publication) data from various countries' eAIP systems. It documents the URL structures, parsing logic, and patterns that can be reused when adding support for new countries.

## Overview

Each web source implements:
- URL construction based on AIRAC dates
- Airport discovery from index pages
- HTML fetching with caching (7-day cache validity)
- Parsing using authority-specific parsers
- Integration with the EuroAipModel

## Common Patterns

### URL Construction
Most sources build URLs using:
- Base URL (country-specific)
- AIRAC date components (YYYY-MM-DD format)
- Path components (html/eAIP/...)

### Airport Discovery
Two main approaches:
1. **Link Pattern Matching**: Search all links in HTML for regex patterns matching airport page URLs
2. **Structured HTML Parsing**: Find specific divs/sections containing airport information, then extract links

### Caching
- Cache keys: `{airac_date}_{resource_type}_{identifier}.html`
- Cache validity: 7 days
- Resources cached: index, airport pages, TOC, navigation pages

### Parsing Pipeline
1. Fetch HTML content (with caching)
2. Use `AIPParserFactory.get_parser(authority, 'html')` to get appropriate parser
3. Parse HTML to extract AIP data and procedures
4. Return structured data with authority and parsed_data

---

## France eAIP Web Source

### Human Access URL

```
https://www.sia.aviation-civile.gouv.fr
```

### Root URL
```
https://www.sia.aviation-civile.gouv.fr/media/dvd
```

### URL Structure
```
{BASE_URL}/eAIP_{day}_{mon}_{year}/FRANCE/AIRAC-{year}-{mm}-{dd}/{path}
```

**Date Components:**
- Uses TWO dates: `airac_date` and `eaip_date` (can differ)
- eAIP date: Used for `eAIP_{day}_{mon}_{year}` part
  - day: DD format (e.g., "15")
  - mon: Uppercase month abbreviation (e.g., "JAN")
  - year: YYYY format (e.g., "2024")
- AIRAC date: Used for `AIRAC-{year}-{mm}-{dd}` part
  - day: DD format (e.g., "15")
  - mon: MM format (e.g., "01")
  - year: YYYY format (e.g., "2024")

**Example URL:**
```
https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_15_JAN_2024/FRANCE/AIRAC-2024-01-15/html/index-fr-FR.html
```

### Key URLs

**Index URL:**
```
html/index-fr-FR.html
```

**Airport URL:**
```
html/eAIP/FR-AD-2.{icao}-fr-FR.html
```
Example: `html/eAIP/FR-AD-2.LFPG-fr-FR.html`

**TOC URL (for frameset handling):**
```
html/toc-frameset-fr-FR.html
```

**Navigation URL (for nested frameset handling):**
```
html/eAIP/FR-menu-fr-FR.html
```

### Airport Discovery Logic

**Function:** `find_available_airports() -> List[str]`

**Process:**
1. Fetch index page using `_fetch_with_cache('index')`
2. Parse index HTML using `_parse_index_for_airports()`
3. Return sorted list of ICAO codes

**Parsing Logic:** `_parse_index_for_airports(index_html: bytes) -> Dict[str, str]`

1. Parse HTML with BeautifulSoup
2. Check if page is a frameset:
   - If `<frameset>` found:
     - Look for frame with `name='eAISNavigationBase'`
     - If found, fetch TOC page and call `_parse_toc_for_airports()`
3. If not frameset (or after TOC parsing):
   - Find all `<a>` tags in the HTML
   - For each link, extract `href` attribute
   - Match against regex pattern: `FR-AD-2\.(LF[A-Z]{2})-fr-FR\.html`
   - Extract ICAO code from first capture group
   - Build absolute URL using `_get_airport_url(icao)`
   - Return mapping: `{icao: absolute_url}`

**TOC Parsing:** `_parse_toc_for_airports(toc_html: bytes) -> Dict[str, str]`

1. Parse TOC HTML
2. Check if TOC is also a frameset:
   - If `<frameset>` found:
     - Look for frame with `name='eAISNavigation'`
     - If found, fetch navigation page and call `_parse_nav_for_airports()`
3. Otherwise, same link pattern matching as index parsing

**Navigation Parsing:** `_parse_nav_for_airports(nav_html: bytes) -> Dict[str, str]`

- Same link pattern matching approach as index parsing

**Pattern:**
```regex
FR-AD-2\.(LF[A-Z]{2})-fr-FR\.html
```
- Matches: `FR-AD-2.LFPG-fr-FR.html` → ICAO: `LFPG`

### Data Fetching

**Function:** `fetch_airport_html(icao: str) -> Optional[bytes]`
- Fetches airport HTML page with caching
- Cache key: `{airac_date}_airport_{icao}.html`

**Function:** `fetch_airport_aip(icao: str) -> Optional[Dict[str, Any]]`
- Fetches airport HTML
- Uses `AIPParserFactory.get_parser('LFC', 'html')` to get parser
- Calls `parser.parse(html_bytes, icao)` to extract AIP data
- Returns:
```python
{
    'icao': 'LFPG',
    'authority': 'LFC',
    'parsed_data': {...}  # Parsed AIP data structure
}
```

**Function:** `fetch_procedures(icao: str) -> List[Dict[str, Any]]`
- Fetches airport HTML
- Uses `AIPParserFactory.get_parser('LFC', 'html')` to get parser
- Calls `parser.extract_procedures(html_bytes, icao)` to extract procedures
- Returns list of procedure dictionaries

### Authority & Parser
- **Authority Code:** `LFC`
- **Parser:** `AIPParserFactory.get_parser('LFC', 'html')` → `LFCHTMLParser`
- **Procedure Parser:** `ProcedureParserFactory.get_parser('LFC')` → `LFCProcedureParser`
- **Source Name:** `france_eaip_html`

### Return Value Examples

**find_available_airports():**
```python
['LFBO', 'LFBZ', 'LFCR', 'LFKJ', 'LFPG', 'LFPO', ...]
```

**fetch_airport_aip('LFPG'):**
```python
{
    'icao': 'LFPG',
    'authority': 'LFC',
    'parsed_data': {
        # Parsed airport data from LFCHTMLParser
        'runways': [...],
        'frequencies': [...],
        # ... other AIP fields
    }
}
```

**fetch_procedures('LFPG'):**
```python
[
    {
        'name': 'ILS RWY 09L',
        'type': 'approach',
        'approach_type': 'ILS',
        'runway_ident': '09L',
        'runway_number': 9,
        'runway_letter': 'L',
        # ... other procedure fields
    },
    # ... more procedures
]
```

---

## UK eAIP Web Source

### Root URL
```
https://www.aurora.nats.co.uk/htmlAIP/Publications
```

### URL Structure
```
{BASE_URL}/{airac_date}-AIRAC/{path}
```

**Date Components:**
- Uses single `airac_date` in YYYY-MM-DD format
- AIRAC root: `{airac_date}-AIRAC` (e.g., `2024-01-15-AIRAC`)

**Example URL:**
```
https://www.aurora.nats.co.uk/htmlAIP/Publications/2024-01-15-AIRAC/html/eAIP/EG-menu-en-GB.html
```

### Key URLs

**Index URL:**
```
html/eAIP/EG-menu-en-GB.html
```

**Airport URL:**
```
html/eAIP/EG-AD-2.{icao}-en-GB.html
```
Example: `html/eAIP/EG-AD-2.EGLL-en-GB.html`

### Airport Discovery Logic

**Function:** `find_available_airports() -> List[str]`

**Process:**
1. Fetch index page using `_fetch_with_cache('index')`
2. Parse index HTML using `_parse_index_for_airports()`
3. Return sorted list of ICAO codes

**Parsing Logic:** `_parse_index_for_airports(index_html: bytes) -> Dict[str, str]`

1. Parse HTML with BeautifulSoup
2. Find the `<div id="ADdetails">` element
   - If not found, return empty dict (log warning)
3. Within ADdetails div, find all sub-divs matching pattern:
   - Regex: `AD-2\.EG[A-Z]{2}details`
   - Example IDs: `AD-2.EGLLdetails`, `AD-2.EGKKdetails`
4. For each airport div:
   - Find all `<a>` tags within the div
   - Extract `href` attribute from each link
   - Match against regex pattern: `EG-AD-2\.(EG[A-Z]{2})-en-GB\.html`
   - Extract ICAO code from first capture group
   - Build absolute URL using `_get_airport_url(icao)`
   - Store in mapping: `{icao: absolute_url}`
5. Return mapping: `{icao: absolute_url}`

**Pattern:**
```regex
EG-AD-2\.(EG[A-Z]{2})-en-GB\.html
```
- Matches: `EG-AD-2.EGLL-en-GB.html` → ICAO: `EGLL`

**Key Difference from France:**
- UK uses structured HTML parsing (looks for specific div structure)
- France uses link pattern matching across all links
- UK does not handle framesets (index page is direct HTML)

### Data Fetching

**Function:** `fetch_airport_html(icao: str) -> Optional[bytes]`
- Fetches airport HTML page with caching
- Cache key: `{airac_date}_airport_{icao}.html`

**Function:** `fetch_airport_aip(icao: str) -> Optional[Dict[str, Any]]`
- Fetches airport HTML
- Uses `AIPParserFactory.get_parser('EGC', 'html')` to get parser
- Calls `parser.parse(html_bytes, icao)` to extract AIP data
- Returns:
```python
{
    'icao': 'EGLL',
    'authority': 'EGC',
    'parsed_data': {...}  # Parsed AIP data structure
}
```

**Function:** `fetch_procedures(icao: str) -> List[Dict[str, Any]]`
- Fetches airport HTML
- Uses `AIPParserFactory.get_parser('EGC', 'html')` to get parser
- Calls `parser.extract_procedures(html_bytes, icao)` to extract procedures
- Returns list of procedure dictionaries

### Authority & Parser
- **Authority Code:** `EGC`
- **Parser:** `AIPParserFactory.get_parser('EGC', 'html')` → `EGCAIPParser`
- **Procedure Parser:** `ProcedureParserFactory.get_parser('EGC')` → `EGCProcedureParser`
- **Source Name:** `uk_eaip_html`

### Return Value Examples

**find_available_airports():**
```python
['EGAA', 'EGBB', 'EGCC', 'EGGD', 'EGKK', 'EGLL', ...]
```

**fetch_airport_aip('EGLL'):**
```python
{
    'icao': 'EGLL',
    'authority': 'EGC',
    'parsed_data': {
        # Parsed airport data from EGCAIPParser
        'runways': [...],
        'frequencies': [...],
        # ... other AIP fields
    }
}
```

**fetch_procedures('EGLL'):**
```python
[
    {
        'name': 'ILS RWY 09L',
        'type': 'approach',
        'approach_type': 'ILS',
        'runway_ident': '09L',
        'runway_number': 9,
        'runway_letter': 'L',
        # ... other procedure fields
    },
    # ... more procedures
]
```

---

## Reusable Patterns for New Countries

### Pattern 1: Simple Link Pattern Matching (France-style)
**Use when:** Index page contains direct links to airport pages

**Steps:**
1. Fetch index page
2. Parse HTML with BeautifulSoup
3. Find all `<a>` tags
4. Match href against regex pattern: `{COUNTRY_PREFIX}-AD-2\.({ICAO_PATTERN})-{LANG}\.html`
5. Extract ICAO from capture group
6. Build absolute airport URL

**Example Pattern:**
```regex
FR-AD-2\.(LF[A-Z]{2})-fr-FR\.html
```

### Pattern 2: Structured HTML Parsing (UK-style)
**Use when:** Index page has structured divs/sections for airports

**Steps:**
1. Fetch index page
2. Parse HTML with BeautifulSoup
3. Find container div (e.g., `id="ADdetails"`)
4. Find airport-specific divs (e.g., `id=re.compile(r'AD-2\.EG[A-Z]{2}details')`)
5. Within each airport div, find links
6. Match href against regex pattern
7. Extract ICAO and build URL

### Pattern 3: Frameset Handling (France-style)
**Use when:** Index page uses framesets

**Steps:**
1. Check for `<frameset>` element
2. If found, identify target frame (e.g., `name='eAISNavigationBase'`)
3. Fetch frame source URL
4. Recursively parse frame content (may also be frameset)
5. Continue until actual content page is found
6. Apply link pattern matching on final content

### URL Construction Patterns

**Pattern A: Simple AIRAC Date (UK-style)**
```
{BASE_URL}/{airac_date}-AIRAC/{path}
```

**Pattern B: Dual Date Structure (France-style)**
```
{BASE_URL}/eAIP_{day}_{mon}_{year}/{COUNTRY}/AIRAC-{year}-{mm}-{dd}/{path}
```
- Requires both eAIP date and AIRAC date
- eAIP date uses month abbreviation (JAN, FEB, etc.)
- AIRAC date uses numeric month (01, 02, etc.)

**Pattern C: Single Date with Formatting**
```
{BASE_URL}/{formatted_date}/{path}
```
- Format date according to country's convention
- Examples: `YYYY-MM-DD`, `DD-MMM-YYYY`, etc.

### Common Implementation Checklist

When adding a new country web source:

- [ ] Identify root URL
- [ ] Determine URL structure pattern (A, B, or C)
- [ ] Identify index page path
- [ ] Identify airport page path pattern
- [ ] Determine airport discovery method (Pattern 1, 2, or 3)
- [ ] Create regex pattern for airport links
- [ ] Identify authority code
- [ ] Verify parser exists: `AIPParserFactory.get_parser(authority, 'html')`
- [ ] Verify procedure parser exists: `ProcedureParserFactory.get_parser(authority)`
- [ ] Test airport discovery
- [ ] Test airport data fetching
- [ ] Test procedure extraction
- [ ] Document in this file

---

## Notes

- All sources inherit from `CachedSource` for file-based caching
- Cache validity is 7 days by default
- All sources implement `SourceInterface` for consistent API
- Parsers are authority-specific and registered via factories
- Airport discovery may require handling framesets, redirects, or complex HTML structures
- Some countries may require additional authentication or headers

## Belgium eAIP

### Human Access URL

```
https://ops.skeyes.be/html/belgocontrol_static/eaip/eAIP_Main/html/index-en-GB.html
```

## Sweden eAIP

### Human Access URL

```
https://aro.lfv.se/content/eaip/default_offline.html
```

## Norway eAIP

### Human Access URL

```
https://aim-prod.avinor.no/no/AIP/View/Index/147/history-no-NO.html
```

## Spain eAIP

### Human Access URL

```
https://aip.enaire.es/aip/aip-en.html
```