# Azure Blob connector live validation plan

Status: planning only; no Azure live tests executed in this review.

## Reference review

Reviewed the current description and discussion of https://github.com/topoteretes/cognee-community/pull/452 and all 16 linked evidence images from evidence commit bc4ab8560613b5485f96afd3413f2c21d3315790. Inspected the raw inventories, result JSON, verification notes, and Cognee 1.6.5 final-document cleanup record. Also reviewed https://github.com/topoteretes/cognee/issues/4762, including the linked comment.

The GCS evidence pairs genuine Console screenshots with tables rendered from measured results. The tables show object name, byte size, content preview, action and download behavior; they are test reports. The raw bundle supplies inventories, staging rows, graph/Data snapshots, vector counts and search responses.

The reference's original broad live matrix used Cognee 1.4.0; only its final-document regression was repeated on 1.6.5. Its later extension-filter/refactor changes were tested offline. For Azure, run the full matrix against the actual current code with locked dependencies and record versions and the working diff. Do not reuse GCS results as Azure evidence.

## 1. Prepare an isolated, reproducible run

- Inspect the existing uncommitted azure_blob.py changes and applicable repository instructions; preserve existing work.
- Record commit, source hash/diff and locked Cognee/dlt/Azure SDK versions; use Cognee 1.6.5 as pinned by this package.
- Load the existing worktree-root .env explicitly, never printing keys. Supply container cognee-validation and prefix docs/ directly as arguments.
- Verify account endpoint and read/list access to the dedicated test container before any model calls.
- Configure real DeepSeek extraction/search and local fastembed BAAI/bge-small-en-v1.5 embeddings, following the reference. Confirm model availability and one small embedding operation.
- Keep validation databases, dlt pipelines, graph/vector stores and output artifacts isolated from other Cognee datasets. Preserve pipeline state across main-matrix steps. Use separate destinations for fresh-prefix and final-document tests.
- Use foreground cognee.remember, merge, primary_key=id, max_rows_per_table=0, self_improvement=False. Check returned completion status.
- Run existing locked pytest and Ruff checks once as a baseline. These are offline coverage, not proof of live Azure behavior.

## 2. Prepare matching synthetic fixtures

Use max_object_size=1024 bytes and max_objects=12 for the main matrix. Create seven eligible text blobs: below-limit.txt (1023 bytes), at-limit.txt (1024), delete-me.txt, empty.txt (0), support.txt, unicode.txt and update-me.txt. Add above-limit.txt (1025 bytes), a zero-byte folder placeholder, and outside-prefix.txt at the container root. Use unique, harmless facts for search and deletion checks. Save exact bytes and hashes locally.

Use separate prefixes/datasets for extension/encoding tests and the final-document regression so additional fixtures do not change the reference matrix counts.

## 3. Main live matrix

| Step | Change or action | Required checks |
| --- | --- | --- |
| 01 Initial sync | Upload main fixtures; ingest docs/ | Seven eligible blobs downloaded/staged; 1023 and 1024 bytes accepted, 1025 skipped; empty/Unicode handled; folder ignored; outside-prefix absent. Distinguish staging acceptance from graph creation for empty text. Search retrieves a known fact. |
| 02 Unchanged rerun | Run again with the same state, including a new process | Zero content downloads, same document IDs and hashes, no duplicate staging/Data records, persistent inventory. |
| 03 Overwrite | Replace update-me.txt with a different known fact | Only the changed blob downloads; Last-Modified/ETag advance; same stable document ID; updated staging/Data/graph and search. Inspect old content artifacts for stale memory. |
| 04 Delete one | Delete delete-me.txt while others remain | Confirm BlobNotFound; deletion marker removes its staging/Data and document-associated graph/vector artifacts; remaining documents stay. Check search and stored contents. |
| 05 Add and oversize | Add new-document.txt and grow support.txt beyond 1024 bytes | New document downloads; now-ineligible prior document leaves staging/Data and associated graph/vector memory. Other documents retained. |
| 06 Metadata edit | Change metadata on unicode.txt without changing content | Record Last-Modified/ETag before/after, measured download count, unchanged content hash and stable ID; no duplicate memory. Azure's current implementation downloads changed cursor pairs, unlike GCS's metadata-only no-download behavior. |
| 07 Fresh prefix | New isolated destination against later container state | Full eligible in-prefix snapshot loads despite an unchanged upstream inventory in the main destination; outside-prefix remains excluded. |
| 08 Count limit | Set max_objects below the measured non-folder object count | Fail before content downloads; preserve inventory and previously committed staging/Data. Repeat with a permissible limit to prove recovery. Count unsupported/oversized blobs too. |
| 09 Final document | Isolated prefix/dataset: ingest one nonempty blob, then delete it | Before: one Data document and nonempty graph/vectors. After successful sync: zero staging rows, zero Data, zero graph nodes/edges and zero rows in all inspected vector tables. Search returns NoDataError or documented empty result. |

For partial deletions, inspect document-associated records and unique fixture facts rather than requiring all shared graph entities to disappear. Inspect vector state before search and record search-created artifacts separately.

## 4. Additional coverage for the current Azure implementation

- Live text-format cases in a separate scope: supported extensions including uppercase, unsupported binary/extensionless objects skipped before download, UTF-8 BOM and replacement decoding for invalid UTF-8.
- Account-key authentication is the live path already configured. SAS precedence, ownership and secret-free URLs are covered by offline tests; only claim live SAS validation if an actual authorized token is tested.
- Live Azure-specific ETag race: overwrite after listing and before a real download; verify conditional failure leaves committed state unchanged and retry recovers. Exercise disappearance after listing in a controlled test scope.
- Controlled bad credential or missing-container failure with isolated state: no accidental deletion or inventory advancement; keep secrets out of error logs.
- Pagination, incomplete-page failures, permission errors, retries, reappearance and destination/account scoping: use existing deterministic tests; add focused checks only for uncovered behavior. Clearly label simulated failure coverage. A forced small-page live SDK check can supplement it if supported without changing connector behavior.
- Do not claim default-scale volume testing, historical-version reads, archive rehydration, or PDF/DOCX/image extraction.

## 5. Evidence collection and acceptance

At each state-changing live step, capture the Azure Portal showing the actual container/blob state, and save its corresponding measured result table. For unchanged/count checks, a result table is sufficient unless a portal view adds useful evidence. Include metadata properties for the Azure cursor test and before/after views for final deletion.

Each raw result records scenario/time, exact versions/source hash, container/prefix/dataset, limits, blob inventory and Last-Modified/ETag, actual SDK downloads/bytes, row hashes and stable IDs, dlt inventory/load status, Data records, graph counts/snapshots, vector counts and search output. Sanitize SAS strings, account/LLM keys and credential-bearing exceptions. Tables must be rendered from these records, not manually assigned success labels.

Use statuses added, updated, unchanged, removed, skipped, excluded and failed, with precise reasons. Preserve last known previews for deleted blobs and label them accordingly. Show raw byte sizes even when the portal rounds them. Name screenshots/results sequentially and create a checksum manifest and evidence index. Preserve failures and retest logs; report failures honestly.

## 6. Draft PR after validation

Only after actual results and screenshots are complete, prepare a draft PR containing the implementation summary, issue link, exact test versions and counts, supported formats and limits, the nine scenario descriptions with matching evidence, Azure-specific metadata behavior, and reproducible commands. Link the raw sanitized evidence. Report separate live and offline coverage and any unresolved limitations. Do not mark the PR ready for review.
