import hashlib
from pathlib import Path

from models.scan_result import FileScanResult
from services.threat_scoring_service import (
    ThreatScoringService
)
from services.trust_policy_service import (
    TrustPolicyService
)


class FileScannerService:
    """
    Safe, trust-aware GLITCH file scanner.

    V2:
    - SHA-256 hashing
    - extension analysis
    - double-extension detection
    - PE/MZ header inspection
    - Downloads / Temp path heuristics
    - local known-bad hashes
    - trusted extensions
    - trusted directories
    - trusted SHA-256 hashes

    It does NOT delete, execute, modify, or launch scanned files.
    """

    def __init__(
        self,
        threat_scoring_service=None,
        trust_policy_service=None,
        known_bad_hashes=None,
        max_file_size_mb=512
    ):

        self.threat_scoring_service = (
            threat_scoring_service
            or ThreatScoringService()
        )

        self.trust_policy_service = (
            trust_policy_service
            or TrustPolicyService()
        )

        self.known_bad_hashes = {
            value.lower()
            for value in (
                known_bad_hashes
                or set()
            )
        }

        self.max_file_size_bytes = (
            int(max_file_size_mb)
            * 1024
            * 1024
        )


    # ---------------------------------------------------------
    # HASHING
    # ---------------------------------------------------------

    def calculate_sha256(
        self,
        file_path
    ):

        digest = hashlib.sha256()

        with open(
            file_path,
            "rb"
        ) as file_handle:

            while True:

                chunk = (
                    file_handle.read(
                        1024 * 1024
                    )
                )

                if not chunk:
                    break

                digest.update(
                    chunk
                )

        return digest.hexdigest()


    # ---------------------------------------------------------
    # FACT EXTRACTION
    # ---------------------------------------------------------

    def _has_double_extension(
        self,
        path
    ):

        suffixes = [
            suffix.lower()
            for suffix
            in path.suffixes
        ]

        if len(suffixes) < 2:

            return False


        deceptive_prefixes = (
            self.threat_scoring_service
            .DOCUMENT_EXTENSIONS
        )

        execution_suffixes = (
            self.threat_scoring_service
            .EXECUTABLE_EXTENSIONS
            | self.threat_scoring_service
            .SCRIPT_EXTENSIONS
        )


        return (
            suffixes[-2]
            in deceptive_prefixes
            and suffixes[-1]
            in execution_suffixes
        )


    def _has_mz_header(
        self,
        path
    ):

        try:

            with open(
                path,
                "rb"
            ) as file_handle:

                return (
                    file_handle.read(
                        2
                    )
                    == b"MZ"
                )

        except Exception:

            return False


    def _path_parts_lower(
        self,
        path
    ):

        return {
            part.lower()
            for part in path.parts
        }


    def _extract_facts(
        self,
        path,
        sha256
    ):

        extension = (
            path.suffix.lower()
        )

        parts = (
            self._path_parts_lower(
                path
            )
        )


        trust_reasons = (
            self.trust_policy_service
            .evaluate(
                path,
                extension,
                sha256
            )
        )


        return {
            "extension":
                extension,

            "double_extension":
                self._has_double_extension(
                    path
                ),

            "hidden_name":
                path.name.startswith(
                    "."
                ),

            "user_download_location":
                (
                    "downloads"
                    in parts
                ),

            "temp_location":
                any(
                    part in {
                        "temp",
                        "tmp",
                    }
                    for part in parts
                ),

            "mz_header":
                self._has_mz_header(
                    path
                ),

            "known_bad_hash":
                (
                    sha256.lower()
                    in self.known_bad_hashes
                ),

            "trusted_extension":
                self.trust_policy_service
                .is_extension_trusted(
                    extension
                ),

            "trusted_directory":
                self.trust_policy_service
                .is_directory_trusted(
                    path
                ),

            "trusted_hash":
                self.trust_policy_service
                .is_hash_trusted(
                    sha256
                ),

            "trust_reasons":
                trust_reasons,
        }


    # ---------------------------------------------------------
    # FILE SCAN
    # ---------------------------------------------------------

    def scan_file(
        self,
        file_path
    ):

        path = (
            Path(file_path)
            .expanduser()
        )

        result = FileScanResult(
            path=str(path),
            file_name=path.name,
            extension=path.suffix.lower(),
        )


        try:

            if not path.exists():

                result.error = (
                    "File does not exist."
                )

                return result


            if not path.is_file():

                result.error = (
                    "Path is not a regular file."
                )

                return result


            if path.is_symlink():

                result.error = (
                    "Symbolic links are skipped for safety."
                )

                return result


            result.size_bytes = (
                path.stat()
                .st_size
            )


            if (
                result.size_bytes
                > self.max_file_size_bytes
            ):

                result.error = (
                    "File exceeds configured scan-size limit."
                )

                return result


            sha256 = (
                self.calculate_sha256(
                    path
                )
            )

            result.sha256 = (
                sha256
            )


            facts = (
                self._extract_facts(
                    path,
                    sha256
                )
            )


            (
                result.risk_score,
                result.risk_level,
                result.indicators
            ) = (
                self.threat_scoring_service
                .score(
                    facts
                )
            )


            return result


        except PermissionError:

            result.error = (
                "Permission denied."
            )

            return result


        except OSError as error:

            result.error = (
                f"OS error: {error}"
            )

            return result


        except Exception as error:

            result.error = (
                f"Scan error: {error}"
            )

            return result


    # ---------------------------------------------------------
    # DIRECTORY SCAN
    # ---------------------------------------------------------

    def scan_directory(
        self,
        directory_path,
        recursive=True,
        max_files=5000,
        exclude_paths=None
    ):

        root = (
            Path(directory_path)
            .expanduser()
        )

        if not root.exists():

            raise FileNotFoundError(
                f"Scan target does not exist: {root}"
            )


        if not root.is_dir():

            raise NotADirectoryError(
                f"Scan target is not a directory: {root}"
            )


        excluded = {
            str(
                Path(value)
                .expanduser()
                .resolve()
            )
            for value in (
                exclude_paths
                or []
            )
        }


        results = []


        iterator = (
            root.rglob("*")
            if recursive
            else root.glob("*")
        )


        for path in iterator:

            if len(results) >= max_files:
                break


            try:

                resolved = str(
                    path.resolve()
                )

            except Exception:

                resolved = str(
                    path
                )


            if any(
                resolved.startswith(
                    excluded_path
                )
                for excluded_path
                in excluded
            ):

                continue


            try:

                if not path.is_file():
                    continue

            except OSError:

                continue


            results.append(
                self.scan_file(
                    path
                )
            )


        return results
