"""Weather analysis: flight categories, wind components, TAF matching."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from math import cos, sin, radians
from typing import Optional, List, Dict, Iterable

from euro_aip.briefing.weather.models import (
    WeatherReport,
    FlightCategory,
    WindComponents,
)

# Weather codes worth calling out in a briefing line: thunderstorms, fog,
# freezing precipitation, snow, hail/graupel, ice pellets, squalls, funnel cloud.
# Matched as substrings so descriptor/intensity variants (VCTS, +TSRA, FZFG,
# BCFG, SHSN) all qualify.
SIGNIFICANT_WEATHER_CODES = ("TS", "FG", "FZ", "SN", "GR", "GS", "PL", "SQ", "FC")
SIGNIFICANT_CLOUD_TYPES = ("CB", "TCU")


@dataclass
class TafConditions:
    """
    What a TAF forecasts for one instant, read the way a pilot reads it.

    Attributes:
        check_time: The instant these conditions are for.
        prevailing: The main body with every BECMG/FM group that has taken
            effect laid over it. A BECMG still inside its transition period
            counts as the worse of its before and after states. Synthesized —
            ``trends`` is empty.
        prevailing_change: The latest BECMG/FM group behind ``prevailing``, or
            None when the main body applies unchanged.
        temporary: TEMPO/PROB/INTER groups valid at ``check_time``, each laid
            over ``prevailing`` so a group that only states weather still has
            a flight category. Each keeps its group's ``trend_type``,
            ``probability`` and validity.
        significant_weather: Significant weather codes, then CB/TCU cloud
            types, from the prevailing and temporary conditions (first seen,
            no duplicates).
    """

    check_time: datetime
    prevailing: WeatherReport
    prevailing_change: Optional[WeatherReport] = None
    temporary: List[WeatherReport] = field(default_factory=list)
    significant_weather: List[str] = field(default_factory=list)

    @property
    def worst_temporary(self) -> Optional[WeatherReport]:
        """The temporary group with the worst flight category (first listed on ties)."""
        worst = None
        for group in self.temporary:
            if group.flight_category is None:
                continue
            if worst is None or group.flight_category < worst.flight_category:
                worst = group
        return worst

    @property
    def temporary_is_worse(self) -> bool:
        """Whether a temporary group brings a strictly worse category than prevailing."""
        worst = self.worst_temporary
        if worst is None:
            return False
        prevailing = self.prevailing.flight_category
        return prevailing is None or worst.flight_category < prevailing

    @property
    def flight_category(self) -> Optional[FlightCategory]:
        """The worse of the prevailing and temporary flight categories."""
        if self.temporary_is_worse:
            return self.worst_temporary.flight_category
        return self.prevailing.flight_category


class WeatherAnalyzer:
    """
    Aviation weather analysis functions.

    All methods are static/classmethod — pure functions with no state.

    Ported from rzflight-save/python/weather/weather.py with safe replacements
    for eval() and subprocess calls.
    """

    @staticmethod
    def flight_category(report: WeatherReport) -> Optional[FlightCategory]:
        """
        Determine flight category from ceiling and visibility.

        Uses FAA thresholds:
            LIFR:  visibility < 1 SM  or  ceiling < 500 ft
            IFR:   1 <= vis < 3 SM    or  500 <= ceiling < 1000 ft
            MVFR:  3 <= vis <= 5 SM   or  1000 <= ceiling <= 3000 ft
            VFR:   visibility > 5 SM  and ceiling > 3000 ft

        The worst condition (ceiling or visibility) determines the category.

        Args:
            report: WeatherReport with visibility_sm and ceiling_ft

        Returns:
            FlightCategory or None if insufficient data
        """
        vis_sm = report.visibility_sm
        ceiling = report.ceiling_ft

        # CAVOK implies VFR
        if report.cavok:
            return FlightCategory.VFR

        if vis_sm is None and ceiling is None:
            return None

        # Determine category from visibility
        vis_cat = None
        if vis_sm is not None:
            if vis_sm < 1:
                vis_cat = FlightCategory.LIFR
            elif vis_sm < 3:
                vis_cat = FlightCategory.IFR
            elif vis_sm <= 5:
                vis_cat = FlightCategory.MVFR
            else:
                vis_cat = FlightCategory.VFR

        # Determine category from ceiling
        ceil_cat = None
        if ceiling is not None:
            if ceiling < 500:
                ceil_cat = FlightCategory.LIFR
            elif ceiling < 1000:
                ceil_cat = FlightCategory.IFR
            elif ceiling <= 3000:
                ceil_cat = FlightCategory.MVFR
            else:
                ceil_cat = FlightCategory.VFR

        # Return the worst (lowest) category
        if vis_cat is not None and ceil_cat is not None:
            return min(vis_cat, ceil_cat)
        return vis_cat if vis_cat is not None else ceil_cat

    @staticmethod
    def wind_components(
        report: WeatherReport,
        runway_heading: int,
        runway_ident: str = "",
    ) -> Optional[WindComponents]:
        """
        Calculate wind components for a runway.

        Headwind is positive when wind is from ahead.
        Crosswind is positive when wind is from the right.

        Handles:
        - Basic headwind/crosswind trigonometry
        - Gust components
        - Variable wind worst-case crosswind

        Args:
            report: WeatherReport with wind data
            runway_heading: Runway heading in degrees (0-360)
            runway_ident: Runway identifier (e.g., "27L")

        Returns:
            WindComponents or None if wind data unavailable
        """
        if report.wind_speed is None:
            return None

        wind_dir = report.wind_direction
        wind_speed = report.wind_speed

        # Calm wind
        if wind_speed == 0:
            return WindComponents(
                runway_ident=runway_ident,
                runway_heading=runway_heading,
                headwind=0.0,
                crosswind=0.0,
                crosswind_direction="",
                max_crosswind=0.0,
            )

        # Variable wind (no direction) — use full speed as worst-case crosswind
        if wind_dir is None:
            return WindComponents(
                runway_ident=runway_ident,
                runway_heading=runway_heading,
                headwind=0.0,
                crosswind=float(wind_speed),
                crosswind_direction="",
                max_crosswind=float(wind_speed),
            )

        headwind, crosswind = _compute_components(wind_dir, runway_heading, wind_speed)

        # Determine crosswind direction
        relative = (wind_dir - runway_heading) % 360
        if relative > 180:
            xwind_dir = "left"
        else:
            xwind_dir = "right"

        # Max crosswind starts with basic crosswind
        max_crosswind = abs(crosswind)

        # Variable wind range — compute worst-case crosswind
        if report.wind_variable_from is not None and report.wind_variable_to is not None:
            max_crosswind = _worst_case_crosswind(
                report.wind_variable_from,
                report.wind_variable_to,
                runway_heading,
                wind_speed,
                max_crosswind,
            )

        # Gust components
        gust_hw = None
        gust_xw = None
        if report.wind_gust is not None:
            gust_hw, gust_xw = _compute_components(wind_dir, runway_heading, report.wind_gust)
            # Gust worst-case crosswind
            gust_max_xw = abs(gust_xw)
            if report.wind_variable_from is not None and report.wind_variable_to is not None:
                gust_max_xw = _worst_case_crosswind(
                    report.wind_variable_from,
                    report.wind_variable_to,
                    runway_heading,
                    report.wind_gust,
                    gust_max_xw,
                )
            max_crosswind = max(max_crosswind, gust_max_xw)

        return WindComponents(
            runway_ident=runway_ident,
            runway_heading=runway_heading,
            headwind=headwind,
            crosswind=crosswind,
            crosswind_direction=xwind_dir,
            gust_headwind=gust_hw,
            gust_crosswind=gust_xw,
            max_crosswind=max_crosswind,
        )

    @staticmethod
    def wind_components_for_runways(
        report: WeatherReport,
        runways: Dict[str, int],
    ) -> Dict[str, WindComponents]:
        """
        Calculate wind components for multiple runways.

        Args:
            report: WeatherReport with wind data
            runways: Dict mapping runway ident to heading
                     e.g., {"27L": 270, "09R": 90}

        Returns:
            Dict mapping runway ident to WindComponents
        """
        result = {}
        for ident, heading in runways.items():
            wc = WeatherAnalyzer.wind_components(report, heading, ident)
            if wc is not None:
                result[ident] = wc
        return result

    @staticmethod
    def compare_categories(
        actual: FlightCategory,
        forecast: FlightCategory,
    ) -> str:
        """
        Compare actual vs forecast flight categories.

        Args:
            actual: Actual (observed) category
            forecast: Forecast category

        Returns:
            "exact" if same, "worse" if actual is worse, "better" if actual is better
        """
        if actual == forecast:
            return "exact"
        elif actual < forecast:
            return "worse"
        else:
            return "better"

    @staticmethod
    def find_applicable_taf(
        taf: WeatherReport,
        check_time: datetime,
    ) -> Optional[WeatherReport]:
        """
        Find the most specific applicable TAF trend for a given time.

        Checks TEMPO/BECMG trends in reverse order (last matching wins).
        Falls back to the base TAF if no trend applies.

        Prefer :meth:`taf_conditions_at` for "what does this TAF say at T":
        this method does not check that the TAF itself is valid at
        ``check_time`` (an expired TAF comes back as its base), and the
        last-listed group wins even when it carries no ceiling or visibility.

        Args:
            taf: TAF WeatherReport with trends
            check_time: Time to check

        Returns:
            The applicable WeatherReport (trend or base TAF)
        """
        applicable = WeatherAnalyzer.applicable_trends(taf, check_time)
        if applicable:
            return applicable[-1]
        return taf

    @staticmethod
    def applicable_trends(
        taf: WeatherReport,
        check_time: datetime,
    ) -> List[WeatherReport]:
        """
        Find all TAF trends valid at a given time.

        Args:
            taf: TAF WeatherReport with trends
            check_time: Time to check

        Returns:
            List of applicable trends, in order
        """
        result = []
        for trend in taf.trends:
            if _validity_contains(trend, check_time):
                result.append(trend)
        return result

    @staticmethod
    def taf_covers(taf: WeatherReport, check_time: datetime) -> bool:
        """
        Whether the TAF's own validity period contains ``check_time``.

        aviationweather.gov returns an airport's most recent TAF however old
        it is, so a small field that stopped issuing hands back a TAF from
        days ago. A TAF whose validity could not be parsed does not cover any
        time — there is nothing to vouch for it with.
        """
        if taf.validity_start is None or taf.validity_end is None:
            return False
        return _validity_contains(taf, check_time)

    @staticmethod
    def taf_conditions_at(
        taf: WeatherReport,
        check_time: datetime,
    ) -> Optional[TafConditions]:
        """
        Read a TAF at one instant: prevailing, temporary groups, significant weather.

        Returns None when the TAF is not valid at ``check_time``.

        Prevailing is the main body with BECMG/FM groups applied in time
        order: an FM group replaces the forecast from its start, a BECMG group
        applies fully once its period has ended, and while it is in progress
        the worse of the before/after states is used — the change may or may
        not have happened yet. Temporary (TEMPO/PROB/INTER) groups are laid
        over prevailing, so fields a group does not state are inherited.

        Args:
            taf: TAF WeatherReport with trends
            check_time: Time to read the TAF for (timezone-aware, like the
                parsed validity)

        Returns:
            TafConditions, or None when the TAF does not cover ``check_time``
        """
        if not WeatherAnalyzer.taf_covers(taf, check_time):
            return None

        prevailing = replace(taf, trends=[], trend_type=None, probability=None)
        prevailing.flight_category = WeatherAnalyzer.flight_category(prevailing)
        prevailing_change = None
        changes = sorted(
            (
                g for g in taf.trends
                if not _is_temporary(g)
                and g.validity_start is not None
                and g.validity_start <= check_time
            ),
            key=lambda g: g.validity_start,
        )
        for group in changes:
            is_fm = (group.trend_type or "").upper() == "FM"
            after = _overlay(prevailing, group, restates_weather=is_fm)
            in_transition = (
                not is_fm
                and group.validity_end is not None
                and check_time < group.validity_end
            )
            prevailing = _worse_of(prevailing, after) if in_transition else after
            prevailing_change = group

        temporary = []
        for group in taf.trends:
            if _is_temporary(group) and _validity_contains(group, check_time):
                state = _overlay(prevailing, group)
                temporary.append(replace(
                    state,
                    raw_text="",
                    trend_type=group.trend_type,
                    probability=group.probability,
                    validity_start=group.validity_start,
                    validity_end=group.validity_end,
                ))

        return TafConditions(
            check_time=check_time,
            prevailing=prevailing,
            prevailing_change=prevailing_change,
            temporary=temporary,
            significant_weather=_significant_weather([prevailing] + temporary),
        )

    @staticmethod
    def trend_label(report: WeatherReport) -> Optional[str]:
        """
        Human label for a change group: "TEMPO", "PROB30 TEMPO", "PROB40", "BECMG", "FM".

        Returns None for a main body (no trend type, no probability).
        """
        trend_type = (report.trend_type or "").upper()
        if report.probability is not None:
            if trend_type in ("", "PROB"):
                return f"PROB{report.probability}"
            return f"PROB{report.probability} {trend_type}"
        return trend_type or None


# --- Module-level helpers (pure functions) ---

def _compute_components(
    wind_dir: int,
    runway_heading: int,
    speed: float,
) -> tuple:
    """
    Compute headwind and crosswind components.

    Returns:
        (headwind, crosswind) where positive headwind = from ahead,
        positive crosswind = from the right.
    """
    angle = abs(wind_dir - runway_heading)
    if angle > 180:
        angle = 360 - angle
    headwind = round(speed * cos(radians(angle)), 1)
    crosswind = round(speed * sin(radians(angle)), 1)

    # Determine sign: crosswind positive = from right
    relative = (wind_dir - runway_heading) % 360
    if relative > 180:
        crosswind = -crosswind  # from left

    return headwind, crosswind


def _worst_case_crosswind(
    var_from: int,
    var_to: int,
    runway_heading: int,
    speed: float,
    current_max: float,
) -> float:
    """
    Compute worst-case crosswind considering variable wind directions.

    Checks if perpendicular angles fall within the variable range,
    and also checks the extremes.
    """
    max_xw = current_max

    # Normalize variable range
    min_dir = var_from
    max_dir = var_to
    if max_dir < min_dir:
        max_dir += 360

    # Check both perpendicular directions
    for perp in [(runway_heading + 90) % 360, (runway_heading + 270) % 360]:
        norm_perp = perp
        if norm_perp < min_dir:
            norm_perp += 360
        if min_dir <= norm_perp <= max_dir:
            # Perpendicular is within variable range — full crosswind
            max_xw = max(max_xw, abs(speed))
            return max_xw

    # Check extremes
    for test_dir in [min_dir, max_dir]:
        angle = abs(test_dir % 360 - runway_heading)
        if angle > 180:
            angle = 360 - angle
        test_xw = abs(speed * sin(radians(angle)))
        max_xw = max(max_xw, test_xw)

    return max_xw


def _validity_contains(trend: WeatherReport, check_time: datetime) -> bool:
    """
    Check if a TAF trend's validity period contains the given time.

    Handles month-crossing cases.
    """
    start = trend.validity_start
    end = trend.validity_end

    if start is None:
        return False

    if end is None:
        # FM trend: valid from start until superseded (always applicable after start)
        return check_time >= start

    # Handle month-crossing
    if end < start:
        if check_time < start:
            # Move start back one month
            month = start.month - 1
            year = start.year
            if month < 1:
                month = 12
                year -= 1
            try:
                start = start.replace(year=year, month=month)
            except ValueError:
                return False
        else:
            # Move end forward one month
            month = end.month + 1
            year = end.year
            if month > 12:
                month = 1
                year += 1
            try:
                end = end.replace(year=year, month=month)
            except ValueError:
                return False

    return start <= check_time <= end


def _is_temporary(group: WeatherReport) -> bool:
    """A TEMPO / PROB / INTER group — a temporary deviation, not a prevailing change."""
    trend_type = (group.trend_type or "").upper()
    return (
        "TEMPO" in trend_type
        or "INTER" in trend_type
        or trend_type.startswith("PROB")
        or group.probability is not None
    )


def _overlay(
    state: WeatherReport,
    group: WeatherReport,
    restates_weather: bool = False,
) -> WeatherReport:
    """
    Lay a change group over a state: whatever the group states replaces the state's.

    Fields the group leaves out carry over — a wind-only BECMG keeps the
    cloud. Weather likewise carries over unless ``restates_weather`` (an FM
    group restates the whole forecast). The parser does not surface ``NSW``,
    so weather a BECMG ends can linger here: the conservative direction.
    """
    changes: Dict = {}
    if group.wind_speed is not None:
        changes.update(
            wind_direction=group.wind_direction,
            wind_speed=group.wind_speed,
            wind_gust=group.wind_gust,
            wind_variable_from=group.wind_variable_from,
            wind_variable_to=group.wind_variable_to,
            wind_unit=group.wind_unit,
        )
    if group.cavok:
        changes.update(
            cavok=True,
            visibility_meters=group.visibility_meters or 10000,
            visibility_sm=group.visibility_sm,
            clouds=[],
            ceiling_ft=None,
            weather_conditions=[],
        )
    else:
        if group.visibility_meters is not None or group.visibility_sm is not None:
            changes.update(
                visibility_meters=group.visibility_meters,
                visibility_sm=group.visibility_sm,
                cavok=False,
            )
        if group.clouds:
            changes.update(clouds=list(group.clouds), ceiling_ft=group.ceiling_ft, cavok=False)
        if group.weather_conditions or restates_weather:
            changes["weather_conditions"] = list(group.weather_conditions)
    result = replace(state, **changes)
    result.flight_category = WeatherAnalyzer.flight_category(result)
    return result


def _effective_ceiling(state: WeatherReport) -> float:
    if state.cavok or state.ceiling_ft is None:
        return float("inf")
    return state.ceiling_ft


def _effective_visibility(state: WeatherReport) -> Optional[float]:
    if state.cavok:
        return max(state.visibility_meters or 0, 9999)
    return state.visibility_meters


def _worse_of(before: WeatherReport, after: WeatherReport) -> WeatherReport:
    """
    Field-wise worse of two states — a BECMG group still inside its transition.

    The lower ceiling (with its cloud layers) and the lower visibility win;
    weather is the union; wind follows ``after``.
    """
    changes: Dict = {
        "cavok": bool(before.cavok and after.cavok),
        "weather_conditions": list(dict.fromkeys(
            list(before.weather_conditions) + list(after.weather_conditions)
        )),
    }
    if _effective_ceiling(before) < _effective_ceiling(after):
        changes.update(clouds=list(before.clouds), ceiling_ft=before.ceiling_ft)
    vis_before, vis_after = _effective_visibility(before), _effective_visibility(after)
    if vis_before is not None and (vis_after is None or vis_before < vis_after):
        changes.update(
            visibility_meters=before.visibility_meters,
            visibility_sm=before.visibility_sm,
        )
    result = replace(after, **changes)
    result.flight_category = WeatherAnalyzer.flight_category(result)
    return result


def _significant_weather(states: Iterable[WeatherReport]) -> List[str]:
    """Significant weather codes, then CB/TCU cloud types, first seen and de-duplicated."""
    states = list(states)
    found: List[str] = []
    for state in states:
        for code in state.weather_conditions:
            if code not in found and any(s in code for s in SIGNIFICANT_WEATHER_CODES):
                found.append(code)
    for state in states:
        for layer in state.clouds:
            cloud_type = layer.get("type")
            if cloud_type in SIGNIFICANT_CLOUD_TYPES and cloud_type not in found:
                found.append(cloud_type)
    return found
