import { useEffect, useRef, useState } from 'react';

// 0 -> A, 25 -> Z, 26 -> AA (spreadsheet-style column letters)
export function columnLetter(index) {
  let s = '';
  let n = index + 1;
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

/**
 * The spreadsheet grid for one page of rows.
 * - Click selects a cell; arrow keys / Tab move the selection.
 * - Double-click, Enter, F2 or just typing starts editing.
 * - Enter or Tab saves, Escape cancels, Delete clears the cell.
 * Saving is done by the parent through onCommit(rowIndex, colIndex, value).
 */
export default function Grid({ columns, rows, startIndex, selected, onSelect, onCommit, sort, order, onSort, gridRef, emptyMessage }) {
  const [editing, setEditing] = useState(null); // { r, c, draft }
  const editingRef = useRef(null); // same as `editing`, readable synchronously

  // Keep the selected cell visible when moving with the keyboard.
  useEffect(() => {
    if (!selected || !gridRef.current) return;
    const el = gridRef.current.querySelector(`[data-cell="${selected.r}-${selected.c}"]`);
    if (el) el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [selected, gridRef]);

  const moveTo = (r, c) => {
    if (rows.length === 0) return;
    onSelect({
      r: Math.max(0, Math.min(rows.length - 1, r)),
      c: Math.max(0, Math.min(columns.length - 1, c)),
    });
  };

  const startEdit = (r, c, draft) => {
    editingRef.current = { r, c, draft };
    setEditing(editingRef.current);
  };

  const updateDraft = (draft) => {
    editingRef.current = { ...editingRef.current, draft };
    setEditing(editingRef.current);
  };

  const finishEdit = (save, dr = 0, dc = 0) => {
    const e = editingRef.current;
    if (!e) return; // already finished (e.g. Enter followed by blur)
    editingRef.current = null;
    setEditing(null);
    if (save) onCommit(e.r, e.c, e.draft);
    gridRef.current?.focus({ preventScroll: true });
    if (dr || dc) moveTo(e.r + dr, e.c + dc);
  };

  const onGridKeyDown = (e) => {
    if (editingRef.current || !selected) return;
    const { r, c } = selected;
    const keys = {
      ArrowUp: [-1, 0],
      ArrowDown: [1, 0],
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
      Tab: [0, e.shiftKey ? -1 : 1],
    };
    if (keys[e.key]) {
      e.preventDefault();
      moveTo(r + keys[e.key][0], c + keys[e.key][1]);
    } else if (e.key === 'Enter' || e.key === 'F2') {
      e.preventDefault();
      startEdit(r, c, rows[r].cells[c]);
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      onCommit(r, c, '');
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      startEdit(r, c, e.key); // typing replaces the value, like Excel
    }
  };

  const onEditorKeyDown = (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') {
      e.preventDefault();
      finishEdit(true, 1, 0);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      finishEdit(true, 0, e.shiftKey ? -1 : 1);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      finishEdit(false);
    }
  };

  return (
    <div className="grid-scroll" ref={gridRef} tabIndex={0} onKeyDown={onGridKeyDown} aria-label="Data grid">
      <table className="grid">
        <thead>
          <tr>
            <th className="corner" scope="col" />
            {columns.map((col, c) => {
              const sorted = sort === col.name;
              return (
                <th
                  key={col.name}
                  scope="col"
                  className={selected?.c === c ? 'col-active' : undefined}
                  aria-sort={sorted ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  <button type="button" className="col-head" onClick={() => onSort(col.name)} title={`Sort by ${col.name}`}>
                    <span className="col-letter">{columnLetter(c)}</span>
                    <span className="col-name">{col.name}</span>
                    <span className="col-type" title={col.type === 'number' ? 'Number column' : 'Text column'}>
                      {col.type === 'number' ? '123' : 'Aa'}
                    </span>
                    <span className="sort-mark" aria-hidden="true">
                      {sorted ? (order === 'asc' ? '▲' : '▼') : ''}
                    </span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td className="empty" colSpan={columns.length + 1}>
                {emptyMessage}
              </td>
            </tr>
          )}
          {rows.map((row, r) => (
            <tr key={row.id}>
              <th scope="row" className={selected?.r === r ? 'row-head row-active' : 'row-head'}>
                {startIndex + r + 1}
              </th>
              {row.cells.map((value, c) => {
                const isSelected = selected?.r === r && selected?.c === c;
                const isEditing = editing?.r === r && editing?.c === c;
                const classes = [columns[c]?.type === 'number' ? 'num' : '', isSelected ? 'selected' : ''].join(' ').trim();
                return (
                  <td
                    key={c}
                    data-cell={`${r}-${c}`}
                    className={classes || undefined}
                    onMouseDown={() => onSelect({ r, c })}
                    onDoubleClick={() => startEdit(r, c, value)}
                  >
                    <div className="cell-text" style={isEditing ? { visibility: 'hidden' } : undefined}>
                      {value}
                    </div>
                    {isEditing && (
                      <input
                        className="cell-editor"
                        autoFocus
                        value={editing.draft}
                        onChange={(e) => updateDraft(e.target.value)}
                        onKeyDown={onEditorKeyDown}
                        onBlur={() => finishEdit(true)}
                        onFocus={(e) => e.target.setSelectionRange(e.target.value.length, e.target.value.length)}
                        aria-label={`Edit ${columns[c].name}, row ${startIndex + r + 1}`}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
