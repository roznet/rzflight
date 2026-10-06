# Consumers

> Who depends on euro_aip / RZFlight, what each one uses, and what breaks them

## Intent

rzflight is a library. Most changes are driven by a consumer (an issue
`roznet/<repo>#N`), and most breakage shows up in a consumer, not here. This doc is
the map for answering "who calls this, and what do they need?" before changing public
API, parser output or the database schema. Grep the consumer checkouts for the actual
call sites; this doc says where to look.

All checkouts live under `~/Developer/public/`. Repos with worktrees have their
default branch at `<repo>/main/`.

## The two roles

### Builds the data — flyfun-apps

`flyfun-apps/main/` pins `euro-aip>=…` in `requirements.txt`.

- **Producer of `airports.db`.** `tools/aipexport.py` fetches AIP sources (France /
  UK / Norway web, autorouter) through `euro_aip` and writes them with
  `DatabaseStorage`. `storage.airac_date` is set before `save_model()`, so the
  `*_changes` tables and `airac_updates` carry the AIRAC cycle.
  `tools/data_update.py` orchestrates a run per AIRAC cycle and rebuilds the derived
  DBs (`ga_notifications.db`, `ga_persona.db`) from `airports.db`. Its pipeline doc:
  `designs/DATA_UPDATE_PIPELINE.md` in that repo.
- **Query API / models** in its web app and MCP server (`shared/`: filters,
  prioritisation, GA friendliness).
- **RZFlight Swift** in its iOS app (`app/FlyFunEuroAIP`): decodes the web API's JSON
  into RZFlight models and reads `airports.db` offline.

Sensitive to: sources, `DatabaseStorage`, the schema, the model and query API, and
the Codable keys of the Swift models.

### Uses the library at runtime — flyfun-weather

`flyfun-weather/main/` pins `euro-aip>=…` in `pyproject.toml`.

- Briefing and weather: `WeatherParser`, `WeatherAnalyzer`, `WeatherReport`,
  `RouteWeatherService`, `RouteSigmetService`, `AvWxSource`, `AutorouterGrametSource`.
- Routes and flight plans: `FlightExchange`, `parse_icao_fpl`, `Route`, `NavPoint`,
  `RouteResolver`.
- Misc: `sun_events`, `AutorouterCredentialManager`, `is_icao_coordinate`.
- Reads `airports.db` through `DatabaseStorage` (`AIRPORTS_DB`).

Sensitive to: parser output for the same input (it grades weather from it), the
shape of briefing/weather results, and network-source failure behaviour.

## Other consumers

- **flyfun-forms** (`flyfun-forms/main/`, `pyproject.toml`): borders and customs —
  `crossing_requirements`, `CustomInterpreter`, customs contacts
  (`scripts/sync_aip_emails.py`) — and RZFlight Swift in its app.
- **flightlogstats** (`flightlogstats/`): RZFlight Swift in the iOS app, reading a
  bundled `nav.db` cut from the flyfun-apps database by `python/make_nav_db.py`;
  Python `euro_aip` in `python/`.

The list is not exhaustive. When in doubt, grep `~/Developer/public/*/` for
`euro_aip` / `import RZFlight`.

## The `airports.db` schema is a cross-language contract

Python `DatabaseStorage` writes it (in flyfun-apps' pipeline). Swift
`Airport(db:ident:)`, `KnownAirports` and `KnownWaypoints` read it in the apps,
directly or via a cut such as flightlogstats' `nav.db`. So a renamed or dropped
column, a changed format or meaning of a stored value, or a change in how
`*_changes` / `airac_updates` are recorded breaks readers in the **other** language.
This already happened once: the `ident` / `airport_ident` rename left an older
bundled DB unreadable by current RZFlight.

When changing the schema: update the Swift readers in the same PR (or flag it as
breaking), and say which DBs must be rebuilt (flyfun-apps `airports.db`, then
anything cut from it).

## Gotchas

- **Pins are lower bounds and lag.** Each consumer pins `euro-aip>=<the version it
  needed>`, so a consumer may still run an older release. A fix isn't live for a
  consumer until it is released *and* that consumer is updated.
- **Issue references.** Refer to a consumer's issue as `roznet/<repo>#N` with no
  closing keyword — a `Closes` would close it before the consumer has picked up the
  release.
- **Swift consumers track `main`, not tags.** Every app's Xcode project references
  `https://github.com/roznet/rzflight` with `kind = branch; branch = main`, and its
  `Package.resolved` pins whatever `main` revision it last resolved. So for Swift,
  **merging to `main` is the release**: a breaking Swift change reaches each app the
  next time it updates packages, with no version signal. The bare `1.x.y` tags
  (`releasing.md`) are markers only; no consumer reads them today.
