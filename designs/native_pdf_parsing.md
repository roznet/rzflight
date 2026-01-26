# Native iOS PDF Parsing

> Swift-native parsing for ForeFlight PDF briefings using PDFKit

## Intent

Provide native iOS parsing capability that:
- Eliminates API dependency for PDF briefing parsing
- Works offline on iOS devices
- Produces the same `Briefing` model as Python parsing
- Mirrors Python `ForeFlightSource` logic for consistency

**What this enables**: Fully offline PDF briefing parsing on iOS without server round-trips.

## Architecture

```
Sources/RZFlight/Briefing/
├── Briefing.swift           # Container model (existing)
├── Notam.swift              # NOTAM model (existing, extended)
├── NotamCategory.swift      # Category enum (existing)
├── Route.swift              # Route model (existing, extended)
├── Notam+Queries.swift      # Filtering extensions (existing)
├── NotamParser.swift        # NEW: NOTAM text parsing
└── ForeFlightParser.swift   # NEW: PDF extraction + parsing
```

**Data flow:**
```
iOS App                           Swift Package
───────                           ─────────────
PDF file/data
     │
     ▼
ForeFlightParser.parse(url:)
     │
     ├── PDFKit text extraction
     │   ├── Two-column layout handling
     │   └── Page-by-page processing
     │
     ├── Route extraction
     │   ├── Departure/Destination patterns
     │   ├── Alternates extraction
     │   └── Waypoints extraction
     │
     └── NOTAM extraction
         ├── Section finding
         ├── NOTAM splitting
         └── NotamParser.parse() per NOTAM
                  │
                  ▼
              Briefing model
```

## Usage Examples

### Parse from File URL
```swift
let parser = ForeFlightParser()
let briefing = try parser.parse(url: pdfFileURL)

// Access route
print(briefing.route?.departure)  // "LFPG"
print(briefing.route?.destination)  // "EGLL"

// Filter NOTAMs
let runwayNotams = briefing.notams
    .forAirport("LFPG")
    .runwayRelated()
```

### Parse from Raw Data
```swift
// From downloaded PDF data
let pdfData: Data = ...
let briefing = try parser.parse(data: pdfData)

// From pre-extracted text (if text extraction done elsewhere)
let text: String = ...
let briefing = parser.parse(text: text)
```

### Error Handling
```swift
do {
    let briefing = try parser.parse(url: url)
} catch ForeFlightParser.ParserError.fileNotFound(let url) {
    print("File not found: \(url)")
} catch ForeFlightParser.ParserError.invalidPDF {
    print("Invalid PDF format")
} catch ForeFlightParser.ParserError.textExtractionFailed {
    print("Could not extract text from PDF")
} catch ForeFlightParser.ParserError.noContent {
    print("PDF appears empty")
}
```

## Key Components

### ForeFlightParser

Main entry point for PDF parsing.

| Method | Description |
|--------|-------------|
| `parse(url:)` | Parse PDF from file URL |
| `parse(data:)` | Parse PDF from raw Data |
| `parse(text:)` | Parse from pre-extracted text |

**PDF Text Extraction:**
- Uses `PDFKit.PDFDocument` for PDF handling
- Detects landscape pages (common in ForeFlight) as two-column
- Uses `PDFPage.selection(for:)` to extract columns separately
- Concatenates left column then right column for proper reading order

### NotamParser

Static parser for individual NOTAM text blocks.

| Method | Description |
|--------|-------------|
| `parse(_:source:)` | Parse single NOTAM text |
| `parseMany(_:source:)` | Parse text containing multiple NOTAMs |

**Extracted Fields:**
- NOTAM ID, series, number, year
- Q-line: FIR, Q-code, traffic type, purpose, scope, altitude limits, coordinates, radius
- A-line: Location
- B/C lines: Effective times
- D-line: Schedule
- E-line: Message
- F/G lines: Altitude limits (override Q-line if present)

## Implementation Details

### Two-Column Layout Handling

ForeFlight briefings often use landscape two-column layouts for NOTAM pages:

```swift
// Detect landscape orientation
if page.bounds.width > page.bounds.height {
    // Extract left column first
    let leftRect = CGRect(x: 0, y: 0, width: width/2, height: height)
    let leftText = page.selection(for: leftRect)?.string ?? ""

    // Then right column
    let rightRect = CGRect(x: width/2, y: 0, width: width/2, height: height)
    let rightText = page.selection(for: rightRect)?.string ?? ""

    return leftText + "\n\n" + rightText
}
```

### NOTAM Section Detection

Multiple patterns to find NOTAM sections:

1. **Explicit headers**: `"LFPG NOTAMs"` or `"NOTAMs for LFPG"`
2. **Standalone ICAO headers**: `"LFPG"` on its own line followed by NOTAM content
3. **FDC NOTAMs**: `"FDC NOTAMs"` section
4. **Fallback**: Any text containing NOTAM ID patterns

### NOTAM Splitting

Smart splitting that avoids breaking on referenced NOTAMs:

```swift
// Only split on IDs that START a new NOTAM (followed by NOTAM[NRC])
// Not on referenced NOTAMs like "NOTAMR E1234/25"
let startPattern = #"([A-Z]\d{4}/\d{2})\s*NOTAM[NRC]"#
```

### Q-Code Category Mapping

Maps Q-code prefixes to `NotamCategory`:

| Prefix | Category |
|--------|----------|
| MR | runway |
| MX, MA | movementArea |
| LR, LL, LX | lighting |
| NA, NV, ND, NI, NL, NM, NB | navigation |
| CO | communication |
| FA, AR, AH, AL, AT, AX, RD, RT | airspace |
| OB, OL | obstacle |
| PI, PA, PD, PS, PT | procedure |
| SE, SA, SN, SV | services |
| WA, WE, WM, WP, WU, WV, WZ | warning |

## Comparison with Python Implementation

| Aspect | Python | Swift |
|--------|--------|-------|
| PDF Library | pdfplumber | PDFKit |
| Regex | re module | NSRegularExpression |
| Two-column | page.crop() | PDFPage.selection(for:) |
| Output | Briefing dataclass | Briefing struct |
| JSON | to_json() / from_json() | Codable |

**Functional Parity**: The Swift implementation mirrors the Python logic for:
- Route extraction patterns
- NOTAM section finding
- NOTAM splitting (including NOTAMR/C reference handling)
- Q-line parsing
- Altitude limit parsing (F/G lines, FL conversion)
- Datetime parsing (YYMMDDHHMM format)

## Key Choices

| Decision | Rationale |
|----------|-----------|
| PDFKit over Core Graphics | Higher-level API, simpler text extraction |
| NSRegularExpression | Foundation native, consistent with Python re |
| Static NotamParser | Matches Python class methods pattern |
| Memberwise initializers added | Enable direct construction without JSON |
| Sendable conformance | Thread-safe for async operations |

## Patterns

- **Two-pass extraction**: First extract text (PDFKit), then parse (regex)
- **Fallback patterns**: Multiple regex patterns tried in order of reliability
- **Section-based parsing**: Find sections first, then parse NOTAMs within
- **Deduplication**: Remove duplicate NOTAMs by ID

## Gotchas

- **PDFKit text quality**: Depends on how PDF was generated; ForeFlight PDFs are digitally created so work well
- **Column detection**: Simple width > height check; may need refinement for unusual layouts
- **Coordinate system**: PDF coordinates are bottom-left origin; PDFKit handles this
- **Optional fields**: Many NOTAM fields may be nil; all made optional

## Testing

Recommended tests:
1. Parse sample ForeFlight PDF, verify route extraction
2. Parse PDF with two-column layout, verify text ordering
3. Parse various NOTAM formats (full Q-line, abbreviated, etc.)
4. Verify deduplication of repeated NOTAMs
5. Compare output with Python parser on same input

## References

- Python source: `euro_aip/euro_aip/briefing/sources/foreflight.py`
- Python NOTAM parser: `euro_aip/euro_aip/briefing/parsers/notam_parser.py`
- Swift models: `Sources/RZFlight/Briefing/`
- PDFKit docs: [Apple Developer](https://developer.apple.com/documentation/pdfkit)
