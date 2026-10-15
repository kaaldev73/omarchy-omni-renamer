"""Seed mock/folders with folders that have real OmniRename history.

The history goes to mock/state, so your real undo history is untouched. Open the
window on the mock with:

    XDG_STATE_HOME=mock/state python omni_care.py mock/folders/chains/*

Run this script again to reset everything.
"""
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOCK = HERE / "folders"
STATE = HERE / "state"
os.environ["XDG_STATE_HOME"] = str(STATE)
sys.path.insert(0, str(HERE.parent))

from omni_care import default_history  # noqa: E402
from omni_renamer import RenameTransaction, build_manual_plan  # noqa: E402

shutil.rmtree(MOCK, ignore_errors=True)
shutil.rmtree(STATE, ignore_errors=True)


def batch(*pairs):
    """Rename every (current, new) pair together, recording history."""
    plan = build_manual_plan((MOCK / old, new) for old, new in pairs)
    RenameTransaction(default_history()).apply(plan)


# 1. Plain chains: three folders, each renamed three times in one batch
for name in ("trip photos", "tax papers", "music demos"):
    (MOCK / "chains" / name).mkdir(parents=True)
    (MOCK / "chains" / name / "file.txt").write_text(name)
batch(("chains/trip photos", "trip_photos"), ("chains/tax papers", "tax_papers"), ("chains/music demos", "music_demos"))
batch(("chains/trip_photos", "trip-photos"), ("chains/tax_papers", "tax-papers"), ("chains/music_demos", "music-demos"))
batch(("chains/trip-photos", "TripPhotos"), ("chains/tax-papers", "TaxPapers"), ("chains/music-demos", "MusicDemos"))

# 2. Swap: alpha and beta trade names in one batch
for name in ("alpha", "beta"):
    (MOCK / "swap" / name).mkdir(parents=True)
    (MOCK / "swap" / name / "was.txt").write_text(f"originally {name}")
batch(("swap/alpha", "beta"), ("swap/beta", "alpha"))

# 3. Nested: inner renamed first, then its parent
(MOCK / "nested" / "outer" / "inner").mkdir(parents=True)
batch(("nested/outer/inner", "inner-renamed"))
batch(("nested/outer", "outer-renamed"))

# 4. Blocked: the old name has been taken by a new folder
(MOCK / "blocked" / "report").mkdir(parents=True)
batch(("blocked/report", "report-final"))
(MOCK / "blocked" / "report").mkdir()

# 5. Never renamed: should be skipped by undo
(MOCK / "untouched").mkdir()

print(f"Seeded {MOCK}; history at {default_history().path}")
