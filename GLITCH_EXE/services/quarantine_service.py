import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


class QuarantineService:
    """
    Safe GLITCH quarantine manager.

    Quarantine is explicit only:
    nothing is quarantined automatically by the scanner.
    """

    def __init__(
        self,
        quarantine_directory=None
    ):

        self.quarantine_directory = (
            Path(
                quarantine_directory
                or (
                    Path("data")
                    / "quarantine"
                )
            )
        )

        self.quarantine_directory.mkdir(
            parents=True,
            exist_ok=True
        )


    def quarantine_file(
        self,
        file_path,
        scan_result
    ):

        source = (
            Path(file_path)
            .expanduser()
            .resolve()
        )


        if not source.exists():

            raise FileNotFoundError(
                str(source)
            )


        if not source.is_file():

            raise ValueError(
                "Only regular files can be quarantined."
            )


        item_id = uuid.uuid4().hex

        payload_path = (
            self.quarantine_directory
            / f"{item_id}.quarantine"
        )

        metadata_path = (
            self.quarantine_directory
            / f"{item_id}.json"
        )


        metadata = {
            "id":
                item_id,

            "original_path":
                str(source),

            "quarantine_path":
                str(payload_path),

            "file_name":
                source.name,

            "sha256":
                scan_result.sha256,

            "risk_score":
                scan_result.risk_score,

            "risk_level":
                scan_result.risk_level,

            "indicators": [
                indicator.message
                for indicator
                in scan_result.indicators
            ],

            "quarantined_at":
                datetime.now()
                .isoformat(),
        }


        shutil.move(
            str(source),
            str(payload_path)
        )


        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2
            ),
            encoding="utf-8"
        )


        return metadata


    def list_items(
        self
    ):

        items = []


        for metadata_path in (
            self.quarantine_directory
            .glob("*.json")
        ):

            try:

                items.append(
                    json.loads(
                        metadata_path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:

                continue


        items.sort(
            key=lambda item:
                item.get(
                    "quarantined_at",
                    ""
                ),
            reverse=True
        )


        return items


    def _load_item(
        self,
        item_id
    ):

        metadata_path = (
            self.quarantine_directory
            / f"{item_id}.json"
        )

        if not metadata_path.exists():

            raise FileNotFoundError(
                f"Unknown quarantine item: {item_id}"
            )


        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )


        return (
            metadata_path,
            metadata
        )


    def restore(
        self,
        item_id
    ):

        (
            metadata_path,
            metadata
        ) = self._load_item(
            item_id
        )


        source = Path(
            metadata[
                "quarantine_path"
            ]
        )

        destination = Path(
            metadata[
                "original_path"
            ]
        )


        if destination.exists():

            raise FileExistsError(
                (
                    "Restore destination already exists: "
                    f"{destination}"
                )
            )


        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        shutil.move(
            str(source),
            str(destination)
        )


        metadata_path.unlink(
            missing_ok=True
        )


        return str(
            destination
        )


    def permanently_delete(
        self,
        item_id
    ):

        (
            metadata_path,
            metadata
        ) = self._load_item(
            item_id
        )


        payload_path = Path(
            metadata[
                "quarantine_path"
            ]
        )


        payload_path.unlink(
            missing_ok=True
        )

        metadata_path.unlink(
            missing_ok=True
        )


        return True

