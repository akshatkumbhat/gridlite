import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import CellBar from './components/CellBar';
import Grid from './components/Grid';
import Pagination from './components/Pagination';
import HistoryPanel from './components/HistoryPanel';

const DEFAULT_QUERY = { page: 1, pageSize: 50, sort: null, order: 'asc', search: '', searchColumn: '' };

const STATUS_TEXT = {
  idle: 'No unsaved changes',
  saving: 'Saving…',
  saved: 'All changes saved',
  error: 'Last change not saved',
};

export default function App() {
  const [tables, setTables] = useState([]);
  const [tablesLoaded, setTablesLoaded] = useState(false);
  const [active, setActive] = useState(null); // file name of the open table
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [data, setData] = useState(null); // { columns, rows, total } for the current page
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [selected, setSelected] = useState(null); // { r, c } = index into data.rows / data.columns
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const gridRef = useRef(null);
  const selectRowId = useRef(null); // after adding a row, select it once it loads
  const versionRef = useRef(null); // latest disk version for optimistic concurrency
  const savingRef = useRef(false); // prevent overlapping edits

  // ---------- loading ----------

  const loadTables = useCallback(async () => {
    try {
      const list = await api.listTables();
      setTables(list);
      setTablesLoaded(true);
      return list;
    } catch (err) {
      setError(err.message);
      return [];
    }
  }, []);

  useEffect(() => {
    loadTables().then((list) => {
      if (list.length) setActive((current) => current || list[0].name);
    });
    // Tell the user straight away if Flask isn't running behind the gateway.
    api.health().catch(() => setError('The data service (Flask) is not running. Start it with: npm run dev:api'));
  }, [loadTables]);

  useEffect(() => {
    if (!active) return undefined;
    let current = true; // ignore responses that arrive after a newer request
    setLoading(true);
    api
      .getRows(active, query)
      .then((res) => {
        if (!current) return;
        // e.g. after deleting the only row on the last page: step back to a page that exists
        if (res.rows.length === 0 && res.total > 0 && query.page > 1) {
          setQuery((q) => ({ ...q, page: Math.ceil(res.total / q.pageSize) }));
          return;
        }
        // Row IDs are positions, so never edit with an older file version.
        versionRef.current = res.version;
        setData(res);
        if (selectRowId.current !== null) {
          const r = res.rows.findIndex((row) => row.id === selectRowId.current);
          setSelected(r >= 0 ? { r, c: 0 } : null);
          selectRowId.current = null;
        }
      })
      .catch((err) => current && setError(err.message))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [active, query, reloadKey]);

  const reload = () => setReloadKey((k) => k + 1);

  // ---------- changes (every change is saved to the CSV file right away) ----------

  const runChange = async (fn) => {
    if (savingRef.current) {
      const message = 'Another edit is still saving; please retry.';
      setStatus('error');
      setError(message);
      throw new Error(message);
    }
    savingRef.current = true;
    setStatus('saving');
    setError('');
    try {
      const result = await fn(versionRef.current);
      if (result.version) {
        versionRef.current = result.version;
        setData((current) => current ? { ...current, version: result.version } : current);
      }
      setStatus('saved');
      if (result.warning) setError(result.warning);
      setHistoryKey((k) => k + 1);
      return result;
    } catch (err) {
      setStatus('error');
      setError(err.message);
      reload(); // re-read disk, especially after a 409 version conflict or 500 error
      throw err;
    } finally {
      savingRef.current = false;
    }
  };

  const saveCell = async (r, c, value) => {
    const row = data?.rows[r];
    const column = data?.columns[c];
    if (!row || !column) return;
    const old = row.cells[c];
    if (old === value) return;

    // Show the new value immediately; put the old one back if saving fails.
    const setCell = (v) =>
      setData((d) => d ? ({
        ...d,
        rows: d.rows.map((x) => (x.id === row.id ? { ...x, cells: x.cells.map((cv, i) => (i === c ? v : cv)) } : x)),
      }) : d);
    setCell(value);
    try {
      await runChange((version) => api.updateCell(active, row.id, column.name, value, version));
    } catch {
      setCell(old);
    }
  };

  const addRow = async () => {
    try {
      const { id, total } = await runChange((version) => api.addRow(active, version));
      selectRowId.current = id;
      // New rows go at the end of the file: clear the search and jump to the last page.
      setQuery((q) => ({ ...q, search: '', page: Math.max(1, Math.ceil(total / q.pageSize)) }));
      reload();
      loadTables();
    } catch {
      /* error already shown */
    }
  };

  const deleteRow = async () => {
    if (!selected || !data?.rows[selected.r]) return;
    const row = data.rows[selected.r];
    const number = (query.page - 1) * query.pageSize + selected.r + 1;
    if (!window.confirm(`Delete row ${number}? It will be removed from ${active}.`)) return;
    try {
      await runChange((version) => api.deleteRow(active, row.id, version));
      setSelected(null);
      reload();
      loadTables();
    } catch {
      /* error already shown */
    }
  };

  const addColumn = async (name) => {
    try {
      await runChange((version) => api.addColumn(active, name, version));
      reload();
      loadTables();
    } catch {
      /* error already shown */
    }
  };

  const upload = async (file) => {
    setUploading(true);
    setError('');
    try {
      const res = await api.uploadTable(file);
      await loadTables();
      openTable(res.name);
      if (res.warning) setError(res.warning);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  // ---------- navigation ----------

  const openTable = (name) => {
    if (savingRef.current) return;
    versionRef.current = null;
    setData(null);
    setActive(name);
    setQuery(DEFAULT_QUERY);
    setSelected(null);
    setStatus('idle');
    setError('');
  };

  const changeQuery = (changes) => {
    setSelected(null);
    setQuery((q) => ({ ...q, ...changes }));
  };

  const sortBy = (column) => {
    // Click once: A→Z, twice: Z→A, three times: original file order.
    if (query.sort !== column) changeQuery({ sort: column, order: 'asc', page: 1 });
    else if (query.order === 'asc') changeQuery({ order: 'desc', page: 1 });
    else changeQuery({ sort: null, order: 'asc', page: 1 });
  };

  const onSearch = useCallback((search, searchColumn) => {
    setSelected(null);
    setQuery((q) => ({ ...q, search, searchColumn, page: 1 }));
  }, []);

  // ---------- render ----------

  const columns = data?.columns ?? [];
  const rows = data?.rows ?? [];
  const startIndex = (query.page - 1) * query.pageSize;
  const selectedColumn = selected ? columns[selected.c] : null;
  const selectedValue = selected ? rows[selected.r]?.cells[selected.c] : '';

  return (
    <div className={showHistory && active ? 'app with-history' : 'app'}>
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true" />
          <span className="wordmark">GridLite</span>
          {active && <span className="file-name">{active}</span>}
        </div>
        <div className={`status status-${status}`} role="status">
          <span className="dot" aria-hidden="true" />
          {STATUS_TEXT[status]}
        </div>
      </header>

      <Sidebar tables={tables} loaded={tablesLoaded} active={active} onSelect={openTable} onUpload={upload} uploading={uploading} />

      <main className="workspace">
        {error && (
          <div className="alert" role="alert">
            <span>{error}</span>
            <button type="button" className="btn btn-quiet" onClick={() => setError('')}>
              Dismiss
            </button>
          </div>
        )}

        {!active ? (
          <div className="placeholder">
            {tablesLoaded ? 'Upload a CSV file, or add one to the data folder, to start editing.' : 'Loading tables…'}
          </div>
        ) : (
          <>
            <Toolbar
              columns={columns}
              search={query.search}
              searchColumn={query.searchColumn}
              onSearch={onSearch}
              onAddRow={addRow}
              onAddColumn={addColumn}
              onDeleteRow={deleteRow}
              canDeleteRow={!!selected}
              downloadUrl={api.downloadUrl(active)}
              tableName={active}
              showHistory={showHistory}
              onToggleHistory={() => setShowHistory((s) => !s)}
            />
            <CellBar
              selected={selected}
              column={selectedColumn}
              rowNumber={selected ? startIndex + selected.r + 1 : null}
              value={selectedValue}
              onCommit={saveCell}
              onDone={() => gridRef.current?.focus({ preventScroll: true })}
            />
            <div className={loading ? 'grid-area loading' : 'grid-area'}>
              {data && (
                <Grid
                  columns={columns}
                  rows={rows}
                  startIndex={startIndex}
                  selected={selected}
                  onSelect={setSelected}
                  onCommit={saveCell}
                  sort={query.sort}
                  order={query.order}
                  onSort={sortBy}
                  gridRef={gridRef}
                  emptyMessage={query.search ? `No rows match “${query.search}”.` : 'This table has no rows. Use Add row to create one.'}
                />
              )}
            </div>
            {data && (
              <Pagination
                page={query.page}
                pageSize={query.pageSize}
                total={data.total}
                onPage={(page) => changeQuery({ page })}
                onPageSize={(pageSize) => changeQuery({ pageSize, page: 1 })}
              />
            )}
          </>
        )}
      </main>

      {showHistory && active && <HistoryPanel tableName={active} refreshKey={historyKey} onClose={() => setShowHistory(false)} />}
    </div>
  );
}
