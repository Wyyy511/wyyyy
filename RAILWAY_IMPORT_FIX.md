# V8.1 Railway Import Fix

This build fixes `ModuleNotFoundError: No module named 'tools'` seen on Railway.

Changes:
- `server.py` explicitly adds the repository root to `sys.path` before local imports.
- Railway start command explicitly sets `PYTHONPATH=/app`.
- `tools/`, `agent/`, `core/`, `engines/`, `data/`, and `static/` are all included at repository root.
- `/api/health` reports version `8.1` so you can verify the new deployment.

## GitHub upload check
After extracting this ZIP, the GitHub repository root must directly show:
`server.py`, `main.py`, `requirements.txt`, `railway.json`, `tools/`, `agent/`, `core/`, `engines/`, `data/`, `static/`.

Do not upload only the ZIP file itself.
