import { useEffect, useState } from 'react';

/** Search, row/column actions, download and history toggle for the open table. */
export default function Toolbar({
  columns,
  search,
  searchColumn,
  onSearch,
  onAddRow,
  onAddColumn,
  onDeleteRow,
  canDeleteRow,
  downloadUrl,
  tableName,
  showHistory,
  onToggleHistory,
}) {
  const [text, setText] = useState(search);
  const [newColumn, setNewColumn] = useState(null); // null = form closed

  useEffect(() => setText(search), [search]);

  // Wait until the user stops typing for 300 ms before searching.
  useEffect(() => {
    if (text === search) return undefined;
    const timer = setTimeout(() => onSearch(text, searchColumn), 300);
    return () => clearTimeout(timer);
  }, [text, search, searchColumn, onSearch]);

  const submitColumn = (e) => {
    e.preventDefault();
    if (!newColumn.trim()) return;
    onAddColumn(newColumn.trim());
    setNewColumn(null);
  };

  return (
    <div className="toolbar">
      <div className="search">
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search rows"
          aria-label="Search rows"
        />
        <select value={searchColumn} onChange={(e) => onSearch(text, e.target.value)} aria-label="Column to search">
          <option value="">in all columns</option>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              in {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="actions">
        <button type="button" className="btn" onClick={onAddRow}>
          Add row
        </button>
        {newColumn === null ? (
          <button type="button" className="btn" onClick={() => setNewColumn('')}>
            Add column
          </button>
        ) : (
          <form className="inline-form" onSubmit={submitColumn}>
            <input
              autoFocus
              value={newColumn}
              onChange={(e) => setNewColumn(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setNewColumn(null)}
              placeholder="Column name"
              aria-label="New column name"
              maxLength={100}
            />
            <button type="submit" className="btn btn-primary">
              Add
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => setNewColumn(null)}>
              Cancel
            </button>
          </form>
        )}
        <button type="button" className="btn btn-danger" onClick={onDeleteRow} disabled={!canDeleteRow}>
          Delete row
        </button>
        <span className="divider" aria-hidden="true" />
        <button type="button" className={showHistory ? 'btn pressed' : 'btn'} onClick={onToggleHistory} aria-pressed={showHistory}>
          History
        </button>
        <a className="btn" href={downloadUrl} download={tableName}>
          Download CSV
        </a>
      </div>
    </div>
  );
}
