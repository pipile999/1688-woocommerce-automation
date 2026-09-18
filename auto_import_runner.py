"""Run from the repository root; `--dry-run` never changes the store."""
from app.auto_import_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
