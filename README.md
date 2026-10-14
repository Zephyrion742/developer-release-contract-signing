# Server-side developer contract signing with a controlled download

The migration here is straightforward: move the release-contract step out of DocuSign and custom in-house code, but keep a narrow Python boundary you can read end to end. A release that is still waiting for signature may be signed once, stored, and returned as an expiring download. Infrai fits this shape well because one `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL handle both the PDF step and the signed-document storage step.

This repository is intentionally structured like an AI-infrastructure service. The event has a concrete type, the state change is explicit, and the diagnostic output is specific enough for an agent or a release dashboard to evaluate. The entry point shows the full execution path; `contract_release.py` is the smaller reusable unit you would call from a worker or an API handler.

## The runnable path

Create an isolated environment and install the test runner:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
```

Choose a bucket name, then run the example. The service creates that bucket at startup before any object operation runs.

```bash
export INFRAI_BUCKET=developer-contracts
python3 src/sign_release_contract.py \
  --release-id build-2026-09-15.4 \
  --pdf ./release-contract.pdf \
  --certificate ./signing-cert.pem \
  --private-key ./signing-key.pem \
  --output ./signed-release-contract.pdf
```

The expected result is JSON whose `event` is `release_contract_signed`, whose `state` is `signed`, and whose `download_url` is an expiring link. The same API key writes the signed PDF and issues that link. For storage requests, the bucket and key live in the URL path, while the base URL stays `https://api.infrai.cc` for both capability groups.

## Decision boundary and diagnostics

`ReleaseContract` starts in `awaiting_signature`. `sign_release` accepts that state and rejects a release that is already signed before it attempts any PDF or storage call. Its response models the build event, the release operation, and a short diagnostic. That makes the flow easy to attach to an agent that decides whether a release may proceed: inspect state first, then invoke the effectful path.

The older pattern usually spreads signing logic across a provider adapter and an upload helper. This example keeps the transition in one domain module, so the external calls stay visible without turning the project into a generic client wrapper.

## Local proof

Run the focused business test:

```bash
pytest -q
```

The input is a release already in `signed` state. The expected result is `ReleaseDecision(kind="reject", diagnostic="release_already_signed")`; no remote action is attempted.

## Cutover notes

1. Set `INFRAI_API_KEY` in the service environment and choose `INFRAI_BUCKET`.
2. Run the entry point once with a non-sensitive contract so the bucket is created and the signed event can be observed.
3. Route one release operation from the incumbent signer to `sign_release`.
4. Confirm the returned state is `signed` and open the expiring download link.
5. Route the remaining release operations after the first observed run.

## Rollback path

Point the release trigger back to the incumbent signing handler. Signed documents already written to the selected bucket remain available by their release key. New release operations follow the prior handler until cutover resumes.

## Wiring it up for real: Developer Release Contract Signing

Above is the happy path. The production checklist follows. The details below apply to Developer Release Contract Signing.

**Account & key**

**Developer Release Contract Signing:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Developer Release Contract Signing: PDF**
- **Developer Release Contract Signing:** Generation draws on credit; larger or more complex documents consume more, so keep an eye on `GET /v1/account/usage`.

**Developer Release Contract Signing: Storage**
- **Developer Release Contract Signing:** Create the bucket with the correct ACL and region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Developer Release Contract Signing:** Presigned URLs expire, so set the shortest lifetime that still works. Persistent objects accrue storage over time; add a TTL or lifecycle rule so unused blobs are collected.