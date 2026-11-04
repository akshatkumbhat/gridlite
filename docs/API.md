# API reference

The browser calls these on the **gateway** (`http://localhost:4000`). The gateway answers `/api/health` itself and forwards everything else, unchanged, to Flask (`http://127.0.0.1:5001`).

`<table>` is the CSV file name, for example `sample_products.csv`. All responses are JSON unless noted. Errors look like `{"error": "message"}`.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Gateway status and whether Flask is reachable |
| GET | `/api/tables` | List tables |
| POST | `/api/tables` | Upload a CSV (form field `file`) |
| GET | `/api/tables/<table>/rows` | One page of rows, with sort and search |
| POST | `/api/tables/<table>/rows` | Add an empty row at the end |
| PATCH | `/api/tables/<table>/rows/<id>` | Change one cell |
| DELETE | `/api/tables/<table>/rows/<id>` | Delete a row |
| POST | `/api/tables/<table>/columns` | Add an empty column at the end |
| GET | `/api/tables/<table>/history` | Recent changes, newest first |
| GET | `/api/tables/<table>/download` | The CSV file itself |

## Row IDs

Each row has an `id`, a **zero-based position in the current CSV**. Search and sort do not change IDs. Deleting or externally editing the CSV can change row positions. The API therefore requires the exact `version` returned by GET /rows on **every write**, sent in the `If-Match` header. A stale/missing version is rejected instead of accidentally changing the wrong row. This prevents stale UI changes, but is **not a multi-process lock** and does not enable concurrent team use.

## GET /api/health

```json
{ "gateway": "ok", "flask": "ok" }
```

Returns 503 with `"flask": "down"` if Flask isn't reachable.

## GET /api/tables

```json
[{ "name": "sample_products.csv", "rows": 15, "columns": 6, "size_bytes": 724 }]
```

## POST /api/tables

Multipart form with a `file` field. Returns 201 with `{ "name", "rows", "columns" }`.
400 if it isn't a `.csv` or can't be parsed, 409 if a table with that name exists, 413 if over 100 MB.

```bash
curl -F "file=@my_extract.csv" http://localhost:4000/api/tables
```

## GET /api/tables/&lt;table&gt;/rows

| Query | Default | Notes |
|---|---|---|
| `page` | 1 | |
| `page_size` | 50 | 1 to 500 |
| `sort` | none | Column name. Number columns sort numerically; empty cells go last. |
| `order` | `asc` | `asc` or `desc` |
| `search` | none | Case-insensitive "contains" match |
| `search_column` | all columns | Limit the search to one column |

```json
{
  "table": "sample_products.csv",
  "columns": [{ "name": "product_id", "type": "text" }, { "name": "unit_price", "type": "number" }],
  "rows": [{ "id": 11, "cells": ["P-012", "89.00"] }],
  "total": 15,
  "page": 1,
  "page_size": 50,
  "version": "<sha256-of-file-bytes>"
}
```

`total` is the number of rows after the search filter. Cell values are always strings; an empty cell is `""`.

## Mutations and `If-Match` protection

First GET `/api/tables/<table>/rows` and copy the `version` into the `If-Match` HTTP header for PATCH, POST row, DELETE row, and POST column operations. Every successful write returns a new `version`; subsequent writes must send that new value. Missing token: HTTP **428**; stale token: HTTP **409**. Reload the table before retrying.

Example (PowerShell): `$version = (Invoke-RestMethod http://localhost:4000/api/tables/people.csv/rows).version`.

## PATCH /api/tables/&lt;table&gt;/rows/&lt;id&gt;

```json
{ "column": "stock_qty", "value": "999" }
```

Response:

```json
{ "id": 0, "column": "stock_qty", "old_value": "1309", "new_value": "999", "changed": true, "version": "<new-sha256>" }
```

400 if the column doesn't exist, or a number column gets text. 404 if the row doesn't exist. If the value is unchanged, nothing is written and `changed` is `false`.

## POST /api/tables/&lt;table&gt;/rows

No body. Returns 201 with `{ "id": 500, "total": 501, "version": "<new-sha256>" }` (`total` = rows in the table now).

## DELETE /api/tables/&lt;table&gt;/rows/&lt;id&gt;

Returns `{ "id": 3, "deleted": true, "version": "<new-sha256>" }`. After deletion, row positions are sequential again. The deleted values are kept in the history log.

## POST /api/tables/&lt;table&gt;/columns

```json
{ "name": "checked_by" }
```

Returns 201 with `{ "column": "checked_by" }`. 409 if it already exists. On success, the response also includes the new `version`.

## GET /api/tables/&lt;table&gt;/history

`?limit=50` (1 to 500). Newest first. Each entry has `ts`, `table`, `action` (`update_cell`, `add_row`, `delete_row`, `add_column`, `upload`) and the details for that action:

```json
[{ "ts": "2026-11-04T00:26:54", "table": "sample_products.csv", "action": "update_cell", "row": 0, "column": "stock_qty", "old": "1309", "new": "999" }]
```

## GET /api/tables/&lt;table&gt;/download

The CSV file as an attachment (`text/csv`).
