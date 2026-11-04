"""API tests. Each test gets its own temporary data folder.

Run from the api/ folder:  python -m pytest -q
"""

import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app  # noqa: E402

CSV = "id,name,score,code\n1,Alice,90,007\n2,bob,75,010\n3,Carol,,002\n4,dave,100,001\n"


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "people.csv").write_text(CSV, encoding="utf-8")
    app = create_app(str(tmp_path))
    return app.test_client(), tmp_path


def rows(client, **params):
    res = client.get("/api/tables/people.csv/rows", query_string=params)
    assert res.status_code == 200, res.get_json()
    return res.get_json()




def versioned(client, method, url, **kwargs):
    """Every write carries the version returned by the latest GET /rows."""
    table = url.split("/tables/", 1)[1].split("/", 1)[0]
    current = client.get(f"/api/tables/{table}/rows").get_json()
    headers = {**kwargs.pop("headers", {}), "If-Match": current["version"]}
    return getattr(client, method)(url, headers=headers, **kwargs)


def test_list_tables(ctx):
    client, _ = ctx
    data = client.get("/api/tables").get_json()
    assert data == [{"name": "people.csv", "rows": 4, "columns": 4, "size_bytes": len(CSV)}]


def test_rows_and_types(ctx):
    client, _ = ctx
    data = rows(client)
    assert data["total"] == 4
    assert [c["type"] for c in data["columns"]] == ["number", "text", "number", "number"]
    assert data["rows"][0] == {"id": 0, "cells": ["1", "Alice", "90", "007"]}


def test_paging(ctx):
    client, _ = ctx
    data = rows(client, page=2, page_size=3)
    assert [r["id"] for r in data["rows"]] == [3]


def test_sort_number_desc_puts_empty_last(ctx):
    client, _ = ctx
    data = rows(client, sort="score", order="desc")
    assert [r["cells"][2] for r in data["rows"]] == ["100", "90", "75", ""]


def test_sort_text_ignores_case(ctx):
    client, _ = ctx
    data = rows(client, sort="name")
    assert [r["cells"][1] for r in data["rows"]] == ["Alice", "bob", "Carol", "dave"]


def test_search_all_columns_and_one_column(ctx):
    client, _ = ctx
    assert rows(client, search="CAROL")["total"] == 1
    assert rows(client, search="00", search_column="code")["total"] == 3  # 007, 002, 001
    assert rows(client, search="00", search_column="name")["total"] == 0


def test_update_cell_saves_file_and_keeps_formatting(ctx):
    client, tmp = ctx
    res = versioned(client, "patch", "/api/tables/people.csv/rows/1", json={"column": "name", "value": "Bob"})
    assert res.status_code == 200
    assert res.get_json()["old_value"] == "bob"
    text = (tmp / "people.csv").read_text(encoding="utf-8")
    assert "2,Bob,75,010" in text  # leading zeros kept
    assert "3,Carol,,002" in text  # empty cell kept empty
    assert len(os.listdir(tmp / "backups")) == 1


def test_update_cell_keeps_windows_line_endings(tmp_path):
    crlf = CSV.replace("\n", "\r\n")
    (tmp_path / "people.csv").write_bytes(crlf.encode("utf-8"))
    client = create_app(str(tmp_path)).test_client()
    res = versioned(client, "patch", "/api/tables/people.csv/rows/1", json={"column": "name", "value": "Bob"})
    assert res.status_code == 200
    # only the edited cell differs; every line still ends with CRLF
    assert (tmp_path / "people.csv").read_bytes() == crlf.replace("bob", "Bob").encode("utf-8")


def test_failed_save_reports_error_and_keeps_disk_value(ctx, monkeypatch):
    client, tmp = ctx

    def locked(*_args):  # what Windows does when Excel has the file open
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("storage.os.replace", locked)
    res = versioned(client, "patch", "/api/tables/people.csv/rows/1", json={"column": "name", "value": "Bob"})
    assert res.status_code == 500
    assert "close it and try again" in res.get_json()["error"]
    monkeypatch.undo()
    assert (tmp / "people.csv").read_text(encoding="utf-8") == CSV
    assert rows(client)["rows"][1]["cells"][1] == "bob"  # app shows the value on disk
    assert not [f for f in os.listdir(tmp) if f.endswith(".tmp")]


def test_backups_are_kept_per_table(ctx):
    client, tmp = ctx
    (tmp / "people.old.csv").write_text(CSV, encoding="utf-8")
    for v in ["80", "81", "82"]:
        versioned(client, "patch", "/api/tables/people.old.csv/rows/0", json={"column": "score", "value": v})
    for v in ["91", "92", "93", "94", "95", "96"]:
        versioned(client, "patch", "/api/tables/people.csv/rows/0", json={"column": "score", "value": v})
    backups = os.listdir(tmp / "backups")
    assert len([f for f in backups if f.startswith("people.old.")]) == 3
    assert len([f for f in backups if not f.startswith("people.old.")]) == 5


def test_repeated_column_names_are_refused(ctx):
    client, tmp = ctx
    (tmp / "dup.csv").write_text("x,x\n1,2\n", encoding="utf-8")
    res = client.get("/api/tables/dup.csv/rows")
    assert res.status_code == 400
    assert "Repeated column names" in res.get_json()["error"]
    assert "error" in [t for t in client.get("/api/tables").get_json() if t["name"] == "dup.csv"][0]


def test_update_number_column_rejects_text(ctx):
    client, tmp = ctx
    res = versioned(client, "patch", "/api/tables/people.csv/rows/0", json={"column": "score", "value": "abc"})
    assert res.status_code == 400
    assert "expects a number" in res.get_json()["error"]
    assert (tmp / "people.csv").read_text(encoding="utf-8") == CSV  # nothing written


def test_add_and_delete_row(ctx):
    client, tmp = ctx
    created = versioned(client, "post", "/api/tables/people.csv/rows").get_json()
    assert created["id"] == 4 and created["total"] == 5 and created["version"]
    assert rows(client)["total"] == 5
    assert versioned(client, "delete", "/api/tables/people.csv/rows/0").status_code == 200
    data = rows(client)
    assert data["total"] == 4
    assert [r["id"] for r in data["rows"]] == [0, 1, 2, 3]  # positions reset consistently
    assert versioned(client, "delete", "/api/tables/people.csv/rows/999").status_code == 404


def test_add_column(ctx):
    client, _ = ctx
    assert versioned(client, "post", "/api/tables/people.csv/columns", json={"name": "city"}).status_code == 201
    assert versioned(client, "post", "/api/tables/people.csv/columns", json={"name": "city"}).status_code == 409
    assert rows(client)["columns"][-1] == {"name": "city", "type": "text"}


def test_history_records_changes(ctx):
    client, tmp = ctx
    versioned(client, "patch", "/api/tables/people.csv/rows/0", json={"column": "score", "value": "95"})
    history = client.get("/api/tables/people.csv/history").get_json()
    assert history[0]["action"] == "update_cell"
    assert history[0]["old"] == "90" and history[0]["new"] == "95"
    assert json.loads((tmp / "changes.jsonl").read_text().splitlines()[0])["column"] == "score"


def test_upload_and_download(ctx):
    client, _ = ctx
    res = client.post(
        "/api/tables",
        data={"file": (io.BytesIO(b"a,b\n1,2\n"), "new.csv")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    assert res.get_json() == {"name": "new.csv", "rows": 1, "columns": 2}
    dup = client.post("/api/tables", data={"file": (io.BytesIO(b"a\n1\n"), "new.csv")}, content_type="multipart/form-data")
    assert dup.status_code == 409
    bad = client.post("/api/tables", data={"file": (io.BytesIO(b"x"), "notes.txt")}, content_type="multipart/form-data")
    assert bad.status_code == 400
    assert client.get("/api/tables/new.csv/download").data == b"a,b\n1,2\n"


def test_unknown_or_unsafe_table_names(ctx):
    client, _ = ctx
    assert client.get("/api/tables/missing.csv/rows").status_code == 404
    assert client.get("/api/tables/..%2Fsecret.csv/rows").status_code == 404


def test_writes_require_a_current_version(ctx):
    client, tmp = ctx
    original = (tmp / "people.csv").read_bytes()
    missing = client.patch("/api/tables/people.csv/rows/0", json={"column": "name", "value": "Wrong"})
    assert missing.status_code == 428
    assert (tmp / "people.csv").read_bytes() == original

    old_version = rows(client)["version"]
    changed = client.patch("/api/tables/people.csv/rows/0", headers={"If-Match": old_version},
                           json={"column": "name", "value": "Updated"})
    assert changed.status_code == 200
    assert changed.get_json()["version"] != old_version
    stale = client.patch("/api/tables/people.csv/rows/1", headers={"If-Match": old_version},
                         json={"column": "name", "value": "Stale"})
    assert stale.status_code == 409
    assert "Refresh" in stale.get_json()["error"]
    assert "Stale" not in (tmp / "people.csv").read_text()


def test_external_insert_cannot_silently_edit_wrong_row(ctx):
    client, tmp = ctx
    current_version = rows(client)["version"]
    (tmp / "people.csv").write_text("id,name,score,code\n0,Outside,1,000\n" + CSV.split("\n", 1)[1])
    response = client.patch("/api/tables/people.csv/rows/1", headers={"If-Match": current_version},
                            json={"column": "name", "value": "Wrong row"})
    assert response.status_code == 409
    assert "Wrong row" not in (tmp / "people.csv").read_text()
    assert rows(client)["rows"][0]["cells"][1] == "Outside"


def test_numeric_syntax_consistent_with_inference(ctx):
    client, tmp = ctx
    for invalid in ("1_000", "inf", "-inf", "nan", "1e999", "hello"):
        response = versioned(client, "patch", "/api/tables/people.csv/rows/0",
                             json={"column": "score", "value": invalid})
        assert response.status_code == 400, invalid
    assert rows(client)["columns"][2]["type"] == "number"
    for valid in ("1e3", "-10.5", ".25"):
        response = versioned(client, "patch", "/api/tables/people.csv/rows/0",
                             json={"column": "score", "value": valid})
        assert response.status_code == 200, valid
        assert rows(client)["columns"][2]["type"] == "number"


def test_deletion_row_position_consistent_after_restart(ctx):
    client, tmp = ctx
    response = versioned(client, "delete", "/api/tables/people.csv/rows/0")
    assert response.status_code == 200
    assert [r["id"] for r in rows(client)["rows"]] == [0, 1, 2]
    client2 = create_app(str(tmp)).test_client()
    assert [r["id"] for r in rows(client2)["rows"]] == [0, 1, 2]
    assert rows(client2)["rows"][0]["cells"][1] == "bob"


def test_quote_all_preserved_with_embedded_comma_and_escaped_quote(tmp_path):
    source = '"id","name"\r\n"001","Acme, Inc"\r\n"002","say ""hello"""\r\n'
    (tmp_path / "quotes.csv").write_bytes(source.encode("utf-8"))
    client = create_app(str(tmp_path)).test_client()
    version = client.get("/api/tables/quotes.csv/rows").get_json()["version"]
    response = client.patch("/api/tables/quotes.csv/rows/0", headers={"If-Match": version},
                            json={"column": "name", "value": "Beta"})
    assert response.status_code == 200
    assert (tmp_path / "quotes.csv").read_bytes() == source.replace("Acme, Inc", "Beta").encode("utf-8")


def test_blank_lines_and_missing_final_newline_preserved(tmp_path):
    source = "id,name\r\n\r\n1,Alice\r\n\r\n2,Bob\r\n\r\n"
    path = tmp_path / "blanks.csv"
    path.write_bytes(source.encode())
    client = create_app(str(tmp_path)).test_client()
    result = client.get("/api/tables/blanks.csv/rows").get_json()
    assert result["total"] == 2
    response = client.patch("/api/tables/blanks.csv/rows/0", headers={"If-Match": result["version"]},
                            json={"column": "name", "value": "Alicia"})
    assert response.status_code == 200
    assert path.read_bytes() == source.replace("Alice", "Alicia").encode()

    other = tmp_path / "no_final.csv"
    other.write_bytes(b"id,name\n1,Alice")
    version = client.get("/api/tables/no_final.csv/rows").get_json()["version"]
    assert client.patch("/api/tables/no_final.csv/rows/0", headers={"If-Match": version},
                        json={"column": "name", "value": "Alicia"}).status_code == 200
    assert other.read_bytes() == b"id,name\n1,Alicia"


def test_utf8_bom_and_latin1_preserved(tmp_path):
    utf = tmp_path / "bom.csv"
    utf.write_bytes(b"\xef\xbb\xbf" + "id,name\n1,Café\n".encode())
    latin = tmp_path / "latin.csv"
    latin.write_bytes("id,name\r\n1,Café\r\n".encode("latin-1"))
    client = create_app(str(tmp_path)).test_client()
    for name, path, encoding, expected_prefix in [
        ("bom.csv", utf, "utf-8", b"\xef\xbb\xbf"), ("latin.csv", latin, "latin-1", b"id,name\r\n")
    ]:
        current = client.get(f"/api/tables/{name}/rows").get_json()
        assert current["rows"][0]["cells"][1] == "Café"
        assert client.patch(f"/api/tables/{name}/rows/0", headers={"If-Match": current["version"]},
                            json={"column": "name", "value": "René"}).status_code == 200
        assert path.read_bytes().startswith(expected_prefix)
        assert "René".encode(encoding) in path.read_bytes()


def test_invalid_upload_leaves_no_csv(ctx):
    client, tmp = ctx
    res = client.post('/api/tables', data={"file": (io.BytesIO(b'x,x\n1,2\n'), 'bad.csv')},
                      content_type='multipart/form-data')
    assert res.status_code == 400
    assert not (tmp / 'bad.csv').exists()
    assert not [p for p in tmp.iterdir() if p.name.endswith('.upload.tmp')]


def test_failed_non_os_encoding_error_invalidates_cache(tmp_path):
    (tmp_path / "latin.csv").write_bytes("id,name\n1,Café\n".encode("latin-1"))
    client = create_app(str(tmp_path)).test_client()
    current = client.get("/api/tables/latin.csv/rows").get_json()
    response = client.patch("/api/tables/latin.csv/rows/0", headers={"If-Match": current["version"]},
                            json={"column": "name", "value": "😀"})
    assert response.status_code == 500
    assert client.get("/api/tables/latin.csv/rows").get_json()["rows"][0]["cells"][1] == "Café"
    assert (tmp_path / "latin.csv").read_bytes() == "id,name\n1,Café\n".encode("latin-1")


def test_symlink_csv_is_not_exposed(tmp_path):
    target = tmp_path / 'outside.txt'
    target.write_text('id\nsecret\n')
    link = tmp_path / 'link.csv'
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip('Windows user lacks symlink permission')
    client = create_app(str(tmp_path)).test_client()
    assert client.get('/api/tables/link.csv/rows').status_code == 404
