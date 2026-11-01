from __future__ import annotations

from pathlib import Path


class SecurityAnomalyService:
    """
    Read-only heuristic scoring for network-active processes.

    This service does NOT declare a process malicious.
    It only identifies combinations that deserve review.

    Levels:
        NORMAL      0-19
        REVIEW      20-39
        SUSPICIOUS  40-69
        HIGH        70+
    """

    COMMON_OUTBOUND_PORTS = {
        53,     # DNS
        80,     # HTTP
        123,    # NTP
        443,    # HTTPS
        465,    # SMTPS
        587,    # SMTP submission
        993,    # IMAPS
        995,    # POP3S
        3478,   # STUN
        5228,   # push services
    }

    def score_process(self, item: dict) -> dict:
        score = 0
        reasons: list[str] = []

        name = str(item.get("name") or "UNKNOWN")
        exe = str(item.get("exe") or "")
        external = int(item.get("external") or 0)
        connections = int(item.get("connections") or 0)
        listening = int(item.get("listening") or 0)
        remote_ports = {
            int(port)
            for port in (item.get("remote_ports") or [])
            if str(port).isdigit()
        }

        path_lower = exe.lower().replace("/", "\\")
        name_lower = name.lower()

        # -------------------------------------------------
        # LOCATION HEURISTICS
        # -------------------------------------------------

        if "\\temp\\" in path_lower or path_lower.endswith("\\temp"):
            score += 45
            reasons.append("EXECUTABLE RUNNING FROM TEMP")

        if "\\downloads\\" in path_lower:
            score += 35
            reasons.append("EXECUTABLE RUNNING FROM DOWNLOADS")

        if "\\appdata\\local\\temp\\" in path_lower:
            score += 20
            reasons.append("USER TEMP EXECUTION")

        elif "\\appdata\\" in path_lower:
            # Many legitimate apps live here, so keep this mild.
            score += 6
            reasons.append("USER PROFILE EXECUTION")

        # Expected system/program install locations reduce location concern.
        trusted_location = (
            "\\windows\\system32\\" in path_lower
            or "\\windows\\syswow64\\" in path_lower
            or "\\program files\\" in path_lower
            or "\\program files (x86)\\" in path_lower
        )

        # -------------------------------------------------
        # CONNECTION VOLUME
        # -------------------------------------------------

        if external >= 30:
            score += 22
            reasons.append(f"HIGH EXTERNAL CONNECTION COUNT ({external})")

        elif external >= 15:
            score += 12
            reasons.append(f"ELEVATED EXTERNAL CONNECTION COUNT ({external})")

        elif external >= 8:
            score += 5

        # -------------------------------------------------
        # LISTEN + OUTBOUND COMBINATION
        # -------------------------------------------------

        if listening >= 1 and external >= 1:
            score += 14
            reasons.append("LISTENING AND OUTBOUND TRAFFIC")

        if listening >= 4:
            score += 8
            reasons.append(f"MULTIPLE LISTENING SOCKETS ({listening})")

        # -------------------------------------------------
        # UNCOMMON REMOTE PORTS
        # -------------------------------------------------

        unusual = sorted(
            port
            for port in remote_ports
            if port not in self.COMMON_OUTBOUND_PORTS
            and port > 0
        )

        if unusual:
            score += min(12, 3 + len(unusual) * 2)
            reasons.append(
                "UNCOMMON REMOTE PORTS: "
                + ",".join(str(port) for port in unusual[:4])
            )

        # -------------------------------------------------
        # LOW-CONTEXT / UNKNOWN PROCESS
        # -------------------------------------------------

        if (
            not exe
            and name_lower not in {"system", "unknown"}
            and external >= 5
        ):
            score += 8
            reasons.append("EXECUTABLE PATH UNAVAILABLE")

        # Reduce purely volume-driven concern for software installed in
        # standard Windows/Program Files locations. This cannot erase
        # strong Temp/Downloads findings.
        if trusted_location and score < 40:
            score = max(0, score - 8)

        score = min(100, max(0, score))

        if score >= 70:
            level = "HIGH"
        elif score >= 40:
            level = "SUSPICIOUS"
        elif score >= 20:
            level = "REVIEW"
        else:
            level = "NORMAL"

        enriched = dict(item)
        enriched["risk_score"] = score
        enriched["risk_level"] = level
        enriched["risk_reasons"] = reasons

        return enriched


    def analyze_processes(self, processes: list[dict]) -> dict:
        scored = [
            self.score_process(item)
            for item in processes
        ]

        scored.sort(
            key=lambda item: (
                int(item.get("risk_score") or 0),
                int(item.get("external") or 0),
                int(item.get("connections") or 0),
            ),
            reverse=True,
        )

        findings = [
            item
            for item in scored
            if item.get("risk_level") in {
                "REVIEW",
                "SUSPICIOUS",
                "HIGH",
            }
        ]

        highest_score = max(
            [
                int(item.get("risk_score") or 0)
                for item in scored
            ],
            default=0,
        )

        if highest_score >= 70:
            network_level = "HIGH"
        elif highest_score >= 40:
            network_level = "SUSPICIOUS"
        elif highest_score >= 20:
            network_level = "REVIEW"
        else:
            network_level = "SECURE"

        return {
            "processes": scored,
            "findings": findings,
            "finding_count": len(findings),
            "highest_score": highest_score,
            "network_level": network_level,
        }
