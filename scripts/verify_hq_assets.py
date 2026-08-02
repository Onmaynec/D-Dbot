from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "images_hq"
MANIFEST = ASSETS / "SHA256SUMS"


def main() -> None:
    missing: list[str] = []
    invalid: list[str] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        expected, filename = line.split("  ", 1)
        path = ASSETS / filename
        if not path.exists():
            missing.append(filename)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            invalid.append(f"{filename}: {actual}")
    if missing or invalid:
        details = []
        if missing:
            details.append("missing=" + ", ".join(missing))
        if invalid:
            details.append("invalid=" + ", ".join(invalid))
        raise SystemExit("HQ asset verification failed: " + "; ".join(details))
    print("HQ PNG assets match the original upload checksums.")


if __name__ == "__main__":
    main()
