import { useEffect, useRef, useState } from 'react';
import { columnLetter } from './Grid';

/**
 * The bar above the grid (like Excel's formula bar): shows which cell is
 * selected and lets you edit its full value, which helps with long text.
 */
export default function CellBar({ selected, column, rowNumber, value, onCommit, onDone }) {
  const [draft, setDraft] = useState(value ?? '');

  // Show the new value whenever the selection (or the saved value) changes.
  useEffect(() => setDraft(value ?? ''), [value, selected?.r, selected?.c]);

  const ref = selected && column ? `${columnLetter(selected.c)}${rowNumber}` : '';

  const cancelled = useRef(false);

  // Saving happens on blur only, so Enter (which moves focus back to the grid)
  // saves exactly once. Escape sets a flag so that blur discards the draft.
  const commit = () => {
    if (cancelled.current) {
      cancelled.current = false;
      setDraft(value ?? '');
      return;
    }
    if (selected && draft !== (value ?? '')) onCommit(selected.r, selected.c, draft);
  };

  return (
    <div className="cell-bar">
      <div className="cell-ref" aria-label="Selected cell">
        {ref || '–'}
      </div>
      <div className="cell-col">{column ? column.name : 'Select a cell to see its value'}</div>
      <input
        className="cell-input"
        value={draft}
        disabled={!selected}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            onDone();
          } else if (e.key === 'Escape') {
            cancelled.current = true;
            onDone();
          }
        }}
        aria-label="Cell value"
        placeholder={selected ? '(empty)' : ''}
      />
    </div>
  );
}
