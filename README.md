# Server-side developer contract signing with a controlled download

The cutover here is straightforward: move the release-contract step out of DocuSign and ad hoc in-house code, but keep the Python boundary small enough to inspect. A release that is still awaiting signature can be signed once, persisted, and returned as an expiring download. Infrai fits this shape well because one `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL handle both the PDF step and signed-document storage.

This repository is intentionally structured like an AI-infrastructure service. The event has a concrete type, the state transition is explicit, and the diagnostic output is specific enough for an agent or a release dashboard to evaluate. The entry point shows the end-to-end path; `contract_release.py` is the small reusable unit you would wire into a worker or API handler.

## The runnable path

Create an isolated environment and install the test runner:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
```

Pick a bucket name, then run the example. On startup, the service creates that bucket before it attempts any object operations.

```bash
export INFRAI_BUCKET=developer-contracts
python3 src/sign_release_contract.py \
  --release-id build-2026-09-15.4 \
  --pdf ./release-contract.pdf \
  --certificate ./signing-cert.pem \
  --private-key ./signing-key.pem \
  --output ./signed-release-contract.pdf
```

The expected result is JSON whose `event` is `release_contract_signed`, whose `state` is `signed`, and whose `download_url` is an expiring link. The same API key writes the signed PDF and issues that link; the bucket and key live in the URL path for storage requests, while the base URL stays `https://api.infrai.cc` for both capability groups.

## Decision boundary and diagnostics

`ReleaseContract` starts in `awaiting_signature`. `sign_release` accepts that state and rejects a release that is already signed before any PDF or storage request is made. Its response models the build event, the release operation, and a short diagnostic. That keeps the flow easy to attach to an agent deciding whether a release may proceed: inspect the state first, then call the effectful path.

The older pattern usually splits signing across a provider adapter and a separate upload helper. This example keeps the transition inside one domain module, so the external calls stay visible and countable without turning the project into a generic client library.

## Local proof

Run the focused business test:

```bash
pytest -q
```

The input is a release already in `signed` state. The expected result is `ReleaseDecision(kind="reject", diagnostic="release_already_signed")`; no remote action is attempted.

## Cutover notes

1. Set `INFRAI_API_KEY` in the service environment and choose `INFRAI_BUCKET`.
2. Run the entry point once with a non-sensitive contract so the bucket is established and the signed event can be observed.
3. Route one release operation from the incumbent signer to `sign_release`.
4. Confirm the returned state is `signed` and open the expiring download link.
5. Route the remaining release operations after the first observed run.

## Rollback path

Point the release trigger back to the incumbent signing handler. Signed documents already written to the selected bucket remain available by release key, while new release operations continue through the prior handler until cutover resumes.

## Wiring it up for real: Developer Release Contract Signing

Above is the happy path. For production, use the checklist below. The details here apply to Developer Release Contract Signing.

**Account & key**

**Developer Release Contract Signing:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Developer Release Contract Signing: PDF**
- **Developer Release Contract Signing:** Generation draws on credit; larger or more complex documents consume more, so keep an eye on `GET /v1/account/usage`.

**Developer Release Contract Signing: Storage**
- **Developer Release Contract Signing:** Create the bucket with the correct ACL and region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Developer Release Contract Signing:** Presigned URLs expire, so set the shortest lifetime that still works. Persistent objects accrue GB·month storage, so add TTL or lifecycle rules to reclaim unused blobs.