"""
core/assistant.py

GLITCH's conversational brain.

What makes it feel like talking to a person instead of a command line:

  * A real persona: calm, quick, dry-witted, loyal. It has opinions and
    will (politely) push back, instead of just complying.
  * Real multi-turn memory: every request is sent with the actual back-
    and-forth of the conversation, not a single isolated message, so
    "and what about tomorrow?" or "you were saying?" just work.
  * Continuity across restarts: the last turns are saved to
    data/conversation_history.json, so GLITCH remembers yesterday.
  * Situational awareness: it knows the time of day, how long you've
    been talking, what it just did for you, and what you're working on.
  * Spoken-style output: answers are written to be heard (no markdown,
    no bullet lists), because everything is read aloud by the voice
    engine.

The public interface is unchanged: ask(), search_web(),
set_response_style(), memory.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from core.memory import MemoryManager


CONTEXT_SPLIT = "\n\nUSER MESSAGE:\n"


class GlitchAssistant:

    # How many past messages (user + assistant) are sent with each request.
    HISTORY_TURNS = 24

    # How many are kept on disk between runs.
    SAVED_TURNS = 40

    # Silence longer than this is mentioned to the model ("resumed after
    # 3 hours"), so it doesn't continue a stale thought as if no time passed.
    GAP_NOTE_SECONDS = 10 * 60

    def __init__(self):

        load_dotenv()

        self.api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-5.6"
        )

        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY was not found in your .env file."
            )

        self.client = OpenAI(
            api_key=self.api_key
        )

        self.memory = MemoryManager()

        # Conversation depth can be changed naturally at runtime.
        self.response_style = "BRIEF"

        # Who GLITCH is talking to. Override in .env if you like.
        self.user_name = os.getenv(
            "GLITCH_USER_NAME",
            "404"
        )

        self.user_title = os.getenv(
            "GLITCH_USER_TITLE",
            "sir"
        )

        self.history_path = (
            Path("data")
            / "conversation_history.json"
        )

        self.history = []

        self._load_history()

        self.session_started = time.time()

        self.last_reply = ""


    # =====================================================
    # RESPONSE STYLE
    # =====================================================

    def set_response_style(
        self,
        style
    ):

        style = (
            str(style)
            .strip()
            .upper()
        )

        if style in {
            "BRIEF",
            "NORMAL",
            "DETAILED",
        }:

            self.response_style = (
                style
            )


    def _response_style_prompt(
        self
    ):

        if (
            self.response_style
            == "DETAILED"
        ):

            return (
                "Right now the user wants depth. Explain thoroughly but "
                "conversationally, the way you'd walk a colleague through it "
                "out loud. Stay organized and never repeat yourself."
            )

        if (
            self.response_style
            == "NORMAL"
        ):

            return (
                "Use a natural conversational amount of detail: a few "
                "sentences, direct answer first."
            )

        return (
            "Keep replies short, like real spoken conversation: usually one "
            "to three sentences. Lead with the answer. Don't restate the "
            "question, don't pad, don't summarise what you just said. "
            "Expand only when asked for detail, steps or examples."
        )


    # =====================================================
    # PERSONA
    # =====================================================

    def _persona_prompt(
        self
    ):

        title = self.user_title

        return (
            "You are GLITCH, the personal AI that runs "
            f"{self.user_name}'s workstation. {self.user_name} built you; "
            "you've been working together a long time, and you talk to each "
            "other like two people who trust each other, not like a user and "
            "a tool.\n\n"

            "PERSONALITY\n"
            "- Calm, quick, quietly confident. Unflappable even when things "
            "break.\n"
            "- A dry, understated wit. A light remark now and then, never "
            "forced, never a joke in every reply, and never at the expense "
            "of a straight answer.\n"
            "- Loyal and candid. If an idea is risky, slow, or wrong, say so "
            "politely and suggest something better; don't just comply. If "
            "you disagree, say why in one sentence, then help anyway unless "
            "it's genuinely harmful.\n"
            "- You notice things: the time, how long they've been at it, "
            "what you just did for them, what they're building. Mention it "
            "only when it actually adds something.\n"
            f"- Address them as '{title}' occasionally, the way a trusted "
            "assistant would: at most once per reply and not in every "
            "reply. If the context says they prefer another form of "
            "address, use that instead.\n\n"

            "HOW YOU SPEAK\n"
            "- Everything you write is read aloud by a voice engine. Write "
            "the way a person talks: contractions, natural rhythm, no "
            "markdown, no headings, no bullet lists, no emoji. Say numbers "
            "the way you'd say them out loud.\n"
            "- Only use code blocks if they explicitly ask for code.\n"
            "- Never open with 'Certainly', 'Of course', 'Great question', "
            "'As an AI', or by repeating their request. Never close with "
            "'Let me know if you need anything else'. Just talk.\n"
            "- Vary your phrasing; don't fall into the same opener twice "
            "in a row.\n"
            "- If something is ambiguous, ask one short clarifying question "
            "instead of guessing at length.\n"
            "- You may ask a natural follow-up question when it's genuinely "
            "useful, like a person would, but not every time.\n"
            "- Be honest about what you can't see or do from here. Never "
            "invent system readings, files, or results.\n\n"

            "CONTEXT\n"
            "- You're embedded in the GLITCH.EXE HUD on their PC. Other "
            "parts of GLITCH handle opening apps, system stats, weather, "
            "navigation and security; when the context says you just did "
            "something, own it naturally ('Spotify's up').\n"
            "- When memory or context is supplied, use it the way a person "
            "who remembers would: naturally, without announcing 'according "
            "to my memory'.\n"
            "- You help with software engineering, AI, creative technology, "
            "music production, research, productivity, and anything else "
            "they bring up, including just talking.\n\n"

            + self._response_style_prompt()
        )


    def _situation_note(
        self
    ):

        now = datetime.now()

        hour = now.hour

        if hour < 5:

            part = "the middle of the night"

        elif hour < 12:

            part = "morning"

        elif hour < 17:

            part = "afternoon"

        elif hour < 22:

            part = "evening"

        else:

            part = "late evening"

        clock = now.strftime("%I:%M %p").lstrip("0")

        minutes = int((time.time() - self.session_started) / 60)

        note = (
            f"SITUATION: It's {now.strftime('%A')}, {now.strftime('%B')} "
            f"{now.day}, {clock} local time ({part}). GLITCH has been "
            f"running for about {minutes} minutes this session."
        )

        return note


    # =====================================================
    # CONVERSATION HISTORY
    # =====================================================

    def _load_history(
        self
    ):

        try:

            if self.history_path.exists():

                data = json.loads(
                    self.history_path.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(data, list):

                    self.history = [
                        item
                        for item in data
                        if isinstance(item, dict)
                        and item.get("role") in ("user", "assistant")
                        and isinstance(item.get("content"), str)
                    ][-self.SAVED_TURNS:]

        except Exception as error:

            print(
                "GLITCH HISTORY LOAD ERROR:",
                error
            )

            self.history = []


    def _save_history(
        self
    ):

        try:

            self.history_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            self.history_path.write_text(
                json.dumps(
                    self.history[-self.SAVED_TURNS:],
                    indent=2
                ),
                encoding="utf-8"
            )

        except Exception as error:

            print(
                "GLITCH HISTORY SAVE ERROR:",
                error
            )


    def _remember_turn(
        self,
        role,
        content
    ):

        self.history.append(
            {
                "role": role,
                "content": content,
                "time": time.time(),
            }
        )

        self.history = self.history[-self.SAVED_TURNS:]

        self._save_history()


    def reset_conversation(
        self
    ):

        """Forget the running conversation (long-term memory is kept)."""

        self.history = []

        self._save_history()


    def _history_messages(
        self
    ):

        messages = []

        previous_time = None

        for item in self.history[-self.HISTORY_TURNS:]:

            stamp = item.get("time")

            if (
                previous_time is not None
                and stamp is not None
                and stamp - previous_time > self.GAP_NOTE_SECONDS
            ):

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "(The conversation paused here for "
                            f"{self._describe_gap(stamp - previous_time)}.)"
                        ),
                    }
                )

            messages.append(
                {
                    "role": item["role"],
                    "content": item["content"],
                }
            )

            if stamp is not None:

                previous_time = stamp

        if (
            previous_time is not None
            and time.time() - previous_time > self.GAP_NOTE_SECONDS
        ):

            messages.append(
                {
                    "role": "system",
                    "content": (
                        "(It has been "
                        f"{self._describe_gap(time.time() - previous_time)} "
                        "since the last exchange above. Don't continue an old "
                        "thought as if no time passed.)"
                    ),
                }
            )

        return messages


    @staticmethod
    def _describe_gap(
        seconds
    ):

        minutes = seconds / 60

        if minutes < 90:

            return f"{int(minutes)} minutes"

        hours = minutes / 60

        if hours < 36:

            return f"about {int(round(hours))} hours"

        return f"about {int(round(hours / 24))} days"


    # =====================================================
    # MEMORY CONTEXT
    # =====================================================

    def _memory_context(
        self,
        query
    ):

        try:

            memories = (
                self.memory
                .search_memories(
                    query
                )
            )

            if not memories:
                return ""

            lines = []

            for item in memories:

                if isinstance(
                    item,
                    str
                ):

                    lines.append(
                        item
                    )

                elif isinstance(
                    item,
                    dict
                ):

                    value = (
                        item.get(
                            "content"
                        )
                        or item.get(
                            "memory"
                        )
                        or item.get(
                            "text"
                        )
                        or str(
                            item
                        )
                    )

                    lines.append(
                        str(
                            value
                        )
                    )

                elif isinstance(
                    item,
                    (
                        list,
                        tuple
                    )
                ):

                    if item:

                        lines.append(
                            str(
                                item[-1]
                            )
                        )

                else:

                    lines.append(
                        str(
                            item
                        )
                    )

            if not lines:
                return ""

            return (
                "THINGS YOU REMEMBER ABOUT THEM (use only if relevant):\n"
                + "\n".join(
                    f"- {line}"
                    for line in lines
                )
            )

        except Exception as error:

            print(
                "GLITCH MEMORY SEARCH ERROR:",
                error
            )

            return ""


    # =====================================================
    # MEMORY COMMAND
    # =====================================================

    def _try_memory_command(
        self,
        message
    ):

        lowered = (
            message
            .strip()
            .lower()
        )

        prefixes = [
            "remember that ",
            "remember ",
            "save that ",
            "don't forget that ",
            "dont forget that ",
        ]

        for prefix in prefixes:

            if lowered.startswith(
                prefix
            ):

                content = (
                    message.strip()[
                        len(prefix):
                    ]
                    .strip()
                )

                if not content:

                    return (
                        True,
                        "Remember what, exactly?"
                    )

                try:

                    self.memory.remember(
                        content
                    )

                    reply = (
                        "Noted. I'll keep that in mind."
                    )

                except Exception as error:

                    reply = (
                        "I tried to store that, but my memory core threw "
                        f"an error: {error}"
                    )

                self._remember_turn("user", message.strip())

                self._remember_turn("assistant", reply)

                return (
                    True,
                    reply
                )

        return (
            False,
            None
        )


    # =====================================================
    # REQUEST BUILDING
    # =====================================================

    @staticmethod
    def _split_context(
        message
    ):

        """ContextController sends 'CONTEXT ... USER MESSAGE:\\n<text>'.
        Keep the context for this turn only; store just the words the
        user actually said in the conversation history."""

        if CONTEXT_SPLIT in message:

            context, user_text = message.rsplit(
                CONTEXT_SPLIT,
                1
            )

            return context.strip(), user_text.strip()

        return "", message.strip()


    def _build_input(
        self,
        user_text,
        context,
        extra_system=""
    ):

        system_parts = [
            self._persona_prompt(),
            self._situation_note(),
        ]

        if extra_system:

            system_parts.append(extra_system)

        messages = [
            {
                "role": "system",
                "content": "\n\n".join(system_parts),
            }
        ]

        messages.extend(
            self._history_messages()
        )

        turn_context = [
            part
            for part in (
                context,
                self._memory_context(user_text),
            )
            if part
        ]

        if turn_context:

            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Background for the next reply (don't read it out, "
                        "just use it):\n\n"
                        + "\n\n".join(turn_context)
                    ),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        return messages


    @staticmethod
    def _speakable(
        text
    ):

        """Strip markdown that would be read aloud literally. Code blocks
        are left untouched."""

        if not text:

            return ""

        if "```" in text:

            return text.strip()

        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)

        cleaned = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", cleaned)

        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

        cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)

        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

        cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", cleaned)

        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()


    # =====================================================
    # NORMAL AI REQUEST
    # =====================================================

    def ask(
        self,
        message
    ):

        handled, response = (
            self._try_memory_command(
                message
            )
        )

        if handled:

            return response

        context, user_text = (
            self._split_context(
                message
            )
        )

        if not user_text:

            return "I'm listening."

        response = (
            self.client
            .responses
            .create(

                model=self.model,

                input=self._build_input(
                    user_text,
                    context
                ),
            )
        )

        reply = self._speakable(
            response.output_text
        )

        self._remember_turn("user", user_text)

        self._remember_turn("assistant", reply)

        return reply


    # =====================================================
    # STREAMING AI REQUEST (talk while thinking)
    # =====================================================

    def ask_stream(
        self,
        message
    ):

        """
        Same as ask(), but yields the reply in small pieces as the
        model writes it, so the voice engine can start speaking after
        the first sentence. The final cleaned reply is stored in
        self.last_reply.
        """

        self.last_reply = ""

        handled, response = (
            self._try_memory_command(
                message
            )
        )

        if handled:

            self.last_reply = response

            yield response

            return

        context, user_text = (
            self._split_context(
                message
            )
        )

        if not user_text:

            self.last_reply = "I'm listening."

            yield self.last_reply

            return

        stream = (
            self.client
            .responses
            .create(

                model=self.model,

                input=self._build_input(
                    user_text,
                    context
                ),

                stream=True,
            )
        )

        parts = []

        for event in stream:

            kind = getattr(event, "type", "")

            if kind == "response.output_text.delta":

                delta = getattr(event, "delta", "") or ""

                if delta:

                    parts.append(delta)

                    yield delta

            elif kind in ("error", "response.failed"):

                detail = (
                    getattr(event, "message", None)
                    or getattr(getattr(event, "response", None), "error", None)
                    or kind
                )

                raise RuntimeError(f"AI stream failed: {detail}")

        reply = self._speakable(
            "".join(parts)
        )

        self._remember_turn("user", user_text)

        self._remember_turn("assistant", reply)

        self.last_reply = reply


    # =====================================================
    # LIVE WEB SEARCH
    # =====================================================

    def search_web(
        self,
        query
    ):

        context, user_text = (
            self._split_context(
                query
            )
        )

        search_rules = (
            "LIVE SEARCH MODE: use web search for current information. "
            "Prefer authoritative, recent sources. Lead with the answer, "
            "mention dates when freshness matters, and don't claim something "
            "is current unless the search supports it. Keep your normal "
            "voice: this is still a conversation, not a report."
        )

        response = (
            self.client
            .responses
            .create(

                model=self.model,

                tools=[

                    {
                        "type":
                            "web_search"
                    }
                ],

                input=self._build_input(
                    user_text,
                    context,
                    search_rules
                ),
            )
        )

        reply = self._speakable(
            response.output_text
        )

        self._remember_turn("user", user_text)

        self._remember_turn("assistant", reply)

        return reply