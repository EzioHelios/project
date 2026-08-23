"""Compatibility entry point for the canonical XTCK migration.

The former implementation copied every legacy table into the application and
disabled foreign-key checks. That path was removed with the legacy Scope
ledgers. Use ``migrate_xtck_data`` so tenant isolation and canonical inventory
rules are always applied.
"""

from __future__ import annotations

from migrate_xtck_data import main

if __name__ == "__main__":
    main()
