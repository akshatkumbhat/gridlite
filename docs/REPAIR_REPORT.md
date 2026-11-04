# GridLite repair report — 4 November 2026

## Source

Input was `gridlite-reviewed.zip`, the reviewed React/Express/Flask application.
The reported macOS review had 17 passing Python tests and 5 fixes. This is a
new edition prepared for migration to Windows and subsequent testing on macOS.
The original source archive has not been modified.

## Changes made in this repair edition

| Area | Repair |
| --- | --- |
| Windows/macOS launch | Improved `scripts/py.js` to choose the local OS interpreter, handle spawn errors/signals, and never use global Python. Added Windows PowerShell check and double-click launcher. |
| Runtime parity | `.nvmrc` and Node engine major 24; pinned reported reviewed Mac versions of Flask/pandas/pytest; `npm ci` uses the provided Node lockfiles. |
| Network exposure | Restricted Express gateway and Vite dev server to `127.0.0.1`; the previous gateway did not specify an interface. |
| Stale row edits | `GET /rows` returns SHA-256 `version`; every modifying request requires `If-Match`; stale version => 409, absent => 428. This prevents stale browser writes from silently editing a row after an external CSV change. |
| Row identifiers | Deletions reset in-memory row positions immediately, consistent with positions after a restart. |
| Numeric input | A single numeric grammar is used for column inference and edit validation; bad forms such as `1_000`, infinity and NaN are refused. |
| CSV formatting | Preserve fully quoted CSV style, blank physical lines, final-line newline absence/presence, UTF-8 BOM, Latin-1, and CRLF/LF. Embedded commas and quoted multiline cells are handled via Python `csv`. |
| Safer saving | Temporary file generated in the same directory, always cleaned up on failure; errors (including Unicode encoding failures) drop stale cache. |
| Failed audit append | If the file saves but history cannot be appended, report a **warning** rather than falsely calling the save a failure. |
| Uploads | Validate CSV prior to publication, create new file exclusively, clean temporary and partially copied files. |
| Symlinks | Reject symlink CSVs, preventing access to arbitrary files through a link in `data/`. |
| Testing/CI | Added API regression tests, independent storage tests, JavaScript client tests, and a GitHub Actions Windows/macOS/Linux matrix. |
| Documentation | Rewrote README and API docs, added Windows tutorial and this report. |

## API breaking change

Older external API callers that do not send `If-Match` will receive HTTP 428.
On a successful `GET /api/tables/name.csv/rows`, read the `version` string and
send it as the `If-Match` header on any PATCH/POST/DELETE mutation. Mutations
return an updated version. The bundled React client has been updated.

## Tests actually performed in this environment

- **12/12 standalone storage tests passed** with Python 3.13.5 and pandas 2.2.3.
  Because Flask/Werkzeug were not available and the runtime cannot access PyPI,
  a *testing-only in-memory stub* was used for `werkzeug.utils.secure_filename`.
  This does not constitute real Flask or Windows verification.
- **4/4 JavaScript tests passed** under Node 22.16.0 (API requests/version headers
  and a source-level loopback-bind assertion).
- Python files: `compileall` passed; gateway, Vite config and launcher:
  `node --check` passed; React/JSX source parsed by locally available TypeScript
  parser without syntax errors. These checks do not replace a Vite build.
- Standalone CSV stress smoke: generated a 50,000-row, 16-column (~4.8 MB)
  synthetic CSV and confirmed load/edit and version update. Approximate times
  in this Linux container: first load ~1.22 s, edit/rewrite ~0.73 s. These are
  **not** Windows or 14 MB benchmark numbers.
- **The full Flask API suite (27 cases) was not run here**, because the required
  Flask/Werkzeug versions cannot be installed without package-network access.
  It must pass on the Windows laptop; it is set up in `npm run test:all` and CI.
- A production frontend build, real browser interaction, and real Windows
  file-lock tests were **not** performed in this environment. Do not treat them
  as verified.

There are currently **39 Python test functions** (27 API + 12 storage) and
**4 JavaScript test functions** in the package. Full cross-platform results
remain pending.

## Required acceptance on your Windows computer

1. Install Node **24** and Python **3.12**; use `docs/WINDOWS.md` or run:
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\GridLite_Windows_Check.ps1 -Setup`.
2. Ensure `npm run test:all` passes. If not, save the exact terminal error.
3. Run `npm run dev` and verify the real browser keyboard/editing workflow.
4. Reproduce Windows Excel file-lock failure using a **disposable** CSV.
5. Verify CRLF, Latin-1 and quoted Oracle files from sample files.
6. For a repository, push code and confirm the GitHub Actions three-OS CI matrix
   passes on its hosted runners; workflow has been authored but not executed.

## Remaining limitations (not falsely claimed fixed)

- GridLite is still a **local, single-user** app without login, undo or database
  transactions. Hash-based `If-Match` protection is not an inter-process lock;
  two truly simultaneous independent writers remain unsafe.
- Mixed cell-by-cell CSV quoting and unusual CSV dialect formatting are still
  normalized on rewrite; only fully quoted files are preserved as quote-all.
- A full Python dependency lock with all **transitive** package versions is not
  included; direct dependencies are pinned and Node lockfiles are supplied.
  Resolve and commit a cross-platform Python lock when online. Test on both OSes.
- The UI is covered by JavaScript API-client tests and syntax checks, **not**
  automated click/keyboard browser tests. Add Playwright once dependencies and
  browsers are available; do not claim UI tests have passed.
- Whole-file rewrite and SHA-256 hashing are potentially expensive on very
  large datasets; benchmark with actual target CSV sizes before deployment.
- Test on copies of your data first.
