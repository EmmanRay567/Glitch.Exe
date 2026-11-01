import json
from pathlib import Path


class TrustPolicyService:
    """
    Stores user-controlled trust rules for GLITCH Security Engine.

    Trust can come from:
    - file extensions
    - directories
    - exact SHA-256 hashes

    The trust layer does NOT mark known-malicious hashes as safe.
    Known-bad signatures always win.
    """

    DEFAULT_TRUSTED_EXTENSIONS = {
        ".pkt",      # Cisco Packet Tracer
        ".py",
        ".cpp",
        ".h",
        ".hpp",
        ".json",
        ".md",
        ".txt",
        ".csv",
        ".ipynb",
        ".sln",
        ".vcxproj",
        ".pyproj",
    }

    def __init__(
        self,
        policy_path=None
    ):

        self.policy_path = Path(
            policy_path
            or (
                Path("data")
                / "security_trust_policy.json"
            )
        )

        self.policy_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.trusted_extensions = set(
            self.DEFAULT_TRUSTED_EXTENSIONS
        )

        self.trusted_directories = set()
        self.trusted_hashes = set()

        self._load()


    # ---------------------------------------------------------
    # STORAGE
    # ---------------------------------------------------------

    def _load(
        self
    ):

        if not self.policy_path.exists():

            self._save()

            return


        try:

            data = json.loads(
                self.policy_path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            return


        extensions = (
            data.get(
                "trusted_extensions",
                []
            )
        )

        directories = (
            data.get(
                "trusted_directories",
                []
            )
        )

        hashes = (
            data.get(
                "trusted_hashes",
                []
            )
        )


        self.trusted_extensions.update(
            str(value).lower()
            for value in extensions
        )

        self.trusted_directories.update(
            str(
                Path(value)
                .expanduser()
                .resolve()
            )
            for value in directories
        )

        self.trusted_hashes.update(
            str(value).lower()
            for value in hashes
        )


    def _save(
        self
    ):

        payload = {
            "trusted_extensions":
                sorted(
                    self.trusted_extensions
                ),

            "trusted_directories":
                sorted(
                    self.trusted_directories
                ),

            "trusted_hashes":
                sorted(
                    self.trusted_hashes
                ),
        }


        self.policy_path.write_text(
            json.dumps(
                payload,
                indent=2
            ),
            encoding="utf-8"
        )


    # ---------------------------------------------------------
    # TRUST MANAGEMENT
    # ---------------------------------------------------------

    def trust_extension(
        self,
        extension
    ):

        extension = (
            str(extension)
            .strip()
            .lower()
        )

        if not extension.startswith(
            "."
        ):

            extension = (
                "."
                + extension
            )


        self.trusted_extensions.add(
            extension
        )

        self._save()


    def trust_directory(
        self,
        directory
    ):

        path = str(
            Path(directory)
            .expanduser()
            .resolve()
        )


        self.trusted_directories.add(
            path
        )

        self._save()


    def trust_hash(
        self,
        sha256
    ):

        sha256 = (
            str(sha256)
            .strip()
            .lower()
        )

        if sha256:

            self.trusted_hashes.add(
                sha256
            )

            self._save()


    # ---------------------------------------------------------
    # TRUST LOOKUP
    # ---------------------------------------------------------

    def is_extension_trusted(
        self,
        extension
    ):

        return (
            str(extension)
            .lower()
            in self.trusted_extensions
        )


    def is_hash_trusted(
        self,
        sha256
    ):

        if not sha256:
            return False

        return (
            str(sha256)
            .lower()
            in self.trusted_hashes
        )


    def is_directory_trusted(
        self,
        file_path
    ):

        try:

            resolved = (
                Path(file_path)
                .expanduser()
                .resolve()
            )

        except Exception:

            return False


        for trusted_directory in (
            self.trusted_directories
        ):

            try:

                if resolved.is_relative_to(
                    Path(
                        trusted_directory
                    )
                ):

                    return True

            except Exception:

                continue


        return False


    def evaluate(
        self,
        file_path,
        extension,
        sha256
    ):

        reasons = []


        if self.is_extension_trusted(
            extension
        ):

            reasons.append(
                (
                    "TRUSTED_EXTENSION",
                    (
                        f"Extension {extension} is "
                        "trusted by local policy."
                    )
                )
            )


        if self.is_directory_trusted(
            file_path
        ):

            reasons.append(
                (
                    "TRUSTED_DIRECTORY",
                    (
                        "File is inside a trusted "
                        "directory."
                    )
                )
            )


        if self.is_hash_trusted(
            sha256
        ):

            reasons.append(
                (
                    "TRUSTED_HASH",
                    (
                        "SHA-256 hash is explicitly "
                        "trusted."
                    )
                )
            )


        return reasons

