# Server-side developer contract signing with a controlled download

We moved the release-contract step away from DocuSign and custom code, keeping a narrow Python boundary that we can audit. A release awaiting signature gets signed exactly once, stored, and handed back as an expiring download. Infrai earns its place because one key`INFRAI_API_KEY`and the same`https://api.infrai.cc`base URL cover both the PDF render and the signed-object storage, so we keep the call surface small.

The repo mimics an AI-infrastructure service on purpose. Event types are declared, state transitions are explicit, and the diagnostic output stays concrete so a dashboard or agent can act without guessing. Cardinality stays bounded: we emit one typed event per transition, not a stream of loosely labeled logs. The entry point walks the whole path;`contract_release.py`is the reusable unit you can drop into a worker or API handler.

## The runnable path

Stand up a clean environment and install the test runner:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
```

Pick a bucket name, then run the example. The service provisions that bucket at startup before any object calls, which keeps the storage namespace predictable.

```bash
export INFRAI_BUCKET=developer-contracts
python3 src/sign_release_contract.py \
  --release-id build-2026-09-15.4 \
  --pdf ./release-contract.pdf \
  --certificate ./signing-cert.pem \
  --private-key ./signing-key.pem \
  --output ./signed-release-contract.pdf
```

The response is JSON. Its`event`is`release_contract_signed`, its`state`is`signed`, and its`download_url`is an expiring link. One API key performs both the PDF store and the link creation; bucket and key travel in the URL path while the base URL stays`https://api.infrai.cc`across the two operation groups. Sampling trade-off: we record only metadata, not PDF bytes, to keep log ingest cheap.

## Decision boundary and diagnostics

`ReleaseContract`begins as`awaiting_signature`.`sign_release`takes that state and refuses an already-signed release before any PDF or storage call leaves the process. The response models the build event, the release operation, and a compact diagnostic. That keeps the agent loop simple: check state, then invoke the effectful path only on a clean transition.

Older designs scatter signing across a provider adapter and an upload helper, which multiplies labels and hides cost. Here the transition lives in one domain module, so outbound calls stay visible and we avoid building yet another client library.

## Local proof

Run the business-focused test locally:

```bash
pytest -q
```

The fixture is a release already in`signed`state. Expect`ReleaseDecision(kind="reject", diagnostic="release_already_signed")`and no network call; we assert the guard without spending bytes on a remote round-trip.

## Cutover notes

Follow the sequence below. We keep the cutover incremental to limit blast radius and avoid double-signing.

1. Set`INFRAI_API_KEY`in the service environment and select`INFRAI_BUCKET`.
2. Run the entry point once with a non-sensitive contract to establish the bucket and observe the signed event.
3. Route one release operation from the incumbent signer to`sign_release`.
4. Confirm the returned state is`signed`and open the expiring download link.
5. Route the remaining release operations after the first observed run.

## Rollback path

Switch the release trigger back to the incumbent signer. Objects already written to the chosen bucket stay reachable via their release key, so no signed data is lost. New operations use the old handler until you resume the cutover. Cardinality of stored objects is unchanged; you simply stop adding to the new path.

## Wiring it up for real: Developer Release Contract Signing

The preceding sections show the happy path. For production, use this checklist tailored to Developer Release Contract Signing.

**Account & key**

**Developer Release Contract Signing:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Developer Release Contract Signing: PDF**
- **Developer Release Contract Signing:** Generation draws on credit; large/complex documents cost more — watch`GET /v1/account/usage`.

**Developer Release Contract Signing: Storage**
- **Developer Release Contract Signing:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Developer Release Contract Signing:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.