"""
services/career_service.py

Data behind GLITCH's Career Matrix.

  campus_events   FAMU iStrike (Campus Labs Engage) public event search
  campus_news     news.famu.edu headlines + The Famuan + Google News
  jobs            Adzuna (free key, local + keyword search) and Remotive
                  (remote jobs, no key). Handshake has no public API, so
                  the page links you straight to it instead.
  local_news      Google News for your city
  world_news      Google News world headlines
  local_events    Ticketmaster Discovery (optional free key)
  weather         Open-Meteo (no key), used for outfit advice
  outfits         OpenAI: a recommendation for today, and a live web
                  search for real products matching your Customizer

Everything is fetched on background threads and cached in
data/career_cache.json. Every source is optional: if one fails or has
no key, its panel says so and the rest keep working.

Settings live in data/career_profile.json (created on first run):
city, job keywords, Engage school slug, and so on.

Optional keys in .env:
  ADZUNA_APP_ID / ADZUNA_APP_KEY      https://developer.adzuna.com
  TICKETMASTER_API_KEY                https://developer.ticketmaster.com
"""

import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv

from PySide6.QtCore import QObject, Signal


load_dotenv()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GLITCH.EXE"

DEFAULT_PROFILE = {
    "school": "Florida A&M University",
    "engage_slug": "famu",
    "city": "Tallahassee",
    "state": "FL",
    "job_keywords": "software engineer intern",
    "job_country": "us",
    "handshake_url": "https://app.joinhandshake.com/stu/postings",
    "istrike_url": "https://famu.campuslabs.com/engage/events",
    "news_url": "https://news.famu.edu/index.php",
}

# What the Customizer offers (also what the AI must choose from).
OUTFIT_OPTIONS = {
    "style": ["BUSINESS", "SMART CASUAL", "STREETWEAR", "ATHLETIC", "TECHWEAR"],
    "top": ["SUIT JACKET", "HOODIE", "BUTTON-UP", "TEE", "POLO", "QUARTER-ZIP"],
    "bottom": ["SUIT PANTS", "CHINOS", "SWEATPANTS", "JOGGERS", "SHORTS", "JEANS"],
    "shoes": ["DRESS SHOES", "SNEAKERS", "HIGH-TOPS", "BOOTS", "SLIDES"],
    "shade": ["EMERALD", "FOREST", "HUNTER", "OLIVE", "SAGE", "MINT", "NEON"],
    "fit": ["SLIM", "REGULAR", "OVERSIZED"],
    "budget": ["$50", "$100", "$200", "$400", "ANY"],
}

SHADE_HEX = {
    "EMERALD": "#1fbf6a",
    "FOREST": "#2e7d32",
    "HUNTER": "#356e4a",
    "OLIVE": "#7d8f3a",
    "SAGE": "#9cb89a",
    "MINT": "#8ff0c0",
    "NEON": "#39ff78",
}

# Your signature look: what the agent hologram wears by default.
DEFAULT_OUTFIT = {
    "style": "STREETWEAR",
    "top": "HOODIE",
    "bottom": "SWEATPANTS",
    "shoes": "SNEAKERS",
    "shade": "EMERALD",
    "fit": "REGULAR",
    "budget": "$100",
}

# Bump when DEFAULT_OUTFIT changes so a previously saved default is
# replaced (a look you customised yourself after this is kept).
OUTFIT_VERSION = 2


def _clean(text):

    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))

    return re.sub(r"\s+", " ", text).strip()


class CareerService(QObject):

    # (section name, payload)  sections: campus_events, campus_news,
    # jobs, local_news, world_news, local_events, weather
    section_updated = Signal(str, object)

    # (section, short status text)
    section_status = Signal(str, str)

    outfit_recommended = Signal(dict)

    products_found = Signal(list)

    outfit_error = Signal(str)

    REFRESH_SECONDS = 20 * 60

    SECTIONS = (
        "campus_events",
        "campus_news",
        "jobs",
        "local_news",
        "world_news",
        "local_events",
        "weather",
    )

    def __init__(self, data_dir="data"):

        super().__init__()

        self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.profile_path = self.data_dir / "career_profile.json"

        self.cache_path = self.data_dir / "career_cache.json"

        self.profile = self._load_profile()

        self.data = self._load_json(self.cache_path, {})

        self.outfit = dict(DEFAULT_OUTFIT)

        if self.profile.get("outfit_version", 1) >= OUTFIT_VERSION:

            self.outfit.update(self.profile.get("outfit", {}))

        else:

            self.save_outfit(self.outfit)

        self._busy = set()

        self._lock = threading.Lock()

        self._ai_client = None

    # =====================================================
    # STORAGE
    # =====================================================

    @staticmethod
    def _load_json(path, default):

        try:

            if path.exists():

                return json.loads(path.read_text(encoding="utf-8"))

        except Exception as error:

            print(f"CAREER LOAD ERROR ({path.name}):", error)

        return default


    def _load_profile(self):

        profile = dict(DEFAULT_PROFILE)

        saved = self._load_json(self.profile_path, None)

        if isinstance(saved, dict):

            profile.update(saved)

        else:

            self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        return profile


    def save_outfit(self, outfit):

        self.outfit = dict(outfit)

        self.profile["outfit"] = self.outfit

        self.profile["outfit_version"] = OUTFIT_VERSION

        try:

            self.profile_path.write_text(json.dumps(self.profile, indent=2), encoding="utf-8")

        except Exception as error:

            print("CAREER PROFILE SAVE ERROR:", error)


    def _store(self, section, payload):

        self.data[section] = {"items": payload, "updated_at": time.time()}

        try:

            self.cache_path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")

        except Exception as error:

            print("CAREER CACHE SAVE ERROR:", error)

        self.section_updated.emit(section, payload)


    def get(self, section):

        return (self.data.get(section) or {}).get("items") or []


    def age_minutes(self, section):

        stamp = (self.data.get(section) or {}).get("updated_at")

        return None if not stamp else int((time.time() - stamp) / 60)

    # =====================================================
    # REFRESH
    # =====================================================

    def emit_cached(self):

        for section in self.SECTIONS:

            if section in self.data:

                self.section_updated.emit(section, self.get(section))


    def refresh(self, sections=None, force=False):

        for section in sections or self.SECTIONS:

            stamp = (self.data.get(section) or {}).get("updated_at", 0)

            if not force and time.time() - stamp < self.REFRESH_SECONDS:

                continue

            with self._lock:

                if section in self._busy:

                    continue

                self._busy.add(section)

            threading.Thread(
                target=self._refresh_section,
                args=(section,),
                daemon=True,
            ).start()


    def _refresh_section(self, section):

        self.section_status.emit(section, "SYNCING")

        try:

            payload = getattr(self, f"_fetch_{section}")()

            self._store(section, payload)

            self.section_status.emit(section, "LIVE" if payload else "NOTHING FOUND")

        except Exception as error:

            print(f"CAREER FETCH ERROR ({section}):", error)

            self.section_status.emit(section, f"OFFLINE // {str(error)[:60]}")

        finally:

            with self._lock:

                self._busy.discard(section)

    # =====================================================
    # HTTP HELPERS
    # =====================================================

    @staticmethod
    def _get(url, timeout=10, headers=None):

        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:

            return response.read()


    def _json(self, url, **kwargs):

        return json.loads(self._get(url, **kwargs).decode("utf-8"))


    def _rss(self, url, limit=12):

        root = ET.fromstring(self._get(url))

        items = []

        for item in root.iter("item"):

            title = _clean(item.findtext("title"))

            source = item.findtext("source") or ""

            # Google News puts " - Source" at the end of titles.
            if source and title.endswith(f" - {source}"):

                title = title[: -len(source) - 3]

            published = item.findtext("pubDate") or ""

            try:

                stamp = parsedate_to_datetime(published).timestamp()

            except Exception:

                stamp = None

            items.append(
                {
                    "title": title,
                    "url": (item.findtext("link") or "").strip(),
                    "source": _clean(source),
                    "time": stamp,
                    "summary": _clean(item.findtext("description"))[:220],
                }
            )

            if len(items) >= limit:

                break

        return items


    @staticmethod
    def _google_news(query=None, topic=None):

        base = "https://news.google.com/rss"

        tail = "hl=en-US&gl=US&ceid=US:en"

        if topic:

            return f"{base}/headlines/section/topic/{topic}?{tail}"

        return f"{base}/search?q={urllib.parse.quote(query)}&{tail}"

    # =====================================================
    # SOURCES
    # =====================================================

    def _fetch_campus_events(self):

        slug = self.profile.get("engage_slug", "famu")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        url = (
            f"https://{slug}.campuslabs.com/engage/api/discovery/event/search?"
            + urllib.parse.urlencode(
                {
                    "endsAfter": now,
                    "orderByField": "endsOn",
                    "orderByDirection": "ascending",
                    "status": "Approved",
                    "take": 25,
                    "query": "",
                }
            )
        )

        data = self._json(url, headers={"Accept": "application/json"})

        events = []

        for event in data.get("value", []) or []:

            events.append(
                {
                    "title": _clean(event.get("name")),
                    "url": f"https://{slug}.campuslabs.com/engage/event/{event.get('id')}",
                    "start": event.get("startsOn"),
                    "end": event.get("endsOn"),
                    "location": _clean(event.get("location")),
                    "org": _clean(event.get("organizationName")),
                    "tags": event.get("categoryNames") or [],
                    "summary": _clean(event.get("description"))[:220],
                }
            )

        return events


    def _fetch_campus_news(self):

        items = []

        seen = set()

        # Official FAMU newsroom (no feed, so read the story links).
        try:

            page = self._get(self.profile.get("news_url", DEFAULT_PROFILE["news_url"])).decode("utf-8", "ignore")

            for href, title in re.findall(
                r'<a[^>]+href="(https://news\.famu\.edu/20\d\d/[^"]+\.php)"[^>]*>(.*?)</a>',
                page,
                flags=re.S | re.I,
            ):

                title = _clean(title)

                if len(title) < 12 or href in seen:

                    continue

                seen.add(href)

                year = re.search(r"/(20\d\d)/", href)

                items.append({"title": title, "url": href, "source": "FAMU News", "time": None, "summary": "", "year": year.group(1) if year else ""})

                if len(items) >= 8:

                    break

        except Exception as error:

            print("CAREER FAMU NEWSROOM ERROR:", error)

        # Student paper.
        try:

            for item in self._rss("https://www.thefamuanonline.com/feed/", limit=6):

                item["source"] = "The Famuan"

                items.append(item)

        except Exception as error:

            print("CAREER FAMUAN FEED ERROR:", error)

        # Wider coverage.
        try:

            school = self.profile.get("school", "Florida A&M University")

            for item in self._rss(self._google_news(f'"{school}" OR FAMU'), limit=8):

                if item["url"] not in seen:

                    items.append(item)

        except Exception as error:

            print("CAREER GOOGLE NEWS (CAMPUS) ERROR:", error)

        return items


    def _fetch_jobs(self):

        keywords = self.profile.get("job_keywords", "")

        city = self.profile.get("city", "")

        jobs = []

        app_id = os.getenv("ADZUNA_APP_ID")

        app_key = os.getenv("ADZUNA_APP_KEY")

        if app_id and app_key:

            url = (
                f"https://api.adzuna.com/v1/api/jobs/{self.profile.get('job_country', 'us')}/search/1?"
                + urllib.parse.urlencode(
                    {
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": keywords,
                        "where": f"{city}, {self.profile.get('state', '')}".strip(", "),
                        "distance": 40,
                        "results_per_page": 15,
                        "sort_by": "date",
                        "content-type": "application/json",
                    }
                )
            )

            try:

                for job in self._json(url).get("results", []) or []:

                    salary = ""

                    if job.get("salary_min"):

                        salary = f"${int(job['salary_min']):,}"

                        if job.get("salary_max") and job["salary_max"] != job["salary_min"]:

                            salary += f"-{int(job['salary_max']):,}"

                    jobs.append(
                        {
                            "title": _clean(job.get("title")),
                            "url": job.get("redirect_url", ""),
                            "company": _clean((job.get("company") or {}).get("display_name")),
                            "location": _clean((job.get("location") or {}).get("display_name")),
                            "salary": salary,
                            "posted": job.get("created", ""),
                            "kind": "LOCAL",
                        }
                    )

            except Exception as error:

                print("CAREER ADZUNA ERROR:", error)

        # Remote roles (no key needed).
        try:

            query = urllib.parse.quote(keywords.split()[0] if keywords else "software")

            remote = self._json(f"https://remotive.com/api/remote-jobs?search={query}&limit=15")

            for job in remote.get("jobs", []) or []:

                jobs.append(
                    {
                        "title": _clean(job.get("title")),
                        "url": job.get("url", ""),
                        "company": _clean(job.get("company_name")),
                        "location": _clean(job.get("candidate_required_location")) or "Remote",
                        "salary": _clean(job.get("salary")),
                        "posted": job.get("publication_date", ""),
                        "kind": "REMOTE",
                    }
                )

        except Exception as error:

            print("CAREER REMOTIVE ERROR:", error)

        return jobs


    def _fetch_local_news(self):

        city = self.profile.get("city", "Tallahassee")

        state = self.profile.get("state", "")

        return self._rss(self._google_news(f"{city} {state}".strip()), limit=12)


    def _fetch_world_news(self):

        return self._rss(self._google_news(topic="WORLD"), limit=12)


    def _fetch_local_events(self):

        key = os.getenv("TICKETMASTER_API_KEY")

        if not key:

            return []

        url = (
            "https://app.ticketmaster.com/discovery/v2/events.json?"
            + urllib.parse.urlencode(
                {
                    "apikey": key,
                    "city": self.profile.get("city", ""),
                    "stateCode": self.profile.get("state", ""),
                    "sort": "date,asc",
                    "size": 15,
                }
            )
        )

        data = self._json(url)

        events = []

        for event in ((data.get("_embedded") or {}).get("events") or []):

            start = (event.get("dates") or {}).get("start") or {}

            venues = ((event.get("_embedded") or {}).get("venues") or [{}])

            events.append(
                {
                    "title": _clean(event.get("name")),
                    "url": event.get("url", ""),
                    "start": start.get("dateTime") or start.get("localDate", ""),
                    "location": _clean(venues[0].get("name")),
                    "org": "",
                    "tags": [],
                    "summary": "",
                }
            )

        return events


    def _fetch_weather(self):

        city = self.profile.get("city", "Tallahassee")

        geo = self._json(
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
        )

        place = (geo.get("results") or [{}])[0]

        if "latitude" not in place:

            return []

        forecast = self._json(
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode(
                {
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                    "timezone": "auto",
                    "forecast_days": 1,
                }
            )
        )

        current = forecast.get("current") or {}

        daily = forecast.get("daily") or {}

        def first(key):

            values = daily.get(key) or [None]

            return values[0]

        return [
            {
                "temp": current.get("temperature_2m"),
                "feels": current.get("apparent_temperature"),
                "code": current.get("weather_code"),
                "wind": current.get("wind_speed_10m"),
                "high": first("temperature_2m_max"),
                "low": first("temperature_2m_min"),
                "rain_chance": first("precipitation_probability_max"),
            }
        ]


    def weather_summary(self):

        weather = (self.get("weather") or [None])[0]

        if not weather or weather.get("temp") is None:

            return ""

        rain = weather.get("rain_chance")

        return (
            f"{round(weather['temp'])}F now (feels {round(weather.get('feels') or weather['temp'])}F), "
            f"high {round(weather.get('high') or weather['temp'])}F / low {round(weather.get('low') or weather['temp'])}F"
            + (f", {rain}% chance of rain" if rain is not None else "")
        )

    # =====================================================
    # OUTFITS (OpenAI)
    # =====================================================

    def _client(self):

        if self._ai_client is None:

            from openai import OpenAI

            self._ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        return self._ai_client


    @staticmethod
    def _extract_json(text, opener="{"):

        closer = "}" if opener == "{" else "]"

        start = text.find(opener)

        end = text.rfind(closer)

        if start == -1 or end <= start:

            raise ValueError("no JSON in reply")

        return json.loads(text[start : end + 1])


    def recommend_outfit(self, occasion=""):

        threading.Thread(target=self._recommend, args=(occasion,), daemon=True).start()


    def _recommend(self, occasion):

        try:

            upcoming = [event["title"] for event in self.get("campus_events")[:3]]

            prompt = (
                "Pick one outfit for today for a college student who wears green. "
                f"Weather in {self.profile.get('city')}: {self.weather_summary() or 'unknown'}. "
                + (f"Occasion: {occasion}. " if occasion else "")
                + (f"Campus events today/soon: {'; '.join(upcoming)}. " if upcoming else "")
                + "Choose ONLY from these options and answer with JSON only:\n"
                + json.dumps(OUTFIT_OPTIONS)
                + '\nFormat: {"style":..,"top":..,"bottom":..,"shoes":..,"shade":..,'
                '"fit":..,"budget":..,"why":"one short spoken sentence"}'
            )

            response = self._client().responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
                input=prompt,
            )

            spec = self._extract_json(response.output_text, "{")

            outfit = dict(self.outfit)

            for key, options in OUTFIT_OPTIONS.items():

                value = str(spec.get(key, "")).upper()

                if value in options:

                    outfit[key] = value

            outfit["why"] = str(spec.get("why", ""))[:200]

            self.outfit_recommended.emit(outfit)

        except Exception as error:

            print("CAREER OUTFIT RECOMMEND ERROR:", error)

            self.outfit_error.emit(f"Couldn't build a recommendation: {error}")


    def describe_outfit(self, outfit):

        return (
            f"{outfit['fit'].lower()} {outfit['shade'].lower()} green {outfit['style'].lower()} look: "
            f"{outfit['top'].lower()}, {outfit['bottom'].lower()}, {outfit['shoes'].lower()}"
        )


    def find_products(self, outfit, extra=""):

        threading.Thread(target=self._find, args=(dict(outfit), extra), daemon=True).start()


    def _find(self, outfit, extra):

        try:

            budget = outfit.get("budget", "ANY")

            pieces = [outfit["top"], outfit["bottom"], outfit["shoes"]]

            prompt = (
                "Search the web for real products currently sold online for this outfit: "
                f"{self.describe_outfit(outfit)}. Colour: {outfit['shade'].lower()} green "
                f"(hex {SHADE_HEX.get(outfit['shade'], '')}). "
                + (f"Extra wishes: {extra}. " if extra else "")
                + (f"Budget per piece: under {budget}. " if budget != "ANY" else "")
                + f"Find 2 options for each piece: {', '.join(pieces)}. "
                "Only include products you actually found in search results, with their "
                "real product page URL. Never invent URLs or prices. Answer with JSON only: "
                '[{"piece":"TOP|BOTTOM|SHOES","name":..,"store":..,"price":"$..","url":..,'
                '"match":"how close it is to the request, a few words"}]'
            )

            response = self._client().responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
                tools=[{"type": "web_search"}],
                input=prompt,
            )

            products = self._extract_json(response.output_text, "[")

            clean = [
                {
                    "piece": str(item.get("piece", "")).upper()[:8],
                    "name": _clean(str(item.get("name", "")))[:90],
                    "store": _clean(str(item.get("store", "")))[:30],
                    "price": _clean(str(item.get("price", "")))[:14],
                    "url": str(item.get("url", "")),
                    "match": _clean(str(item.get("match", "")))[:60],
                }
                for item in products
                if isinstance(item, dict) and str(item.get("url", "")).startswith("http")
            ]

            self.products_found.emit(clean)

        except Exception as error:

            print("CAREER PRODUCT SEARCH ERROR:", error)

            self.outfit_error.emit(f"Product search failed: {error}")

    # =====================================================
    # AI CONTEXT
    # =====================================================

    def context_for(self, text):

        lowered = text.lower()

        parts = []

        if any(word in lowered for word in ("campus", "famu", "event", "on campus", "happening")):

            events = self.get("campus_events")[:5]

            if events:

                parts.append(
                    "Upcoming campus events: "
                    + "; ".join(f"{e['title']} ({format_when(e.get('start'))}, {e.get('location') or 'TBA'})" for e in events)
                )

            news = self.get("campus_news")[:4]

            if news:

                parts.append("Campus news: " + "; ".join(n["title"] for n in news))

        if any(word in lowered for word in ("job", "internship", "career", "hiring", "work")):

            jobs = self.get("jobs")[:5]

            if jobs:

                parts.append(
                    "Job leads: "
                    + "; ".join(f"{j['title']} at {j['company']} ({j['location']})" for j in jobs)
                )

        if any(word in lowered for word in ("news", "world", "going on", "headlines")):

            local = self.get("local_news")[:4]

            world = self.get("world_news")[:4]

            if local:

                parts.append(f"Local news ({self.profile.get('city')}): " + "; ".join(n["title"] for n in local))

            if world:

                parts.append("World news: " + "; ".join(n["title"] for n in world))

        if any(word in lowered for word in ("wear", "outfit", "fit", "dress", "clothes", "drip")):

            parts.append(
                f"Current Customizer outfit: {self.describe_outfit(self.outfit)}. "
                f"Weather: {self.weather_summary() or 'unknown'}."
            )

        if not parts:

            return ""

        return "CAREER MATRIX DATA (GLITCH's live feeds):\n" + "\n".join(parts)


def format_when(value):

    """ISO time -> 'Tue Nov 4, 6:00 PM' in local time."""

    if not value:

        return "TBA"

    try:

        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if stamp.tzinfo is not None:

            stamp = stamp.astimezone()

        text = stamp.strftime("%a %b %d, %I:%M %p")

        if len(str(value)) <= 10:

            text = stamp.strftime("%a %b %d")

        return text.replace(" 0", " ")

    except Exception:

        return str(value)[:16]


def format_age(stamp):

    if not stamp:

        return ""

    minutes = int((time.time() - stamp) / 60)

    if minutes < 60:

        return f"{max(1, minutes)}m ago"

    if minutes < 48 * 60:

        return f"{minutes // 60}h ago"

    return f"{minutes // 1440}d ago"