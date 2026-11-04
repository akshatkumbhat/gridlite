const fmt = (n) => Number(n).toLocaleString('en-US');
const PAGE_SIZES = [25, 50, 100, 200];

/** Footer under the grid. Only one page of rows is ever loaded from the server. */
export default function Pagination({ page, pageSize, total, onPage, onPageSize }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);

  return (
    <div className="pagination">
      <span className="range">
        Rows {fmt(first)}–{fmt(last)} of {fmt(total)}
      </span>
      <div className="pager">
        <button type="button" className="btn btn-quiet" onClick={() => onPage(1)} disabled={page <= 1}>
          First
        </button>
        <button type="button" className="btn btn-quiet" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Previous
        </button>
        <span className="page-of">
          Page {fmt(page)} of {fmt(pages)}
        </span>
        <button type="button" className="btn btn-quiet" onClick={() => onPage(page + 1)} disabled={page >= pages}>
          Next
        </button>
        <button type="button" className="btn btn-quiet" onClick={() => onPage(pages)} disabled={page >= pages}>
          Last
        </button>
      </div>
      <label className="page-size">
        Rows per page
        <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
          {PAGE_SIZES.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
