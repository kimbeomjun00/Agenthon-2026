from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfbench2_common.contracts.descriptor import (
    SubmissionDescriptor,
    seal_descriptor_digest,
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Create a packable Agenthon T2 Development descriptor for V11."
    )
    ap.add_argument("--digest", required=True, help="sha256:<64 hex> image/index digest")
    ap.add_argument("--out", default="submission_v11.json")
    args = ap.parse_args()

    digest = args.digest.strip()
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise SystemExit("digest must be sha256:<64 lowercase/uppercase hex chars>")
    try:
        int(digest[7:], 16)
    except ValueError:
        raise SystemExit("digest contains non-hex characters")

    body = {
        "schema_version": "1.0.0",
        "interface_version": "2.0",
        "competition_id": "agenthon2026-forecasting-dev",
        # team_id intentionally omitted before `qfbench2 submission pack`
        "track": "forecasting",
        "phase": "dev",
        "category": "api",
        "image": {
            "registry": "docker.io",
            "repository": "kbj710211/agenthon-t2-v11",
            "digest": digest.lower(),
        },
        "image_access": "public",
        "models": [
            {
                "name": "nvidia/nemotron-3-super-120b-a12b",
                "version": "rl-030326-fp8",
                "revision": "rl-030326-fp8",
                "training_cutoff": "unpublished",
                "access": "api",
            }
        ],
        "license": "MIT",
    }

    # Packable pre-team descriptor.
    packable = seal_descriptor_digest(body)

    # Validate all ordinary descriptor fields using a temporary team id.
    validation_body = dict(body)
    validation_body["team_id"] = "team-validation-placeholder"
    validated = seal_descriptor_digest(validation_body)
    SubmissionDescriptor.from_mapping(validated)

    out = Path(args.out)
    out.write_text(
        json.dumps(packable, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("Wrote:", out.resolve())
    print("Repository:", packable["image"]["repository"])
    print("Image digest:", packable["image"]["digest"])
    print("Pre-pack team_id present:", "team_id" in packable)
    print("VALID: non-team descriptor fields passed parser validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())