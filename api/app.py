"""GridLite data API (Flask).

This service owns the data: it reads and writes the CSV files in the data
folder through storage.CsvStore. The browser never calls it directly; every
request comes through the Node gateway (see ../gateway/server.js).

Run:  python app.py        (listens on http://127.0.0.1:5001 by default)
"""

import os

from flask import Flask, jsonify, request, send_file

from storage import CsvStore, StoreError

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "..", "data"))
MAX_PAGE_SIZE = 500


def create_app(data_dir=DATA_DIR):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit
    store = CsvStore(data_dir)

    # ---------- error handling: always answer with JSON ----------

    @app.errorhandler(StoreError)
    def handle_store_error(err):
        return jsonify(error=str(err)), err.status

    @app.errorhandler(413)
    def handle_too_large(_err):
        return jsonify(error="File is too large (max 100 MB)"), 413

    @app.errorhandler(404)
    def handle_not_found(_err):
        return jsonify(error="Not found"), 404

    def body():
        return request.get_json(silent=True) or {}

    def int_arg(name, default, low, high):
        try:
            value = int(request.args.get(name, default))
        except ValueError:
            value = default
        return max(low, min(high, value))

    def version():
        # Send the SHA-256 version returned by GET /rows on every write.
        # This prevents stale row positions from silently changing another row.
        return request.headers.get("If-Match")

    # ---------- routes ----------

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="flask")

    @app.get("/api/tables")
    def list_tables():
        return jsonify(store.list_tables())

    @app.post("/api/tables")
    def upload_table():
        file = request.files.get("file")
        if file is None:
            return jsonify(error="Send the CSV as form field 'file'"), 400
        return jsonify(store.create_from_upload(file)), 201

    @app.get("/api/tables/<name>/rows")
    def get_rows(name):
        return jsonify(
            store.query(
                name,
                page=int_arg("page", 1, 1, 10**9),
                page_size=int_arg("page_size", 50, 1, MAX_PAGE_SIZE),
                sort=request.args.get("sort") or None,
                order=request.args.get("order", "asc"),
                search=request.args.get("search", ""),
                search_column=request.args.get("search_column", ""),
            )
        )

    @app.post("/api/tables/<name>/rows")
    def add_row(name):
        return jsonify(store.add_row(name, version())), 201

    @app.patch("/api/tables/<name>/rows/<int:row_id>")
    def update_cell(name, row_id):
        data = body()
        if "column" not in data:
            return jsonify(error="Body must include 'column' and 'value'"), 400
        return jsonify(store.update_cell(name, row_id, data["column"], data.get("value"), version()))

    @app.delete("/api/tables/<name>/rows/<int:row_id>")
    def delete_row(name, row_id):
        return jsonify(store.delete_row(name, row_id, version()))

    @app.post("/api/tables/<name>/columns")
    def add_column(name):
        return jsonify(store.add_column(name, body().get("name"), version())), 201

    @app.get("/api/tables/<name>/history")
    def history(name):
        return jsonify(store.history(name, limit=int_arg("limit", 50, 1, 500)))

    @app.get("/api/tables/<name>/download")
    def download(name):
        return send_file(store.file_path(name), mimetype="text/csv", as_attachment=True, download_name=name)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    print(f"GridLite API on http://127.0.0.1:{port}  (data folder: {os.path.abspath(DATA_DIR)})")
    create_app().run(host="127.0.0.1", port=port, debug=debug)
