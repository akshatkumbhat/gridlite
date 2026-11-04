import { useEffect, useState } from 'react';
import { api } from '../api';

const show = (v) => (v === '' || v == null ? '(empty)' : `“${v}”`);

function describe(e) {
  switch (e.action) {
    case 'update_cell':
      return { title: `Edited ${e.column}, row position ${e.row}`, detail: `${show(e.old)} → ${show(e.new)}` };
    case 'add_row':
      return { title: `Added row at position ${e.row}` };
    case 'delete_row':
      return { title: `Deleted row at position ${e.row}` };
    case 'add_column':
      return { title: `Added column ${e.column}` };
    case 'upload':
      return { title: 'Uploaded file' };
    default:
      return { title: e.action };
  }
}

/** Right panel listing the most recent changes to the open table (from changes.jsonl). */
export default function HistoryPanel({ tableName, refreshKey, onClose }) {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let current = true;
    api
      .history(tableName)
      .then((data) => current && (setEntries(data), setError('')))
      .catch((err) => current && setError(err.message));
    return () => {
      current = false;
    };
  }, [tableName, refreshKey]);

  return (
    <aside className="history" aria-label="Change history">
      <div className="history-head">
        <h2>Change history</h2>
        <button type="button" className="btn btn-quiet" onClick={onClose}>
          Close
        </button>
      </div>
      {error && <p className="history-empty">{error}</p>}
      {entries && entries.length === 0 && <p className="history-empty">No changes yet. Edits to this table will appear here.</p>}
      <ol className="history-list">
        {entries?.map((e, i) => {
          const { title, detail } = describe(e);
          return (
            <li key={`${e.ts}-${i}`}>
              <div className="history-title">{title}</div>
              {detail && <div className="history-detail">{detail}</div>}
              <time dateTime={e.ts}>{new Date(e.ts).toLocaleString()}</time>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
