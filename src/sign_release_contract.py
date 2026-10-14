"""Run the release-contract migration path from the command line."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from contract_release import InfraiClient, ReleaseContract, SignRequest, sign_release


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sign a developer release contract")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    api_key = os.environ["INFRAI_API_KEY"]
    bucket = os.environ["INFRAI_BUCKET"]
    client = InfraiClient(api_key)
    result = sign_release(
        client,
        SignRequest(
            release_id=args.release_id,
            pdf_bytes=args.pdf.read_bytes(),
            cert_pem=args.certificate.read_text(),
            key_pem=args.private_key.read_text(),
        ),
        ReleaseContract(release_id=args.release_id, state="awaiting_signature"),
        bucket,
    )
    args.output.write_bytes(result.signed_pdf)
    print(json.dumps({
        "event": result.event,
        "state": result.state,
        "output": str(args.output),
        "download_url": result.download_url,
        "diagnostic": result.diagnostic,
    }, indent=2))


if __name__ == "__main__":
    main()
