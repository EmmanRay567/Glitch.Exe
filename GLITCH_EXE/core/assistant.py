import os

from dotenv import load_dotenv
from openai import OpenAI

from core.memory import MemoryManager


# =========================================================
# GLITCH.EXE ASSISTANT
# =========================================================

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

            "You are helpful, intelligent, friendly, concise, "
            "and technically capable. "

            "Your personality has a subtle cybernetic/glitch aesthetic "
            "without becoming difficult to read. "

            "You assist with software engineering, AI, creative technology, "
            "music production, research, productivity, and general questions. "

            "When memory context is supplied, use it naturally when relevant."
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

            "Use web search to answer the user's request with "
            "current information. "

            "Prefer authoritative and recent sources. "

            "Be concise but useful. "

            "Include relevant dates when freshness matters. "

            "Do not claim information is current unless supported "
            "by the web search results."
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