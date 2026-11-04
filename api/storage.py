"""Local CSV storage for GridLite.

Data integrity rules:
- Files remain CSVs (no hidden database). Values are always treated as strings.
- All writes require a version from the client's most recent read. A stale
  browser tab cannot edit a row after another process changes/reorders the CSV.
- Back up first, write a complete temporary file in the same directory,
  then replace. Failed writes invalidate the in-memory cache.
- Preserve encoding, line endings, trailing newline, completely quoted CSVs,
  and physically blank CSV lines. Mixed quoting is normalized on a write.

This module is deliberately single-user. A version token detects stale writes,
but it is not an inter-process lock and is not suitable for shared deployment.
"""

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from werkzeug.utils import secure_filename

MAX_BACKUPS_PER_TABLE = 5
# A numeric value must be acceptable to pandas.to_numeric (for sorting) and
# use ordinary decimal/scientific notation. Python float('1_000') is too lax.
_NUMBER_FORMAT = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\Z")


class StoreError(Exception):
    status = 400


class TableNotFound(StoreError):
    status = 404


class RowNotFound(StoreError):
    status = 404


class Conflict(StoreError):
    status = 409


class PreconditionRequired(StoreError):
    status = 428


class ValidationError(StoreError):
    status = 400


class SaveFailed(StoreError):
    status = 500


@dataclass
class Table:
    df: pd.DataFrame
    types: dict
    encoding: str
    line_ending: str
    version: str  # SHA-256 of the bytes currently on disk
    quote_all: bool
    blank_positions: list  # logical row index BEFORE which blank lines appeared
    leading_blanks: int
    final_newline: bool


def is_number(value: str) -> bool:
    """Use exactly the same numeric grammar as infer_type and numeric sorting."""
    if not isinstance(value, str) or not _NUMBER_FORMAT.fullmatch(value.strip()):
        return False
    try:
        result = pd.to_numeric(value.strip(), errors="coerce")
        return bool(pd.notna(result)) and math.isfinite(float(result))
    except (ValueError, TypeError, OverflowError):
        return False


def infer_type(series: pd.Series) -> str:
    values = series.astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return "text"
    # The regex also rejects 1_000, which float() accepts but pandas rejects.
    if not bool(values.str.fullmatch(_NUMBER_FORMAT).all()):
        return "text"
    parsed = pd.to_numeric(values, errors="coerce")
    # Infinity is disallowed, just as it is for edit validation.
    return "number" if bool(parsed.notna().all()) and not bool(parsed.isin([math.inf, -math.inf]).any()) else "text"


def _file_version(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def detect_line_ending(path: str) -> str:
    with open(path, "rb") as f:
        head = f.read(64 * 1024)
    first = head.find(b"\n")
    return "\r\n" if first > 0 and head[first - 1] == 13 else "\n"


def _get_csv(path: str):
    """Read logical rows, tracking empty physical records and quote-all style."""
    encoding = detect_encoding(path)
    newline = detect_line_ending(path)
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 2))
        final_newline = f.read().endswith(b"\n")

    captured = []
    headers = None
    data = []
    leading_blanks = 0
    blanks = []
    all_quoted = True
    try:
        # newline='' is required by the Python CSV module on every OS.
        with open(path, encoding=encoding, newline="") as stream:
            def lines():
                for line in stream:
                    captured.append(line)
                    yield line

            for record in csv.reader(lines(), strict=True):
                original = "".join(captured)
                captured.clear()
                if not record:  # an actual blank line, not a row of empty fields
                    if headers is None:
                        leading_blanks += 1
                    else:
                        blanks.append(len(data))
                    continue

                # A fully quoted Oracle export should stay fully quoted.
                rendered = io.StringIO(newline="")
                csv.writer(rendered, quoting=csv.QUOTE_ALL, lineterminator=newline).writerow(record)
                quoted = rendered.getvalue()
                if original not in (quoted, quoted[:-len(newline)]):
                    all_quoted = False

                if headers is None:
                    headers = record
                    repeated = [name for name, count in Counter(headers).items() if count > 1]
                    if repeated:
                        raise ValidationError(f"Repeated column names {sorted(repeated)}: rename them in the file before editing it here")
                    if not headers:
                        raise ValidationError("CSV has no columns")
                else:
                    if len(record) > len(headers):
                        raise ValidationError(f"CSV row {len(data)+2} has more values than the header")
                    data.append(record + [""] * (len(headers) - len(record)))
    except (csv.Error, UnicodeError) as exc:
        raise ValidationError(f"Could not parse CSV: {exc}") from exc

    if headers is None:
        raise ValidationError("CSV is empty or has no header row")
    frame = pd.DataFrame(data, columns=headers, dtype=object)
    return (frame, encoding, newline, all_quoted, blanks, leading_blanks, final_newline)


def read_csv(path: str):
    """Compatibility helper retained for upload validation."""
    return _get_csv(path)


class CsvStore:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        self.backup_dir = os.path.join(self.data_dir, "backups")
        self.log_path = os.path.join(self.data_dir, "changes.jsonl")
        os.makedirs(self.backup_dir, exist_ok=True)
        self._cache = {}
        self._lock = threading.RLock()

    def _path(self, name: str) -> str:
        if name != secure_filename(name) or not name.lower().endswith(".csv"):
            raise TableNotFound(f"Table '{name}' not found")
        path = os.path.join(self.data_dir, name)
        if not os.path.isfile(path) or os.path.islink(path):
            raise TableNotFound(f"Table '{name}' not found")
        return path

    def _load(self, name: str) -> Table:
        path = self._path(name)
        version = _file_version(path)
        cached = self._cache.get(name)
        if cached and cached.version == version:
            return cached
        frame, encoding, newline, quote_all, blanks, leading, final_newline = read_csv(path)
        types = {col: infer_type(frame[col]) for col in frame.columns}
        table = Table(frame, types, encoding, newline, version, quote_all, blanks, leading, final_newline)
        self._cache[name] = table
        return table

    def _editable(self, name: str, expected_version: str) -> Table:
        if not expected_version:
            raise PreconditionRequired("An edit requires the latest file version; refresh the table and retry")
        table = self._load(name)
        if table.version != expected_version:
            raise Conflict("This CSV changed since you loaded it. Refresh the table before editing; no changes were saved")
        return table

    def _save(self, name: str, table: Table):
        path = self._path(name)
        tmp_path = None
        # Checking again limits TOCTOU windows but does not replace a multi-process lock.
        if _file_version(path) != table.version:
            self._cache.pop(name, None)
            raise Conflict("The CSV was modified on disk before saving. Refresh and retry")
        try:
            # Backup errors should prevent the write, not silently disable recovery.
            self._backup(name, path)
            with tempfile.NamedTemporaryFile(mode="w", encoding=table.encoding, newline="",
                    dir=self.data_dir, prefix=f".{name}.", suffix=".tmp", delete=False) as out:
                tmp_path = out.name
                writer = csv.writer(out, quoting=csv.QUOTE_ALL if table.quote_all else csv.QUOTE_MINIMAL,
                                    lineterminator=table.line_ending)
                for _ in range(table.leading_blanks):
                    writer.writerow([])
                writer.writerow(list(table.df.columns))
                blank_counts = Counter(table.blank_positions)
                for pos in range(len(table.df) + 1):
                    for _ in range(blank_counts[pos]):
                        writer.writerow([])
                    if pos < len(table.df):
                        writer.writerow(table.df.iloc[pos].tolist())
            if not table.final_newline:
                with open(tmp_path, "rb+") as out:
                    newline_bytes = table.line_ending.encode("ascii")
                    out.seek(-len(newline_bytes), os.SEEK_END)
                    if out.read() == newline_bytes:
                        out.seek(-len(newline_bytes), os.SEEK_END)
                        out.truncate()
            os.replace(tmp_path, path)
            tmp_path = None
        except (OSError, UnicodeError, ValueError) as exc:
            self._cache.pop(name, None)
            raise SaveFailed(
                f"Could not save '{name}' ({exc}). "
                "If it is open in Excel or another program, close it and try again."
            ) from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        table.version = _file_version(path)

    def _backup(self, name: str, path: str):
        stem = name[:-4]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, os.path.join(self.backup_dir, f"{stem}.{stamp}.csv"))
        mine = sorted(f for f in os.listdir(self.backup_dir)
                      if f.endswith(".csv") and f[:-4].rpartition(".")[0] == stem)
        for old in mine[:-MAX_BACKUPS_PER_TABLE]:
            os.remove(os.path.join(self.backup_dir, old))

    def _log(self, name: str, action: str, **details):
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "table": name, "action": action, **details}
        try:
            with open(self.log_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            # The CSV was already replaced successfully. Do not falsely claim
            # that the data save failed just because the audit log is unwritable.
            return f"'{name}' was saved, but writing its change history failed: {exc}"
        return None

    def _columns(self, table):
        return [{"name": col, "type": table.types[col]} for col in table.df.columns]

    def _get_row(self, table: Table, row_id: int):
        if row_id not in table.df.index:
            raise RowNotFound(f"Row {row_id} not found")

    def list_tables(self):
        with self._lock:
            result = []
            for name in sorted(os.listdir(self.data_dir)):
                if not name.lower().endswith(".csv") or name != secure_filename(name):
                    continue
                try:
                    table = self._load(name)
                except Exception as exc:
                    result.append({"name": name, "error": str(exc)})
                    continue
                result.append({"name": name, "rows": len(table.df), "columns": len(table.df.columns),
                               "size_bytes": os.path.getsize(os.path.join(self.data_dir, name))})
            return result

    def query(self, name, page=1, page_size=50, sort=None, order="asc", search="", search_column=""):
        with self._lock:
            table = self._load(name)
            df = table.df
            if search:
                cols = [search_column] if search_column else list(df.columns)
                for col in cols:
                    if col not in df.columns:
                        raise ValidationError(f"Unknown column '{col}'")
                mask = pd.Series(False, index=df.index)
                for col in cols:
                    mask |= df[col].str.contains(search, regex=False, case=False)
                df = df[mask]
            if sort:
                if sort not in df.columns:
                    raise ValidationError(f"Unknown column '{sort}'")
                if table.types[sort] == "number":
                    key = pd.to_numeric(df[sort], errors="coerce")
                else:
                    key = df[sort].str.lower().mask(df[sort] == "")
                order_index = key.sort_values(ascending=order != "desc", na_position="last", kind="stable").index
                df = df.loc[order_index]
            total = len(df)
            chunk = df.iloc[(page - 1) * page_size:page * page_size]
            rows = [{"id": int(idx), "cells": list(values)} for idx, values in zip(chunk.index, chunk.values)]
            return {"table": name, "columns": self._columns(table), "rows": rows,
                    "total": total, "page": page, "page_size": page_size, "version": table.version}

    def history(self, name, limit=50):
        with self._lock:
            self._path(name)
            if not os.path.exists(self.log_path):
                return []
            with open(self.log_path, encoding="utf-8") as stream:
                entries = [json.loads(line) for line in stream if line.strip()]
            return list(reversed([entry for entry in entries if entry.get("table") == name][-limit:]))

    def file_path(self, name):
        return self._path(name)

    def update_cell(self, name, row_id, column, value, expected_version):
        with self._lock:
            table = self._editable(name, expected_version)
            self._get_row(table, row_id)
            if column not in table.df.columns:
                raise ValidationError(f"Unknown column '{column}'")
            value = "" if value is None else str(value)
            if table.types[column] == "number" and value.strip() and not is_number(value):
                raise ValidationError(f"Column '{column}' expects a number, got '{value}'")
            old = table.df.at[row_id, column]
            if old == value:
                return {"id": row_id, "column": column, "old_value": old, "new_value": value,
                        "changed": False, "version": table.version}
            table.df.at[row_id, column] = value
            self._save(name, table)
            table.types[column] = infer_type(table.df[column])
            warning = self._log(name, "update_cell", row=row_id, column=column, old=old, new=value)
            return {"id": row_id, "column": column, "old_value": old, "new_value": value,
                    "changed": True, "version": table.version, "warning": warning}

    def add_row(self, name, expected_version):
        with self._lock:
            table = self._editable(name, expected_version)
            new_id = len(table.df)
            table.df.loc[new_id] = [""] * len(table.df.columns)
            # Previously trailing blank lines remain trailing rather than moving above the new row.
            table.blank_positions = [pos + 1 if pos == new_id else pos for pos in table.blank_positions]
            self._save(name, table)
            warning = self._log(name, "add_row", row=new_id)
            return {"id": new_id, "total": len(table.df), "version": table.version, "warning": warning}

    def delete_row(self, name, row_id, expected_version):
        with self._lock:
            table = self._editable(name, expected_version)
            self._get_row(table, row_id)
            old = dict(table.df.loc[row_id])
            table.df = table.df.drop(index=row_id).reset_index(drop=True)
            table.blank_positions = [pos if pos <= row_id else pos - 1 for pos in table.blank_positions]
            self._save(name, table)
            warning = self._log(name, "delete_row", row=row_id, old=old)
            return {"id": row_id, "deleted": True, "version": table.version, "warning": warning}

    def add_column(self, name, column, expected_version):
        with self._lock:
            table = self._editable(name, expected_version)
            column = (column or "").strip()
            if not column:
                raise ValidationError("Column name is required")
            if len(column) > 100:
                raise ValidationError("Column name is too long (max 100 characters)")
            if column in table.df.columns:
                raise Conflict(f"Column '{column}' already exists")
            table.df[column] = ""
            table.types[column] = "text"
            self._save(name, table)
            warning = self._log(name, "add_column", column=column)
            return {"column": column, "version": table.version, "warning": warning}

    def create_from_upload(self, file_storage):
        with self._lock:
            name = secure_filename(file_storage.filename or "")
            if not name.lower().endswith(".csv"):
                raise ValidationError("Only .csv files can be uploaded")
            final_path = os.path.join(self.data_dir, name)
            if os.path.exists(final_path):
                raise Conflict(f"A table named '{name}' already exists")
            tmp_path = None
            created_final = False
            try:
                with tempfile.NamedTemporaryFile(dir=self.data_dir, prefix=f".{name}.",
                        suffix=".upload.tmp", delete=False) as stream:
                    tmp_path = stream.name
                    file_storage.save(stream)
                read_csv(tmp_path)
                # Exclusive create prevents another upload from silently replacing this file.
                with open(final_path, "xb") as out, open(tmp_path, "rb") as source:
                    created_final = True
                    shutil.copyfileobj(source, out)
            except FileExistsError as exc:
                raise Conflict(f"A table named '{name}' already exists") from exc
            except (ValidationError, OSError, UnicodeError) as exc:
                # If the exclusive create succeeded but copying failed, remove
                # this process's incomplete upload, never leave a corrupt CSV.
                if created_final and os.path.exists(final_path):
                    try:
                        os.remove(final_path)
                    except OSError:
                        pass
                if isinstance(exc, StoreError):
                    raise
                raise ValidationError(f"Could not read or upload '{name}' as CSV: {exc}") from exc
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            warning = self._log(name, "upload")
            table = self._load(name)
            result = {"name": name, "rows": len(table.df), "columns": len(table.df.columns)}
            if warning:
                result["warning"] = warning
            return result
