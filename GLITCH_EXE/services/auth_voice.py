"""
services/auth_voice.py

GLITCH's voice at the biometric gate.

  * "Scanning user."                        when the scan starts
  * "Please show yourself to the camera..." when no face is in view
  * "Sorry. You are not 404. Access denied."   on a face mismatch
  *  ... "Try again after the timer ends."     when it locks you out
  *  a personal welcome when it's you, which gets more personal over
     time (OwnerMemory learns your routine: what time you usually
     sign in, how long you've been away, your streak, the team you
     follow, and anyone who tried to get in while you were gone).

Wiring (see main_window):

    self.auth_voice = AuthVoice(self.voice_engine, self.data_dir, ...)
    self.auth_voice.attach(self.auth_session)
    self.auth_voice.session_started()      # in start_authentication
    greeting = self.auth_voice.granted()   # when access is granted
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl

try:
    from PySide6.QtMultimedia import QSoundEffect
except Exception:          # QtMultimedia missing: run silently
    QSoundEffect = None


OWNER = "404"

# Streaks worth mentioning (every day would get old fast).
STREAK_MILESTONES = {3, 5, 7, 10, 14, 21, 30, 50, 75, 100, 150, 200, 365}


# =========================================================
# LINES
# =========================================================

SCANNING = "Scanning user."

SHOW_YOURSELF = "Please show yourself to the camera for authentication."

NO_FACE_TIMEOUT = (
    "I can't see anyone. Please show yourself to the camera for authentication."
)

DENIED = f"Sorry. You are not {OWNER}. Access denied."

LOCKED_OUT = (
    f"Sorry. You are not {OWNER}. Access denied. Try again after the timer ends."
)

NO_PROFILE = "No owner profile on file. Run the enrollment tool, then restart me."

FAULT = "Security subsystem fault. I can't verify you right now."

LOCK_LIFTED = "Lockdown lifted. Ready to scan."

# Result sounds (made by audio/generate_auth_sounds.py) and how long
# each plays before GLITCH starts talking over its tail.
SOUNDS = {
    "granted": ("auth_granted.wav", 0.95, 0.9),   # file, voice delay s, volume
    "denied":  ("auth_denied.wav", 0.45, 0.8),
    "unknown": ("auth_unknown.wav", 0.7, 0.85),
}

# Fixed lines are rendered once and cached, so they play instantly.
FIXED_LINES = (
    SCANNING,
    SHOW_YOURSELF,
    NO_FACE_TIMEOUT,
    DENIED,
    LOCKED_OUT,
    LOCK_LIFTED,
)


# =========================================================
# OWNER MEMORY (learns 404 over time)
# =========================================================

class OwnerMemory:

    """Small JSON memory of your sign-ins and habits.

    data/auth/owner_memory.json — delete it to make GLITCH forget.
    """

    MAX_VISITS = 400

    def __init__(self, path):

        self.path = Path(path)

        self.data = self._load()

    # ---------------------------------------------- storage

    def _blank(self):

        return {
            "version": 1,
            "unlocks": 0,
            "first_seen": None,
            "last_seen": None,
            "visits": [],            # unix times of past unlocks
            "streak_days": 0,
            "last_day": None,        # YYYY-MM-DD of last unlock
            "pages": {},             # page -> times opened
            "last_page": None,
            "teams": {},             # team -> times viewed
            "last_team": None,
            "intrusions": [],        # unix times of rejected faces
            "recent_lines": [],      # avoid repeating the same welcome
        }

    def _load(self):

        data = self._blank()

        try:

            stored = json.loads(self.path.read_text(encoding="utf-8"))

            if isinstance(stored, dict):

                data.update(stored)

        except FileNotFoundError:

            pass

        except Exception as error:

            print("AUTH VOICE // memory unreadable, starting fresh:", error)

        return data

    def save(self):

        try:

            self.path.parent.mkdir(parents=True, exist_ok=True)

            temp = self.path.with_suffix(".tmp")

            temp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

            os.replace(temp, self.path)

        except Exception as error:

            print("AUTH VOICE // memory save failed:", error)

    # ---------------------------------------------- learning

    def record_intrusion(self):

        self.data["intrusions"] = (self.data["intrusions"] + [time.time()])[-50:]

        self.save()

    def note_page(self, page):

        page = str(page or "").upper().strip()

        if not page:

            return

        pages = self.data["pages"]

        pages[page] = pages.get(page, 0) + 1

        self.data["last_page"] = page

        self.save()

    def note_team(self, team):

        team = str(team or "").strip()

        if not team:

            return

        teams = self.data["teams"]

        teams[team] = teams.get(team, 0) + 1

        self.data["last_team"] = team

        self.save()

    # ---------------------------------------------- greeting

    def welcome(self, now=None):

        """Build the welcome for this sign-in, then remember it."""

        now = now or time.time()

        facts = self._facts(now)

        line = self._compose(facts)

        self._record_unlock(now, facts)

        return line

    def _facts(self, now):

        data = self.data

        moment = datetime.fromtimestamp(now)

        today = moment.date()

        facts = {
            "hour": moment.hour + moment.minute / 60.0,
            "first_time": not data["unlocks"],
            "unlock_number": data["unlocks"] + 1,
            "gap": (now - data["last_seen"]) if data["last_seen"] else None,
            "team": data.get("last_team"),
            "team_views": data["teams"].get(data.get("last_team") or "", 0),
        }

        # ---- streak (consecutive days with a sign-in)
        streak = data.get("streak_days") or 0

        last_day = data.get("last_day")

        if last_day == today.isoformat():

            facts["streak"] = streak
            facts["new_day"] = False

        elif last_day == (today - timedelta(days=1)).isoformat():

            facts["streak"] = streak + 1
            facts["new_day"] = True

        else:

            facts["streak"] = 1
            facts["new_day"] = True

        # ---- routine: when do you usually sign in?
        hours = [
            datetime.fromtimestamp(stamp).hour
            + datetime.fromtimestamp(stamp).minute / 60.0
            for stamp in data["visits"][-60:]
        ]

        facts["usual_hour"] = None
        facts["late_owl"] = False

        if len(hours) >= 8:

            angles = [h / 24.0 * 2 * math.pi for h in hours]

            x = sum(math.cos(a) for a in angles) / len(angles)

            y = sum(math.sin(a) for a in angles) / len(angles)

            # Only trust a routine that's actually consistent.
            if math.hypot(x, y) >= 0.45:

                facts["usual_hour"] = (math.atan2(y, x) / (2 * math.pi) * 24) % 24

            late = sum(1 for h in hours if h < 4.5)

            facts["late_owl"] = late / len(hours) >= 0.35

        # ---- anyone try to get in while you were away?
        # (ignore the last 3 minutes: that was probably you in bad light)
        since = data["last_seen"] or 0

        facts["intrusions"] = sum(
            1
            for stamp in data["intrusions"]
            if since < stamp < now - 180
        )

        return facts

    def _record_unlock(self, now, facts):

        data = self.data

        data["unlocks"] += 1

        data["first_seen"] = data["first_seen"] or now

        data["last_seen"] = now

        data["visits"] = (data["visits"] + [now])[-self.MAX_VISITS:]

        data["streak_days"] = facts["streak"]

        data["last_day"] = datetime.fromtimestamp(now).date().isoformat()

        data["intrusions"] = []

        self.save()

    # ---------------------------------------------- phrasing

    def _pick(self, options):

        """Random choice that avoids the lines used most recently."""

        recent = self.data["recent_lines"]

        fresh = [o for o in options if o not in recent] or options

        choice = random.choice(fresh)

        self.data["recent_lines"] = (recent + [choice])[-8:]

        return choice

    def _compose(self, f):

        name = random.choice((OWNER, OWNER, "sir"))

        hour = f["hour"]

        gap = f["gap"]

        # ---- first sign-in ever
        if f["first_time"]:

            return (
                f"Identity confirmed. Welcome, {OWNER}. "
                "I'll start learning your routine from here."
            )

        # ---- opening
        if gap is not None and gap < 20 * 60:

            opening = self._pick((
                f"Welcome back, {name}.",
                f"Back already, {name}?",
                f"That was quick, {name}.",
            ))

        elif 5 <= hour < 12:

            opening = self._pick((
                f"Good morning, {name}.",
                f"Morning, {name}. Welcome back.",
                f"Hello {name}, welcome back.",
            ))

        elif 12 <= hour < 17:

            opening = self._pick((
                f"Good afternoon, {name}.",
                f"Hello {name}, welcome back.",
                f"Welcome back, {name}.",
            ))

        elif 17 <= hour < 22:

            opening = self._pick((
                f"Good evening, {name}.",
                f"Evening, {name}. Welcome back.",
                f"Hello {name}, welcome back.",
            ))

        else:

            opening = self._pick((
                f"Hello {name}, welcome back.",
                f"Welcome back, {name}.",
                f"Still up, {name}?",
            ))

        # ---- the most interesting thing it has noticed
        remarks = []   # (priority, line)

        if f["intrusions"]:

            count = f["intrusions"]

            remarks.append((95, (
                "While you were away, I blocked "
                + ("one unrecognised access attempt." if count == 1
                   else f"{count} unrecognised access attempts.")
                + " Snapshots are in the security log."
            )))

        if gap is not None and gap >= 7 * 86400:

            weeks = int(gap // (7 * 86400))

            remarks.append((80, self._pick((
                "It's been over a week. I kept the lights on." if weeks < 2
                else f"It's been {weeks} weeks. I kept the lights on.",
                "Been a while. Everything's exactly where you left it.",
            ))))

        elif gap is not None and gap >= 2 * 86400:

            days = int(gap // 86400)

            remarks.append((70, self._pick((
                f"It's been {days} days. Everything's exactly where you left it.",
                f"{days} days away. I held down the fort.",
            ))))

        number = f["unlock_number"]

        if number in (10, 25, 50, 100, 250, 500) or (number > 500 and number % 250 == 0):

            remarks.append((55, f"That's sign-in number {number}, for the record."))

        if f["new_day"] and f["streak"] in STREAK_MILESTONES:

            remarks.append((45, self._pick((
                f"{f['streak']} days in a row now.",
                f"Day {f['streak']} of the streak.",
            ))))

        usual = f["usual_hour"]

        if usual is not None and (gap is None or gap > 3 * 3600):

            diff = (hour - usual + 12) % 24 - 12

            if diff <= -3:

                remarks.append((40, self._pick((
                    "You're up earlier than usual.",
                    "Earlier than your usual start.",
                ))))

            elif diff >= 3:

                remarks.append((40, self._pick((
                    "Later than usual today.",
                    "Running a little later than your usual.",
                ))))

        if hour < 4.5 and f["late_owl"]:

            remarks.append((38, self._pick((
                "Another late night, I see.",
                "Burning the midnight oil again.",
            ))))

        team = f["team"]

        if team and f["team_views"] >= 3:

            nickname = team.split()[-1]

            remarks.append((20, f"Want the latest on the {nickname}?"))

        closers = (
            "What's on the agenda?",
            "All systems are online.",
            "What are we working on today?",
            "Ready when you are.",
        )

        parts = [opening]

        if remarks:

            remarks.sort(key=lambda item: item[0], reverse=True)

            top = remarks[0][0]

            # A little variety between equally interesting remarks.
            pool = [line for priority, line in remarks if priority >= top - 5]

            remark = random.choice(pool)

            parts.append(remark)

            if top < 60 and not remark.endswith("?") and random.random() < 0.6:

                parts.append(self._pick(closers))

        else:

            parts.append(self._pick(closers))

        return " ".join(parts)


# =========================================================
# GATE VOICE
# =========================================================

class AuthVoice(QObject):

    # No face for this long -> "please show yourself..."
    # Counted from the first camera frame, not from when the scan
    # starts (the webcam takes a moment to switch on).
    NO_FACE_AFTER_S = 4.0

    # ...and don't repeat it more often than this.
    NAG_EVERY_S = 9.0

    MAX_NAGS = 3

    # How long a new line waits for the current one to finish before
    # cutting it off (so "Scanning user" isn't chopped mid-word).
    POLITE_WAIT_S = 1.2

    def __init__(self, voice_engine, data_dir, enabled=None, parent=None, sounds_dir=None):

        super().__init__(parent)

        self.voice = voice_engine

        self.enabled = enabled or (lambda: True)

        self.memory = OwnerMemory(Path(data_dir) / "auth" / "owner_memory.json")

        self.state = "idle"     # idle | scanning | denied | locked | granted

        self.last_greeting = None

        self._scan_t0 = None
        self._last_face = None
        self._last_nag = None
        self._nags = 0
        self._last_lock_line = None

        # What we're saying / waiting to say.
        self._in_flight = False
        self._in_flight_since = 0.0
        self._pending = None

        self._poll = QTimer(self)
        self._poll.setInterval(250)
        self._poll.timeout.connect(self._tick)

        self._deny_timer = QTimer(self)
        self._deny_timer.setSingleShot(True)
        self._deny_timer.timeout.connect(lambda: self._cue("denied", DENIED, cache=True))

        # Result sounds: hacker chime / red saber hum / unknown query.
        self._cue_token = 0
        self._cue_until = 0.0
        self._sounds = {}

        sounds_dir = Path(sounds_dir) if sounds_dir else Path(data_dir).parent / "audio"

        if QSoundEffect is not None:

            for kind, (name, _lead, volume) in SOUNDS.items():

                path = sounds_dir / name

                if not path.exists():

                    print(f"AUTH VOICE // {path} not found: run generate_auth_sounds.py")

                    continue

                effect = QSoundEffect(self)

                effect.setSource(QUrl.fromLocalFile(str(path)))

                effect.setVolume(volume)

                self._sounds[kind] = effect

        if voice_engine is not None:

            voice_engine.speech_finished.connect(self._on_speech_finished)

            if hasattr(voice_engine, "voice_error"):

                voice_engine.voice_error.connect(lambda *_: self._on_speech_finished())

            if hasattr(voice_engine, "prefetch"):

                try:

                    voice_engine.prefetch(FIXED_LINES)

                except Exception as error:

                    print("AUTH VOICE // prefetch skipped:", error)

    # =====================================================
    # WIRING
    # =====================================================

    def attach(self, auth_session):

        auth_session.stage_changed.connect(self._on_stage)

        auth_session.face_status.connect(self._on_face)

        auth_session.denied.connect(self._on_denied)

        auth_session.lockdown.connect(self._on_lockdown)

    # =====================================================
    # CALLED BY MAIN WINDOW
    # =====================================================

    def session_started(self):

        """A new scan is starting (call before auth_session.begin())."""

        self.state = "scanning"

        self._scan_t0 = None
        self._last_face = None
        self._nags = 0
        self._last_nag = None

        self._deny_timer.stop()

        self._cue_token += 1

        self._poll.start()

        # Deferred: if begin() immediately reports a lockout, the
        # lockout line is said instead of "Scanning user".
        QTimer.singleShot(120, self._announce_scan)

    def granted(self):

        """Access granted: say (and return) the personal welcome."""

        if self.state == "granted":

            return self.last_greeting

        self.state = "granted"

        self._poll.stop()

        self._deny_timer.stop()

        self.last_greeting = self.memory.welcome()

        self._cue("granted", self.last_greeting)

        return self.last_greeting

    def note_page(self, page):

        self.memory.note_page(page)

    def note_team(self, team):

        self.memory.note_team(team)

    # =====================================================
    # AUTH SESSION EVENTS
    # =====================================================

    def _announce_scan(self):

        if self.state == "scanning":

            self._say(SCANNING, cache=True)

    def _on_stage(self, stage, *args):

        if self.state != "scanning":

            return

        # Nothing to do here any more: the no-face clock starts at the
        # first real camera frame (_on_face), not at the FACE stage,
        # because the webcam can take a few seconds to switch on.
        return

    def _on_face(self, score, present, *args):

        if self.state != "scanning":

            return

        now = time.monotonic()

        if self._scan_t0 is None:

            self._scan_t0 = now

        if present:

            self._last_face = now

    def _on_denied(self, result):

        if self.state != "scanning":

            return

        reason = str(getattr(result, "reason", "") or "").upper()

        if reason == "CANCELLED":

            return

        self._poll.stop()

        self.state = "denied"

        if reason in ("FACE_MISMATCH", "VOICE_MISMATCH"):

            self.memory.record_intrusion()

            # If this failure also trips the lockout, _on_lockdown fires
            # right after and says the lockout line instead.
            self._deny_timer.start(80)

        elif reason == "NO_FACE":

            self._cue("unknown", NO_FACE_TIMEOUT, cache=True)

        elif reason == "NO_PROFILE":

            self._cue("unknown", NO_PROFILE, cache=True)

        elif reason == "FAULT":

            self._cue("unknown", FAULT, cache=True)

        else:

            self._deny_timer.start(80)

    def _on_lockdown(self, *args):

        if self.state == "granted":

            return

        self._deny_timer.stop()

        self._poll.stop()

        self.state = "locked"

        now = time.monotonic()

        # Clicking retry during a lockout re-reports it; don't repeat
        # the whole line every click.
        if self._last_lock_line is not None and now - self._last_lock_line < 6.0:

            return

        self._last_lock_line = now

        self._cue("denied", LOCKED_OUT, cache=True)

        seconds = args[0] if args and isinstance(args[0], (int, float)) else 0

        if seconds > 0:

            self._lift_at = now + seconds

            QTimer.singleShot(int(seconds * 1000) + 300, self._lock_lifted)

    def _lock_lifted(self):

        if self.state == "locked" and time.monotonic() >= getattr(self, "_lift_at", 0):

            self.state = "idle"

            self._say(LOCK_LIFTED, cache=True)

    def _tick(self):

        if self.state != "scanning" or self._scan_t0 is None:

            return

        now = time.monotonic()

        reference = self._last_face or self._scan_t0

        if (
            now - reference >= self.NO_FACE_AFTER_S
            and (self._last_nag is None or now - self._last_nag >= self.NAG_EVERY_S)
            and self._nags < self.MAX_NAGS
            and not self._busy()
        ):

            self._nags += 1

            self._last_nag = now

            self._cue("unknown", SHOW_YOURSELF, cache=True)

    # =====================================================
    # SPEAKING
    # =====================================================

    def _cue(self, kind, text, cache=False):

        """Play the result sound, then say the line over its tail."""

        self._cue_token += 1

        token = self._cue_token

        for effect in self._sounds.values():

            effect.stop()

        effect = self._sounds.get(kind)

        lead = SOUNDS[kind][1] if effect is not None else 0.0

        if effect is not None:

            effect.play()

        self._cue_until = time.monotonic() + lead

        def speak():

            if token == self._cue_token:

                self._cue_until = 0.0   # timers can fire a hair early

                self._say(text, cache)

        if lead > 0:

            QTimer.singleShot(int(lead * 1000), speak)

        else:

            speak()

    def _busy(self):

        if time.monotonic() < self._cue_until:

            return True

        if self._in_flight and time.monotonic() - self._in_flight_since > 8.0:

            self._in_flight = False   # lost a signal somewhere; recover

        return self._in_flight

    def _say(self, text, cache=False):

        if self.voice is None or not self.enabled():

            return

        if self._busy():

            # Let the current line finish (briefly), newest line wins.
            first = self._pending is None

            self._pending = (text, cache)

            if first:

                QTimer.singleShot(int(self.POLITE_WAIT_S * 1000), self._flush)

            return

        self._speak_now(text, cache)

    def _flush(self):

        if self._pending is not None:

            text, cache = self._pending

            self._speak_now(text, cache)

    def _speak_now(self, text, cache):

        self._pending = None

        try:

            self.voice.speak(text, cache=cache)

        except TypeError:

            # Older voice_engine without the phrase cache.
            self.voice.speak(text)

        # Set after speak(): interrupting the old line emits its
        # speech_finished synchronously inside speak().
        self._in_flight = True

        self._in_flight_since = time.monotonic()

    def _on_speech_finished(self):

        self._in_flight = False

        if self._pending is not None:

            QTimer.singleShot(60, self._flush)