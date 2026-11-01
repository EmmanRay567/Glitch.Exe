from pathlib import Path
from tempfile import TemporaryDirectory

from services.file_scanner_service import (
    FileScannerService
)

from services.quarantine_service import (
    QuarantineService
)

from services.security_engine import (
    SecurityEngine
)


def main():

    with TemporaryDirectory() as temp_dir:

        root = Path(
            temp_dir
        )

        quarantine_dir = (
            root
            / "quarantine"
        )


        scanner = (
            FileScannerService(
                max_file_size_mb=20
            )
        )


        quarantine = (
            QuarantineService(
                quarantine_dir
            )
        )


        engine = (
            SecurityEngine(
                file_scanner=scanner,
                quarantine_service=quarantine
            )
        )


        normal_file = (
            root
            / "notes.txt"
        )

        normal_file.write_text(
            "hello glitch",
            encoding="utf-8"
        )


        suspicious_file = (
            root
            / "invoice.pdf.exe"
        )

        suspicious_file.write_bytes(
            b"MZ"
            + b"\x00" * 128
        )


        print(
            "NORMAL:"
        )

        normal_result = (
            engine.scan_file(
                normal_file
            )
        )

        print(
            normal_result.to_dict()
        )


        print(
            "\nSUSPICIOUS:"
        )

        suspicious_result = (
            engine.scan_file(
                suspicious_file
            )
        )

        print(
            suspicious_result.to_dict()
        )


        print(
            "\nQUARANTINE:"
        )

        metadata = (
            engine.quarantine(
                suspicious_result
            )
        )

        print(
            metadata
        )


        restored = (
            engine.restore_quarantine_item(
                metadata["id"]
            )
        )

        print(
            "\nRESTORED:",
            restored
        )


if __name__ == "__main__":

    main()

