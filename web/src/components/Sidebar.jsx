import { useRef } from 'react';

const fmt = (n) => Number(n).toLocaleString('en-US');

/** Left panel: the list of tables (CSV files in the data folder) and the upload button. */
export default function Sidebar({ tables, loaded, active, onSelect, onUpload, uploading }) {
  const fileInput = useRef(null);

  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">Tables</h2>
      {loaded && tables.length === 0 && <p className="sidebar-empty">No tables yet. Upload a CSV file to start.</p>}
      <ul className="table-list">
        {tables.map((t) => (
          <li key={t.name}>
            <button
              type="button"
              className={t.name === active ? 'table-item active' : 'table-item'}
              onClick={() => onSelect(t.name)}
              aria-current={t.name === active ? 'true' : undefined}
              title={t.name}
            >
              <span className="table-name">{t.name.replace(/\.csv$/i, '')}</span>
              <span className="table-meta">
                {t.error ? 'Could not read file' : `${fmt(t.rows)} rows, ${fmt(t.columns)} cols`}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <input
        ref={fileInput}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ''; // allow picking the same file again
          if (file) onUpload(file);
        }}
      />
      <button type="button" className="btn btn-primary upload" onClick={() => fileInput.current.click()} disabled={uploading}>
        {uploading ? 'Uploading…' : 'Upload CSV'}
      </button>
    </aside>
  );
}
