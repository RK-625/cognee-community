# Azure Blob connector: real-life validation evidence

Validated on 20 October 2026 against a real private Azure Blob container with account-key authentication, real DeepSeek extraction/search (`openai/deepseek-flash`, custom provider), and non-mocked local fastembed `BAAI/bge-small-en-v1.5` embeddings (384 dimensions). No embedding API key was needed.

All nine planned primary scenarios passed. Supplemental live source/dlt checks passed. The evidence audit passed all 18 assertions; offline pytest passed 61 cases and Ruff passed. Expected failure tests are retained as failure evidence, followed by successful recovery.

## Tested build

- Commit: `972c8897790f739255e0d7385c7e54ef83c67f5b` (azure-blob worktree).
- Connector SHA-256: `e08712992cdc1ee5e33f71581d50f0162b2c18cbbd8f205879d9dfdc17db0ab4`.
- Python 3.13.5; Cognee 1.6.5; dlt 1.30.0; fastembed 0.8.0; azure-storage-blob 12.31.0; azure-core 1.41.0.
- Storage account `cogneeazblob20261020`, private container `cognee-validation`, Central India, Standard LRS.
- Main scope `docs/`; max size 1024 bytes; max count 12. Count guard deliberately lowers count to 7 against 8 non-folder blobs.
- Final scope `final/`; format scope `formats/`; race scope `race/`. All use isolated local storage; main state persists across separate processes.

## Measured scenario results

| Scenario | Content downloads | Staging / Data | Graph nodes / edges | Result |
| --- | ---: | ---: | ---: | --- |
| [Initial ingestion and boundaries](reports/01-initial.png) | 7 | 7 / 7 | 41 / 42 | Passed |
| [New-process unchanged rerun](reports/02-unchanged.png) | 0 | 7 / 7 | 41 / 42 | Passed |
| [Overwrite](reports/03-update.png) | 1 | 7 / 7 | 41 / 42 | Passed |
| [Delete one document](reports/04-delete.png) | 0 | 6 / 6 | 32 / 31 | Passed |
| [New document + oversized cleanup](reports/05-add-oversize.png) | 1 | 6 / 6 | 33 / 34 | Passed |
| [Metadata-only edit](reports/06-metadata.png) | 1 | 6 / 6 | 33 / 34 | Passed |
| [Fresh destination](reports/07-fresh.png) | 6 | 6 / 6 | 33 / 34 | Passed |
| [Expected count-limit failure](reports/08-count-guard.png) | 0 | 6 / 6 | 33 / 34 | Expected failure; state preserved |
| [Recovery](reports/08-count-recovery.png) | 0 | 6 / 6 | 33 / 34 | Passed |
| [Final-document before deletion](reports/09-final-before.png) | 1 | 1 / 1 | 7 / 7 | Passed |
| [Final-document after deletion](reports/09-final-after.png) | 0 | 0 / 0 | 0 / 0 | Passed |

The first sync accepts seven text blobs, including 1023/1024-byte boundaries, empty content and Unicode. It skips a 1025-byte blob and folder placeholder, and excludes the root-level file. An unchanged new-process rerun downloads zero blobs. Overwrite downloads one blob, preserves its source URL ID, removes the old Monday fact from current graph/vector text, and search returns Friday at 3 PM.

Deletion removes the Zephyr document and its stored facts; search no longer knows the access phrase. Adding Polaris while growing Calypso support to 1115 bytes downloads only Polaris and removes Calypso memory. Polaris search returns silver otter. Six documents remain. The fresh destination independently downloads all six.

A metadata edit changes ETag and Last-Modified while retaining the content hash. Azure therefore downloads that one blob again; Data and graph do not duplicate. This differs from the GCS metadata-only zero-download case.

Final deletion changes staging/Data from 1/1 to 0/0 and graph nodes/edges from 7/7 to 0/0. All seven inspected vector tables are zero (`DocumentChunk_text`, `EdgeType_relationship_name`, `EntityType_name`, `Entity_name`, `SessionQAVector_text`, `TextDocument_name`, `TextSummary_text`). Search raises the expected `NoDataError`.

## Screenshot and report index

The `screenshots/` PNGs are genuine Azure Portal captures. The `reports/` PNGs are tables rendered from the raw recorded JSON; they are explicitly labeled test reports. No report is presented as a portal screenshot. Exact byte sizes come from Azure SDK inventory; portal sizes may be rounded. Deleted content previews are labeled last-known. Padding is omitted from table previews and preserved in raw content.

| Scenario | Genuine portal evidence | Measured report | Raw result |
| --- | --- | --- | --- |
| Initial ingestion and boundaries | [Portal 1](screenshots/00-outside-prefix-portal.png) / [Portal 2](screenshots/01-initial-portal.png) | [Report](reports/01-initial.png) | [JSON](evidence/01-initial-result.json) |
| New-process unchanged rerun | See unchanged source state above | [Report](reports/02-unchanged.png) | [JSON](evidence/02-unchanged-result.json) |
| Overwrite | [Portal 1](screenshots/03-update-portal.png) | [Report](reports/03-update.png) | [JSON](evidence/03-update-result.json) |
| Delete one document | [Portal 1](screenshots/04-delete-portal.png) | [Report](reports/04-delete.png) | [JSON](evidence/04-delete-result.json) |
| New document + oversized cleanup | [Portal 1](screenshots/05-add-oversize-portal.png) | [Report](reports/05-add-oversize.png) | [JSON](evidence/05-add-oversize-result.json) |
| Metadata-only edit | [Portal 1](screenshots/06-metadata-properties-before-refresh.png) / [Portal 2](screenshots/06-metadata-properties-portal.png) / [Portal 3](screenshots/06-metadata-values-portal.png) | [Report](reports/06-metadata.png) | [JSON](evidence/06-metadata-result.json) |
| Fresh destination | See unchanged source state above | [Report](reports/07-fresh.png) | [JSON](evidence/07-fresh-result.json) |
| Expected count-limit failure | See unchanged source state above | [Report](reports/08-count-guard.png) | [JSON](evidence/08-count-guard-result.json) |
| Recovery | See unchanged source state above | [Report](reports/08-count-recovery.png) | [JSON](evidence/08-count-recovery-result.json) |
| Final-document before deletion | [Portal 1](screenshots/09-final-before-portal.png) | [Report](reports/09-final-before.png) | [JSON](evidence/09-final-before-result.json) |
| Final-document after deletion | [Portal 1](screenshots/09-final-after-portal.png) | [Report](reports/09-final-after.png) | [JSON](evidence/09-final-after-result.json) |
| Supplemental live checks | [Formats top](screenshots/10-formats-top-portal.png) / [bottom](screenshots/10-formats-bottom-portal.png) | [Report](reports/10-extra-live.png) | [JSON](evidence/10-extra-live.json) |

The metadata properties pane was opened before mutation. Its original values were captured before refreshing the pane; the next properties screenshot shows refreshed ETag/Last-Modified, and the scrolled screenshot shows the custom metadata values. Raw mutation JSON records both live before/after properties.

## Supplemental live and offline coverage

Live source + real SQLite dlt checks accept all 12 allowed extensions, uppercase TXT, BOM text and invalid UTF-8 replacement: 15 rows. Unsupported PDF/extensionless blobs are skipped without downloads. A forced two-entry Azure page size consumes nine real pages.

A controlled real overwrite immediately before download triggers an If-Match `ConditionNotMet` failure; committed rows and cursor remain unchanged. Retry commits the latest content. A real missing-container failure preserves committed state. A blob deleted immediately before download returns BlobNotFound and removes the final source row. Mutation timing is controlled by observer wrappers around real SDK clients; Azure responses are not simulated. These supplemental checks do not call an LLM.

Main scenario SDK wrappers record actual download attempts, payload bytes/hashes and direct missing checks. Cognee ingestion, extraction, embeddings and graph search run normally. The factory is wrapped to use an observed real client with the same account-key authentication; no connector production code was edited for these tests.

Offline tests cover SAS/key precedence, explicit configuration, client ownership, pagination failures, extraction rollback, reappearance, state/destination scoping and secret-free identities. Live authentication used an account key; live SAS authentication was not run. No scale, archive-tier rehydration, version-history or binary-document parsing claims are made. Extension tests check text extraction/allowlisting, not JSON/XML/HTML semantic parsing.

## Raw evidence and interpretation

- [Audit: 18 passed checks](evidence/validation-audit.json).
- [Successful live preflight](evidence/preflight-success.json).
- [Offline test log](logs/offline-tests.log): 61 passed, 49 dependency warnings; [Ruff](logs/ruff.log): all checks passed.
- Every primary scenario has `*-before-sql.json`, `*-after-sql.json`, `*-pipeline-state.json`, `*-memory.json` and `*-result.json`.
- SQL dumps retain staging text and Data metadata. Memory dumps retain graph nodes/edges plus vector text and counts, omitting numerical vectors for compactness.
- Vector counts are sampled before each search, which can itself create a SessionQAVector row. Later sync cleanup can remove stale search cache rows.
- The source URL ID is stable across overwrite; Cognee recreates its content-derived internal Data ID for changed content. The evidence does not claim the internal Data ID stays fixed.
- Empty source content is preserved as an empty string in staging. Cognee also ingests the title/URL envelope; its Data/graph counts do not imply semantic facts were extracted from zero bytes.
- Initial sandbox DNS/model access failures are retained in preflight logs. The authorized network run succeeded before fixture testing. A later 50-token model preflight retry exhausted its budget on reasoning and had empty final text; the full ingestion and graph searches completed successfully with actual responses.
- [Secret scan](evidence/secret-scan.json) finds no known credential values in publishable text or decoded dlt state. No `.env`, runtime databases, model cache or access-key screenshots are included.

## Reproduction

Use the package environment installed from its lockfile and an isolated, disposable Azure container. The bootstrap reads the worktree-root `.env` for the account URL/key and LLM config; it supplies container/prefix as direct arguments and sets local fastembed itself. No container/prefix environment variable is required. The fixture script refuses overwrites on `initial`. It deliberately edits/deletes only the named test fixtures on later actions.

```sh
export AZURE_VALIDATION_WORKTREE=/absolute/path/to/azure-blob-worktree
AZURE_TEST_PYTHON="$AZURE_VALIDATION_WORKTREE/packages/connector/azure-blob/.venv/bin/python"
"$AZURE_TEST_PYTHON" scripts/preflight.py
"$AZURE_TEST_PYTHON" scripts/fixtures.py initial
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 01-initial
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 02-unchanged
"$AZURE_TEST_PYTHON" scripts/fixtures.py update
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 03-update
"$AZURE_TEST_PYTHON" scripts/fixtures.py delete
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 04-delete --question "What is the Zephyr vault access phrase?"
"$AZURE_TEST_PYTHON" scripts/fixtures.py add-oversize
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 05-add-oversize --question "What is the Polaris project mascot?"
"$AZURE_TEST_PYTHON" scripts/fixtures.py metadata
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 06-metadata --no-search
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 07-fresh --scope fresh --no-search
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 08-count-guard --max-objects 7 --no-search --expect-failure
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 08-count-recovery --no-search
"$AZURE_TEST_PYTHON" scripts/fixtures.py final-upload
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 09-final-before --scope final --prefix final/ --question "What is the Solstice observatory telescope named?"
"$AZURE_TEST_PYTHON" scripts/fixtures.py final-delete
"$AZURE_TEST_PYTHON" scripts/run_scenario.py 09-final-after --scope final --prefix final/ --question "What is the Solstice observatory telescope named?"
"$AZURE_TEST_PYTHON" scripts/fixtures.py formats
"$AZURE_TEST_PYTHON" scripts/fixtures.py race-upload
"$AZURE_TEST_PYTHON" scripts/extra_live.py
"$AZURE_TEST_PYTHON" scripts/audit.py
```

Capture corresponding portal views after each mutation before advancing to the next step. All run data stays beneath the script root, isolated from other datasets. Rendering uses Pillow and macOS Arial fonts. [Original plan](scripts/PLAN.md).

## Draft PR readiness

All required live results and images are collected. Use the table and paired portal/report links for the draft PR validation section, in the same style as reference PR #452. Publish/upload the chosen sanitized assets when drafting the PR; these are currently local files. Keep the PR in draft status. Reference issue: topoteretes/cognee#4762.

The remaining Azure blobs are disposable validation fixtures (`docs/`, `formats/`, and the excluded root file). The final and race blobs were deleted as part of their tests. No storage account deletion or additional subscription was created during validation.

## PR presentation

[Latest PR preview with all 24 images](PR_PREVIEW.md). The `tables/` directory contains the concise table-only versions used in the PR.
