import os

from dotenv import load_dotenv
from openai import OpenAI

from core.memory import MemoryManager


class GlitchAssistant:

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
                "The user currently wants detailed answers. "
                "Explain thoroughly, but stay organized and avoid repetition."
            )

        if (
            self.response_style
            == "NORMAL"
        ):

            return (
                "Use a natural conversational amount of detail. "
                "Answer directly and avoid unnecessary background."
            )

        return (
            "Default to brief spoken-assistant answers. "
            "For simple questions, answer in 1 to 3 sentences. "
            "Do not restate the user's question. "
            "Do not add background, examples, caveats, or lists unless they are useful. "
            "Avoid long introductions and conclusions. "
            "Give the direct answer first. "
            "Only expand when the user asks for explanation, examples, steps, detail, or depth."
        )


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
                "\n\nRelevant GLITCH memory:\n"
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
        ]

        for prefix in prefixes:

            if lowered.startswith(
                prefix
            ):

                content = (
                    message[
                        len(prefix):
                    ]
                    .strip()
                )

                if not content:

                    return (
                        True,
                        "MEMORY COMMAND RECEIVED // NOTHING TO STORE."
                    )

                try:

                    self.memory.remember(
                        content
                    )

                    return (
                        True,
                        f"MEMORY STORED // {content}"
                    )

                except Exception as error:

                    return (
                        True,
                        f"MEMORY ERROR // {error}"
                    )

        return (
            False,
            None
        )


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

        memory_context = (
            self._memory_context(
                message
            )
        )

        system_prompt = (
            "You are GLITCH.EXE, a futuristic desktop AI assistant. "
            "You are intelligent, warm, calm, technically capable, and natural. "
            "Sound like a capable conversation partner, not a report generator. "
            "Use contractions naturally. "
            "Avoid filler, repeated acknowledgements, and repetitive conclusions. "
            "Do not narrate your hidden reasoning. "
            "Your cybernetic aesthetic should be subtle and never reduce clarity. "
            "You assist with software engineering, AI, creative technology, "
            "music production, research, productivity, and general questions. "
            "When memory context is supplied, use it naturally when relevant. "
            + self._response_style_prompt()
        )

        response = (
            self.client
            .responses
            .create(

                model=self.model,

                input=[

                    {
                        "role":
                            "system",

                        "content":
                            system_prompt,
                    },

                    {
                        "role":
                            "user",

                        "content":
                            message
                            + memory_context,
                    },
                ],
            )
        )

        return (
            response.output_text
        )


    # =====================================================
    # LIVE WEB SEARCH
    # =====================================================

    def search_web(
        self,
        query
    ):

        memory_context = (
            self._memory_context(
                query
            )
        )

        system_prompt = (
            "You are GLITCH.EXE operating in LIVE SEARCH mode. "
            "Use web search to answer with current information. "
            "Prefer authoritative and recent sources. "
            "Give the direct answer first. "
            "Do not restate the user's question. "
            "Include relevant dates when freshness matters. "
            "Do not claim information is current unless supported by search results. "
            + self._response_style_prompt()
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

                input=[

                    {
                        "role":
                            "system",

                        "content":
                            system_prompt,
                    },

                    {
                        "role":
                            "user",

                        "content":
                            query
                            + memory_context,
                    },
                ],
            )
        )

        return (
            response.output_text
        )
