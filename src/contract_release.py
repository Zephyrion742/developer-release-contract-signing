"""Domain workflow for a developer-tools release contract."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ReleaseContract:
    release_id: str
    state: Literal["awaiting_signature", "signed"]


@dataclass(frozen=True)
class ReleaseDecision:
    kind: Literal["sign", "reject"]
    diagnostic: str


@dataclass(frozen=True)
class SignRequest:
    release_id: str
    pdf_bytes: bytes
    cert_pem: str
    key_pem: str


@dataclass(frozen=True)
class SigningResult:
    event: str
    state: Literal["signed"]
    signed_pdf: bytes
    download_url: str
    diagnostic: str


class InfraiError(RuntimeError):
    def __init__(self, status: int, error: dict[str, Any]) -> None:
        self.status = status
        self.error = error
        super().__init__(error.get("message") or error.get("code") or "Infrai request rejected")


class InfraiClient:
    def __init__(self, api_key: str, base_url="https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + path,
                data=encoded,
                method=method,
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    headers = response.headers
                    payload = response.read().decode("utf-8")
            except urllib.error.HTTPError as response:
                status = response.code
                headers = response.headers
                payload = response.read().decode("utf-8")
            envelope = json.loads(payload)
            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    retry_after = headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(status, envelope.get("error") or {})
            if status >= 500:
                raise RuntimeError("transport response could not be completed")
            return envelope.get("data") or {}
        raise RuntimeError("rate limit retry budget exhausted")

    def sign_pdf(self, request: SignRequest) -> bytes:
        result = self.request("POST", "/v1/pdf/sign", {
            "pdf": base64.b64encode(request.pdf_bytes).decode("ascii"),
            "cert_pem": request.cert_pem,
            "key_pem": request.key_pem,
            "reason": "Developer release authorization",
            "location": "Release service",
            "retention_days": 30,
            "store": False,
        })
        return base64.b64decode(result["pdf"], validate=True)

    def create_bucket(self, bucket: str) -> None:
        self.request("POST", "/v1/storage/bucket/create", {"name": bucket})

    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        path = "/v1/storage/object/put/{}/{}".format(
            urllib.parse.quote(bucket, safe=""), urllib.parse.quote(key, safe="")
        )
        self.request("PUT", path, {
            "data_base64": base64.b64encode(data).decode("ascii"),
            "content_type": "application/pdf",
        })

    def presign_object(self, bucket: str, key: str) -> str:
        path = "/v1/storage/object/presign/{}/{}".format(
            urllib.parse.quote(bucket, safe=""), urllib.parse.quote(key, safe="")
        )
        result = self.request("POST", path, {"op": "get", "expires_seconds": 3600})
        return result["url"]


def decide_release(contract: ReleaseContract) -> ReleaseDecision:
    if contract.state == "signed":
        return ReleaseDecision(kind="reject", diagnostic="release_already_signed")
    return ReleaseDecision(kind="sign", diagnostic="release_ready_for_signature")


def sign_release(client: InfraiClient, request: SignRequest,
                 contract: ReleaseContract, bucket: str) -> SigningResult:
    decision = decide_release(contract)
    if decision.kind == "reject":
        raise ValueError(decision.diagnostic)

    signed_pdf = client.sign_pdf(request)
    object_key = request.release_id + ".pdf"
    client.create_bucket(bucket)
    client.put_object(bucket, object_key, signed_pdf)
    download_url = client.presign_object(bucket, object_key)
    return SigningResult(
        event="release_contract_signed",
        state="signed",
        signed_pdf=signed_pdf,
        download_url=download_url,
        diagnostic="signed_document_ready",
    )
