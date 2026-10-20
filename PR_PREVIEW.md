# feat(connector): add Azure Blob Storage sync

## Description

Adds an Azure Blob Storage connector that syncs text documents from a container prefix into Cognee. Runs download on new or changed files and removes documents from memory for deleted or oversized files.

Uses the [S3 connector implementation](https://github.com/topoteretes/cognee-community/pull/209) as the reference for extraction helpers and sync structure, adapted for Azure Last-Modified/ETag tracking and conditional downloads. Includes account-key/SAS authentication, persistent state, documentation, an example, and tests.

Closes [cognee#4762](https://github.com/topoteretes/cognee/issues/4762).

## Implementation

I kept the connector logic in `azure_blob.py`, following the S3 implementation’s structure. `azure_blob_source()` sets up the document source and coordinates incremental sync and deletion checks. I split the individual steps into these helpers:

| Helper | Role |
| --- | --- |
| `_build_client()` | Creates the Azure client using the account URL and credentials. |
| `_list_objects()` | Lists every page under the prefix, ignores empty folder placeholders, and enforces the object-count limit before downloads. |
| `_is_eligible()` | Checks the file extension and size limit. |
| `_read_object()` | Downloads against the listed ETag so a concurrent overwrite fails safely; skips a blob that disappeared. |
| `_decode()` | Decodes UTF-8, strips an optional BOM, and replaces invalid bytes. |
| `_object_to_row()` | Builds the document’s `id`, `url`, `title`, and `content` fields. |
| `_stamp()` | Records Last-Modified and ETag values for change detection. |
| `_scope()` | Separates source inventories by account, container, and prefix. |

Missing previously ingested blobs are checked directly before their documents are removed from memory.

The package exposes `azure_blob_source` through `__init__.py`. `examples/example.py` shows how to sync and search a dataset, `tests/` covers the helpers and sync behavior, and `README.md` explains setup and usage. Dependencies are defined in `pyproject.toml` and locked in `uv.lock`.

```text
packages/connector/azure-blob/
├── cognee_community_connector_azure_blob/
│   ├── __init__.py          # Public source export
│   └── azure_blob.py        # Connector and sync helpers
├── examples/
│   └── example.py          # Sync and search example
├── tests/
│   ├── conftest.py         # Isolated test environment
│   └── test_azure_blob.py  # Helper and sync tests
├── README.md               # Setup and usage
├── pyproject.toml          # Dependencies and package configuration
└── uv.lock                 # Locked dependency versions
```

## Tests

I ran the automated suite with mocked Azure clients and real temporary SQLite dlt destinations: **all 61 tests passed**. I covered credential precedence and client ownership; file types, size/count boundaries and decoding; unchanged reruns, updates and deletions; pagination failures, ETag races and reappearing blobs; and saved state across restarts and separate destinations. I also checked snapshot modes and recovery after failed extraction. **Ruff lint passed.** These tests run without Azure or model credentials; the live Azure checks follow below.

## Validation

I then tested the connector with real Azure Blob Storage, DeepSeek, and local embeddings on Cognee 1.6.5.

All live scenarios passed: initial ingestion, unchanged reruns, updates, deletion, size limits, metadata edits, independent destinations, count-limit recovery, and final-document cleanup. Additional live checks covered text formats, pagination, ETag races, and missing-container failures.

## Evidence

All 24 images are embedded below: **12 genuine Azure Portal screenshots and 12 tables rendered from recorded measurements**.

### Initial Sync

I uploaded seven eligible text files, a 1,025-byte file, an empty folder placeholder, and a file outside `docs/`. As expected, the seven eligible files were ingested and the others were skipped or excluded.

![Azure Portal — root file outside the selected prefix](screenshots/00-outside-prefix-portal.png)

![Azure Portal — initial test files](screenshots/01-initial-portal.png)

![Measured report — initial ingestion](tables/01-initial.png)

### Unchanged Rerun

I ran the sync again in a new process. As expected, it reused the saved state, downloaded nothing, and kept the same seven documents without duplicates.

![Measured report — unchanged rerun](tables/02-unchanged.png)

### File Update

I changed `update-me.txt` from Monday at nine AM to Friday at three PM. As expected, only that file downloaded and search returned "Friday at 3 PM".

![Azure Portal — overwritten file](screenshots/03-update-portal.png)

![Measured report — update and search result](tables/03-update.png)

### File Deletion

I deleted `delete-me.txt` from Azure. As expected, its document and facts were removed from memory while the other six documents remained.

![Azure Portal — file removed](screenshots/04-delete-portal.png)

![Measured report — deletion and search result](tables/04-delete.png)

### New File and Size Limit

I added a new document and grew `support.txt` to 1,115 bytes, above the 1,024-byte MAX FILE LIMIT  for this test. As expected, the new document was ingested and the oversized document was removed from memory.

![Azure Portal — new and oversized files](screenshots/05-add-oversize-portal.png)

![Measured report — addition and oversized cleanup](tables/05-add-oversize.png)

### Metadata Update

I changed only the Unicode file’s metadata. As expected, its changed ETag and Last-Modified triggered one download, while the content stayed identical and no duplicates appeared.

![Azure Portal — original properties before refreshing the pane](screenshots/06-metadata-properties-before-refresh.png)

![Azure Portal — refreshed properties](screenshots/06-metadata-properties-portal.png)

![Azure Portal — updated custom metadata](screenshots/06-metadata-values-portal.png)

![Measured report — metadata change](tables/06-metadata.png)

### Fresh Destination

I synced the same prefix into a fresh destination. As expected, it loaded all six eligible documents independently of the first destination’s saved state.

![Measured report — fresh destination](tables/07-fresh.png)

### Count Limit and Recovery

I lowered the MAX COUNT limit to seven while the prefix contained eight non-folder blobs. As expected, the sync stopped before downloads and preserved existing memory; restoring the limit allowed a successful retry.

![Measured report — expected count-limit failure](tables/08-count-guard.png)

![Measured report — successful recovery](tables/08-count-recovery.png)

### Final File Deletion

I ingested one document into an isolated dataset, then deleted it from Azure. As expected, staging, Data, graph nodes/edges, and all inspected vector tables became empty, and search returned `NoDataError`.

![Azure Portal — final document before deletion](screenshots/09-final-before-portal.png)

![Measured report — memory before deletion](tables/09-final-before.png)

![Azure Portal — empty prefix after deletion](screenshots/09-final-after-portal.png)

![Measured report — complete memory cleanup](tables/09-final-after.png)

### Formats and Failure Recovery

I uploaded the supported text formats and exercised pagination, an ETag race, a missing container, and a disappearing blob. As expected, 15 eligible files staged across nine pages, failures preserved committed state, and the recovery checks passed.

![Azure Portal — format fixtures, top](screenshots/10-formats-top-portal.png)

![Azure Portal — format fixtures, bottom](screenshots/10-formats-bottom-portal.png)

![Measured report — formats, pagination, and recovery](tables/10-extra-live.png)

[Raw evidence, exact versions, and reproduction steps](README.md).

Live authentication used an account key; SAS behavior was tested offline. Supported files are decoded as UTF-8 text; binary parsing and OCR are outside this change.

