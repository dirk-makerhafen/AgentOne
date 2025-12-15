#!/usr/bin/env python3
import os
import shutil
import subprocess
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent
MANAGE = ["python3", "manage.py"]
DB_FILE = PROJECT_ROOT / "db.sqlite3"
BACKUP_FILE = PROJECT_ROOT / "db_backup.json"
MIGRATION_DIR_NAME = "migrations"


def run(cmd):
    print(f"\n>>> Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def backup_db():
    print("== Backing up current SQLite DB ==")
    if BACKUP_FILE.exists():
        BACKUP_FILE.unlink()
    run(MANAGE + ["dumpdata", "--natural-primary", "--natural-foreign", "--indent=2", "-o", str(BACKUP_FILE)])
    print("Backup stored at:", BACKUP_FILE)


def remove_migrations():
    print("== Removing migration directories ==")
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if MIGRATION_DIR_NAME in dirs:
            mig_path = Path(root) / MIGRATION_DIR_NAME
            print("Deleting:", mig_path)
            # Delete everything except __init__.py
            for item in mig_path.iterdir():
                if item.name != "__init__.py":
                    if item.is_file():
                        item.unlink()
                    else:
                        shutil.rmtree(item)


def remove_db_file():
    if DB_FILE.exists():
        print("== Removing DB file:", DB_FILE, "==")
        DB_FILE.unlink()
    else:
        print("No DB file found, skipping")


def recreate_schema():
    print("== Creating new empty DB ==")
    run(MANAGE + ["makemigrations"])
    run(MANAGE + ["migrate"])


def restore_backup():
    print("== Restoring data from backup ==")
    run(MANAGE + ["loaddata", str(BACKUP_FILE)])


if __name__ == "__main__":
    print("### Django DB reset & restore tool ###")

    backup_db()
    remove_migrations()
    remove_db_file()
    recreate_schema()
    restore_backup()

    print("\n### DONE! DB and migrations were rebuilt and data restored. ###")
