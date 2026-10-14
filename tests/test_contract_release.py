from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contract_release import InfraiClient, ReleaseContract, SignRequest, decide_release, sign_release


def test_signed_release_is_rejected_before_signing() -> None:
    decision = decide_release(ReleaseContract(release_id="build-42", state="signed"))

    assert decision.kind == "reject"
    assert decision.diagnostic == "release_already_signed"


def test_sign_release_stores_pdf_and_returns_presigned_url() -> None:
    class Client(InfraiClient):
        def __init__(self) -> None:
            self.calls = []

        def sign_pdf(self, request: SignRequest) -> bytes:
            self.calls.append(("sign", request.release_id))
            return b"signed-pdf"

        def create_bucket(self, bucket: str) -> None:
            self.calls.append(("create_bucket", bucket))

        def put_object(self, bucket: str, key: str, data: bytes) -> None:
            self.calls.append(("put_object", bucket, key, data))

        def presign_object(self, bucket: str, key: str) -> str:
            self.calls.append(("presign_object", bucket, key))
            return "https://download.example/signed"

    request = SignRequest("build-42", b"pdf", "cert", "key")
    client = Client()
    result = sign_release(
        client, request, ReleaseContract("build-42", "awaiting_signature"), "contracts"
    )

    assert result.signed_pdf == b"signed-pdf"
    assert result.download_url == "https://download.example/signed"
    assert result.diagnostic == "signed_document_ready"
    assert client.calls == [
        ("sign", "build-42"),
        ("create_bucket", "contracts"),
        ("put_object", "contracts", "build-42.pdf", b"signed-pdf"),
        ("presign_object", "contracts", "build-42.pdf"),
    ]
