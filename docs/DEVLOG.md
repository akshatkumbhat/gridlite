# Development log

What was built, in order, why each choice was made, and how it was checked. Built with AI assistance (Claude); every step below was run and verified, not only written.

## Goal

A simple web tool to open a data file (for example a CSV extracted from Oracle), view it like a spreadsheet, edit it, and save the changes back into the same file. Stack: React, Node.js and Flask, running locally.

## Step 1: Flask data service (`api/`)

**Built:** `storage.py` (all file reading and writing) and `app.py` (the HTTP routes).

**Decisions:**

| Decision | Why |
|---|---|
| The CSV file itself is the storage, no database | Matches the goal: edit the data file and save back into it. Nothing extra to install. |
| Read every value as text (`dtype=str`, `keep_default_na=False`) | pandas normally turns `007` into `7`, and whole-number columns with blanks into `1990.0`. Reading as text keeps the file exactly as it was. |
| Guess each column's type (number or text) only to sort and validate | Numbers sort as numbers, and text in a number column is refused, without changing how values are stored. |
| Cache each table in memory, reload when the file's modified time changes | A 14 MB file takes about 1.6 s to read; after that, pages load in about 0.1 s. Edits made to the file outside the app are still picked up. |
| Backup, then write a temp file and rename it over the original | `os.replace` is atomic, so a crash mid-save can't leave a half-written CSV. The last 5 backups per table are kept. |
| Log every change to `data/changes.jsonl` | Traceability: what changed, old and new value, when. Also makes undo possible later. |
| Row IDs = position in the file when loaded | Edits target the right row even when the view is sorted or searched. |
| One lock around every read and write | Simple protection against two requests changing the same table at the same time. |
| Table names checked with `secure_filename` and must be an existing `.csv` in `data/` | Blocks paths like `../secret.csv`. |

**Checked:**
- 13 pytest tests (`api/tests/test_api.py`): listing, paging, numeric and text sorting, search, editing (formatting kept), rejecting text in a number column, add and delete rows, add column, history, upload and download, unsafe names.
- The same tests pass on pandas 3.0.5 / Flask 3.1.3 and on pandas 2.2.3 / Flask 3.0.3, in case another machine has older versions.
- Edited one cell in the 50,411 × 79 OWID file, then diffed it with the original: only that one cell differed.

## Step 2: Node gateway (`gateway/`)

**Built:** `server.js` with Express.

**Decisions:**

| Decision | Why |
|---|---|
| The browser talks only to the gateway | Flask stays private. Login or caching can be added here later without touching data code. |
| `http-proxy-middleware` v3, not v4 | v4 requires Node 22.15+; v3 runs on Node 18+, which is safer for an unknown laptop. |
| No body parser before the proxy | Uploads and downloads are streamed straight through. |
| `/api/health` answered by Node itself | Shows whether Flask is up even when it's down. |
| Flask address is `127.0.0.1`, not `localhost` | Node 17+ may resolve `localhost` to IPv6 (`::1`), while Flask listens on IPv4. |
| Serves `web/dist` if it exists | One-port demo mode: `npm run build`, then `npm start`. |

**Checked:** every route through the gateway with curl (list, rows with sort, valid and invalid edit, upload, download headers, history, 404). With Flask stopped: health returns 503 and other calls return 502 with a readable message.

## Step 3: React UI (`web/`)

**Built:** Vite + React 19. `App.jsx` holds the state. `api.js` holds every HTTP call. Components: `Sidebar`, `Toolbar`, `CellBar`, `Grid`, `Pagination`, `HistoryPanel`.

**Decisions:**

| Decision | Why |
|---|---|
| A plain HTML table with server-side paging, no grid library | Easy to read and explain. Only one page (up to 200 rows) is in the browser at once. |
| Optimistic edits | The new value shows immediately; if the server refuses it, the old value comes back and the error is shown. |
| Spreadsheet keyboard behaviour | Familiar to Excel users: type to edit, Enter or Tab to save and move, Esc to cancel. |
| Cell bar above the grid | Shows the cell reference (for example `F4`) and allows editing long values. |
| Vite 6 | Supports Node 18, 20 and 22. |
| Font (IBM Plex Sans) installed from npm, not loaded from Google | Works offline and on locked-down work networks. |

**Checked** in Chrome with Playwright, through the full stack (browser → Vite → gateway → Flask → file):
- Edit a cell with the keyboard: saved, selection moves down.
- Type `lots` into a number column: error shown, old value restored, file unchanged.
- Sort a number column descending; search one column; edit through the cell bar.
- History lists the changes; add column; add row (selected on the last page); delete row.
- 390 px wide screen: no sideways page scroll.
- 50,411-row file: opens, searches, sorts and saves.

**Bug found and fixed:** after searching, "Add row" jumped to the wrong page, because the page was worked out from the filtered row count. Flask now returns the table's real row count after adding, and the UI uses that.

**Visual fixes after screenshots:** column headers were squeezed to the minimum width (the table shrank to fit the screen instead of scrolling), fixed with `width: max-content`. The Download link was link-blue; now matches the other buttons.

## Step 4: One-command run and fresh-clone test

**Built:** root `package.json` with `npm run dev` (starts all three with `concurrently`), `npm start`, `npm test`, `npm run sample-data`. `.gitignore` keeps everything in `data/` out of git except the two samples.

**Checked:** committed the project to a throwaway git repo, cloned it into an empty folder, followed the README setup exactly, ran `npm test` (13 passed), `npm run dev` (browser test passed again), and the one-port mode (`npm run build` + `npm start`: UI and API both on :4000).

## Step 5: Docs

README (setup, run, how saving works, measured speed, limits), `docs/API.md`, this log.

## Publishing to GitHub

```bash
git init
git add .
git commit -m "GridLite v1: React + Node gateway + Flask CSV editor"
git branch -M main
git remote add origin https://github.com/<your-username>/gridlite.git
git push -u origin main
```

Create the empty `gridlite` repository on GitHub first.
