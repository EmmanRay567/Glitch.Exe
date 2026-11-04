"""
services/sports_service.py

Live data for GLITCH's Sports Nexus: records, standings, schedule,
results, injuries and stat leaders for your favourite teams.

Source: ESPN's public JSON endpoints (no API key). They're unofficial,
so every field is read defensively: if ESPN changes something, that
panel shows "no data" instead of GLITCH crashing. Results are cached
in data/sports_cache.json so the page opens instantly and still works
offline.

Teams live in data/sports_teams.json (created on first run). Add or
remove teams there; "abbr" is the ESPN team abbreviation.
"""

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Signal,
)


SITE = "https://site.api.espn.com/apis/site/v2/sports"

CORE = "https://sports.core.api.espn.com/v2/sports"

DEFAULT_TEAMS = [
    {
        "key": "JAX",
        "sport": "football",
        "league": "nfl",
        "abbr": "jax",
        "name": "Jacksonville Jaguars",
        "nicknames": ["jaguars", "jags", "jacksonville"],
    },
    {
        "key": "BOS",
        "sport": "basketball",
        "league": "nba",
        "abbr": "bos",
        "name": "Boston Celtics",
        "nicknames": ["celtics", "celts", "c's"],
    },
    {
        "key": "NE",
        "sport": "football",
        "league": "nfl",
        "abbr": "ne",
        "name": "New England Patriots",
        "nicknames": ["patriots", "pats", "new england"],
    },
]

# Fallback colours if ESPN doesn't send any (hex, no '#').
FALLBACK_COLORS = {
    "JAX": ("006778", "d7a22a"),
    "BOS": ("007a33", "ba9653"),
    "NE": ("c60c30", "b0b7bc"),
}


def _get(data, *path, default=None):

    """Safe nested lookup: _get(d, "team", "record", "items", 0)."""

    for key in path:

        try:

            data = data[key]

        except (KeyError, IndexError, TypeError):

            return default

    return data if data is not None else default


def _score(competitor):

    score = competitor.get("score")

    if isinstance(score, dict):

        return score.get("displayValue") or (
            str(int(score["value"])) if score.get("value") is not None else ""
        )

    return str(score or "")


class SportsService(QObject):

    # (team key, normalized team dict)
    team_updated = Signal(str, dict)

    # Short status text for the HUD ("SYNCING", "LIVE", "OFFLINE ...").
    status_changed = Signal(str)

    REFRESH_SECONDS = 10 * 60

    def __init__(self, data_dir="data"):

        super().__init__()

        self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.teams_path = self.data_dir / "sports_teams.json"

        self.cache_path = self.data_dir / "sports_cache.json"

        self.teams = self._load_teams()

        self.data = self._load_cache()

        self._lock = threading.Lock()

        self._busy = False

    # =====================================================
    # CONFIG + CACHE
    # =====================================================

    def _load_teams(self):

        try:

            if self.teams_path.exists():

                teams = json.loads(self.teams_path.read_text(encoding="utf-8"))

                if isinstance(teams, list) and teams:

                    return teams

        except Exception as error:

            print("SPORTS TEAMS LOAD ERROR:", error)

        self.teams_path.write_text(
            json.dumps(DEFAULT_TEAMS, indent=2),
            encoding="utf-8",
        )

        return list(DEFAULT_TEAMS)


    def _load_cache(self):

        try:

            if self.cache_path.exists():

                data = json.loads(self.cache_path.read_text(encoding="utf-8"))

                if isinstance(data, dict):

                    return data

        except Exception as error:

            print("SPORTS CACHE LOAD ERROR:", error)

        return {}


    def _save_cache(self):

        try:

            self.cache_path.write_text(
                json.dumps(self.data, indent=1),
                encoding="utf-8",
            )

        except Exception as error:

            print("SPORTS CACHE SAVE ERROR:", error)


    def team_keys(self):

        return [team["key"] for team in self.teams]


    def team_config(self, key):

        for team in self.teams:

            if team["key"] == key:

                return team

        return None


    def get(self, key):

        return self.data.get(key)


    def emit_cached(self):

        for key in self.team_keys():

            if key in self.data:

                self.team_updated.emit(key, self.data[key])

    # =====================================================
    # REFRESH
    # =====================================================

    def is_stale(self):

        stamps = [
            (self.data.get(key) or {}).get("updated_at", 0)
            for key in self.team_keys()
        ]

        return not stamps or time.time() - min(stamps) > self.REFRESH_SECONDS


    def refresh(self, force=False):

        """Fetch all teams in the background (no-op if fresh)."""

        if not force and not self.is_stale():

            self.emit_cached()

            return

        with self._lock:

            if self._busy:

                return

            self._busy = True

        self.status_changed.emit("SYNCING")

        threading.Thread(target=self._refresh_all, daemon=True).start()


    def _refresh_all(self):

        failures = 0

        try:

            for team in self.teams:

                try:

                    result = self._fetch_team(team)

                    self.data[team["key"]] = result

                    self.team_updated.emit(team["key"], result)

                except Exception as error:

                    failures += 1

                    print(f"SPORTS FETCH ERROR ({team.get('key')}):", error)

            self._save_cache()

        finally:

            with self._lock:

                self._busy = False

            if failures == len(self.teams):

                self.status_changed.emit("OFFLINE // SHOWING CACHE")

            elif failures:

                self.status_changed.emit("PARTIAL SYNC")

            else:

                self.status_changed.emit("LIVE")

    # =====================================================
    # HTTP
    # =====================================================

    @staticmethod
    def _json(url, timeout=8):

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 GLITCH.EXE"},
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:

            return json.loads(response.read().decode("utf-8"))

    # =====================================================
    # FETCH + NORMALIZE ONE TEAM
    # =====================================================

    def _fetch_team(self, team):

        sport = team["sport"]

        league = team["league"]

        abbr = team["abbr"]

        base = f"{SITE}/{sport}/{league}/teams/{abbr}"

        info = self._json(base)

        t = info.get("team", {})

        primary, alternate = FALLBACK_COLORS.get(team["key"], ("39ff78", "c8ffdc"))

        result = {
            "key": team["key"],
            "sport": sport,
            "league": league.upper(),
            "id": t.get("id"),
            "name": t.get("displayName") or team.get("name"),
            "short": t.get("shortDisplayName") or t.get("name") or team["key"],
            "abbr": t.get("abbreviation") or team["key"],
            "color": t.get("color") or primary,
            "alt_color": t.get("alternateColor") or alternate,
            "standing": t.get("standingSummary") or "",
            "record": "",
            "splits": {},
            "stats": {},
            "next_game": None,
            "schedule": [],
            "injuries": [],
            "leaders": [],
            "season": None,
            "errors": [],
            "updated_at": time.time(),
        }

        # ---------------- record + record stats ----------------
        for item in _get(t, "record", "items", default=[]) or []:

            kind = (item.get("type") or item.get("description") or "").lower()

            summary = item.get("summary", "")

            if kind in ("total", "overall record", "overall"):

                result["record"] = summary

                for stat in item.get("stats", []) or []:

                    name = stat.get("name")

                    value = stat.get("value")

                    if name and value is not None:

                        result["stats"][name] = value

            elif kind in ("home", "road", "away"):

                result["splits"]["away" if kind == "road" else kind] = summary

        if not result["record"]:

            result["record"] = _get(t, "record", "items", 0, "summary", default="")

        # ---------------- schedule ----------------
        try:

            schedule = self._json(f"{base}/schedule")

            result["season"] = _get(schedule, "season", "year") or _get(
                schedule, "requestedSeason", "year"
            )

            result["schedule"] = self._parse_schedule(schedule, result["abbr"])

        except Exception as error:

            result["errors"].append(f"schedule: {error}")

        upcoming = [game for game in result["schedule"] if not game["completed"]]

        if upcoming:

            result["next_game"] = upcoming[0]

        # ---------------- roster -> injuries ----------------
        try:

            roster = self._json(f"{base}/roster")

            result["injuries"] = self._parse_injuries(roster)

        except Exception as error:

            result["errors"].append(f"roster: {error}")

        # ---------------- stat leaders ----------------
        if result["id"] and result["season"]:

            try:

                result["leaders"] = self._fetch_leaders(
                    sport, league, result["id"], result["season"]
                )

            except Exception as error:

                result["errors"].append(f"leaders: {error}")

        return result


    def _parse_schedule(self, schedule, my_abbr):

        games = []

        for event in schedule.get("events", []) or []:

            competition = _get(event, "competitions", 0, default={}) or {}

            competitors = competition.get("competitors", []) or []

            me = None

            them = None

            for competitor in competitors:

                abbr = _get(competitor, "team", "abbreviation", default="")

                if abbr.upper() == my_abbr.upper():

                    me = competitor

                else:

                    them = competitor

            if me is None or them is None:

                continue

            status = _get(competition, "status", "type", default={}) or _get(
                event, "status", "type", default={}
            ) or {}

            completed = bool(status.get("completed"))

            result = ""

            if completed:

                mine = _score(me)

                theirs = _score(them)

                won = me.get("winner")

                if won is None and mine.isdigit() and theirs.isdigit():

                    won = int(mine) > int(theirs)

                outcome = "W" if won else ("T" if mine == theirs else "L")

                result = f"{outcome} {mine}-{theirs}"

            broadcast = _get(competition, "broadcasts", 0, "media", "shortName", default="") or _get(
                competition, "broadcasts", 0, "names", 0, default=""
            )

            games.append(
                {
                    "date": event.get("date", ""),
                    "label": _get(event, "week", "text", default="") or "",
                    "opponent": _get(them, "team", "abbreviation", default="?"),
                    "opponent_name": _get(them, "team", "displayName", default="")
                    or _get(them, "team", "shortDisplayName", default=""),
                    "home": me.get("homeAway") == "home",
                    "completed": completed,
                    "result": result,
                    "state": status.get("state", ""),
                    "detail": status.get("shortDetail", ""),
                    "venue": _get(competition, "venue", "fullName", default=""),
                    "broadcast": broadcast,
                }
            )

        games.sort(key=lambda game: game["date"])

        return games


    def _parse_injuries(self, roster):

        players = []

        groups = roster.get("athletes", []) or []

        for group in groups:

            if isinstance(group, dict) and "items" in group:

                players.extend(group.get("items") or [])

            elif isinstance(group, dict):

                players.append(group)

        order = {"out": 0, "injured reserve": 0, "doubtful": 1, "questionable": 2, "day-to-day": 3}

        injuries = []

        for player in players:

            for injury in player.get("injuries", []) or []:

                status = injury.get("status") or _get(injury, "type", "description", default="") or "Injured"

                detail = (
                    _get(injury, "details", "type", default="")
                    or injury.get("shortComment", "")
                    or ""
                )

                injuries.append(
                    {
                        "name": player.get("displayName") or player.get("fullName", "?"),
                        "position": _get(player, "position", "abbreviation", default=""),
                        "jersey": player.get("jersey", ""),
                        "status": status,
                        "detail": detail,
                    }
                )

        injuries.sort(key=lambda item: order.get(item["status"].lower(), 4))

        return injuries


    def _fetch_leaders(self, sport, league, team_id, season):

        url = (
            f"{CORE}/{sport}/leagues/{league}/seasons/{season}"
            f"/types/2/teams/{team_id}/leaders"
        )

        data = self._json(url)

        wanted = {
            "nfl": ["passingYards", "rushingYards", "receivingYards", "sacks", "totalTackles", "interceptions"],
            "nba": ["pointsPerGame", "reboundsPerGame", "assistsPerGame", "stealsPerGame", "blocksPerGame"],
        }.get(league, [])

        categories = data.get("categories", []) or []

        by_name = {category.get("name"): category for category in categories}

        ordered = [by_name[name] for name in wanted if name in by_name] or categories[:5]

        leaders = []

        athlete_names = {}

        for category in ordered[:6]:

            top = _get(category, "leaders", 0)

            if not top:

                continue

            ref = _get(top, "athlete", "$ref", default="")

            name = athlete_names.get(ref)

            if name is None and ref:

                try:

                    athlete = self._json(ref.replace("http://", "https://"), timeout=6)

                    name = athlete.get("shortName") or athlete.get("displayName") or "?"

                except Exception:

                    name = "?"

                athlete_names[ref] = name

            leaders.append(
                {
                    "category": category.get("shortDisplayName")
                    or category.get("displayName")
                    or category.get("name", ""),
                    "name": name or "?",
                    "value": top.get("displayValue") or str(top.get("value", "")),
                }
            )

        return leaders

    # =====================================================
    # VOICE / AI HELPERS
    # =====================================================

    def match_team(self, text):

        """Team key mentioned in text ('how are the celtics doing')."""

        lowered = f" {text.lower()} "

        for team in self.teams:

            names = [team["key"].lower(), team.get("name", "").lower()] + [
                nickname.lower() for nickname in team.get("nicknames", [])
            ]

            for name in names:

                if name and len(name) > 2 and f" {name}" in lowered:

                    return team["key"]

        return None


    def context_for(self, text):

        """Plain-text briefing for the AI if text mentions a team."""

        key = self.match_team(text)

        if key is None:

            lowered = text.lower()

            if not any(word in lowered for word in ("game", "score", "team", "sports", "play")):

                return ""

            keys = self.team_keys()

        else:

            keys = [key]

        lines = []

        for key in keys:

            team = self.data.get(key)

            if not team:

                continue

            age = int((time.time() - team.get("updated_at", 0)) / 60)

            parts = [f"{team['name']} ({team['league']})"]

            if team.get("record"):

                parts.append(f"record {team['record']}")

            if team.get("standing"):

                parts.append(team["standing"])

            last = [game for game in team.get("schedule", []) if game["completed"]][-3:]

            if last:

                parts.append(
                    "last games: "
                    + ", ".join(
                        f"{game['result']} {'vs' if game['home'] else 'at'} {game['opponent']}"
                        for game in last
                    )
                )

            nxt = team.get("next_game")

            if nxt:

                parts.append(
                    f"next: {'vs' if nxt['home'] else 'at'} {nxt['opponent_name'] or nxt['opponent']} "
                    f"on {format_game_time(nxt['date'])}"
                )

            if team.get("injuries"):

                parts.append(
                    "injuries: "
                    + ", ".join(
                        f"{item['name']} ({item['status']})"
                        for item in team["injuries"][:6]
                    )
                )

            if team.get("leaders"):

                parts.append(
                    "leaders: "
                    + ", ".join(
                        f"{item['category']} {item['name']} {item['value']}"
                        for item in team["leaders"][:5]
                    )
                )

            lines.append("; ".join(parts) + f" (data {age} min old)")

        if not lines:

            return ""

        return "SPORTS DATA (from GLITCH's live feed):\n" + "\n".join(lines)


def format_game_time(iso):

    """'2026-11-02T18:00Z' -> 'Sun Nov 2, 1:00 PM' in local time."""

    if not iso:

        return "TBD"

    try:

        stamp = datetime.strptime(iso.replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")

    except ValueError:

        try:

            stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))

        except ValueError:

            return iso

    local = stamp.astimezone()

    return local.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")


def seconds_until(iso):

    try:

        stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))

        return (stamp - datetime.now(timezone.utc)).total_seconds()

    except Exception:

        return None
