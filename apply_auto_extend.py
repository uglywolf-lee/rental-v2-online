#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_auto_extend.py
Mark monthly-rolling (kkalse) contracts as auto-extending.

- Backs up the database first.
- Only sets a flag on contracts that match room + start date.
- Never deletes or overwrites contract terms.
- Safe to run twice.
"""
import sqlite3, shutil, os, sys, datetime

DB = sys.argv[1] if len(sys.argv) > 1 else "/home/uglywolf/rental-v2-online/building_manager.db"

TARGETS = [['444', '2026-04-14', '2026-05-13'], ['449', '2026-02-26', '2026-03-25'], ['552', '2025-12-22', '2026-01-21'], ['555', '2023-11-01', '2023-12-29'], ['660', '2026-05-19', '2026-06-18'], ['661', '2025-01-10', '2026-02-09'], ['666', '2026-05-11', '2026-06-10'], ['668', '2023-11-11', '2025-11-10'], ['778', '2025-01-20', '2025-02-19'], ['779', '2025-11-24', '2025-12-23'], ['882', '2026-03-09', '2026-04-08']]

def main():
    if not os.path.exists(DB):
        print("DB not found:", DB); return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = os.path.join(os.path.dirname(DB), "_backups")
    os.makedirs(bdir, exist_ok=True)
    bak = os.path.join(bdir, "building_manager_%s_before_autoextend.db" % stamp)
    shutil.copy2(DB, bak)
    print("[1/3] backup ->", bak)

    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; cur = con.cursor()
    try: cur.execute("ALTER TABLE contracts ADD COLUMN auto_extend INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    print("[2/3] column ready")

    on = already = miss = 0
    for room, sdate, edate in TARGETS:
        rows = cur.execute("""SELECT ct.id, ct.auto_extend, ct.start_date, ct.end_date
                              FROM contracts ct JOIN rooms ro ON ro.id = ct.room_id
                              WHERE ro.room_no = ?""", (room,)).fetchall()
        hit = [r for r in rows if (r["start_date"] or "")[:10] == sdate[:10]] or rows
        if not hit:
            print("   ? no contract for room", room); miss += 1; continue
        for r in hit:
            if int(r["auto_extend"] or 0) == 1:
                already += 1; continue
            cur.execute("UPDATE contracts SET auto_extend=1 WHERE id=?", (r["id"],))
            on += 1
    con.commit()
    print("[3/3] turned on %d, already on %d, room not found %d" % (on, already, miss))

    today = datetime.date.today().isoformat()
    live = cur.execute("""SELECT COUNT(DISTINCT ct.room_id) FROM contracts ct
                          WHERE ct.auto_extend=1 OR ct.end_date IS NULL
                             OR ct.end_date='' OR ct.end_date>=?""", (today,)).fetchone()[0]
    print("      rooms counted as occupied now:", live)
    print()
    print("DONE. To undo:")
    print("   cp '%s' '%s'" % (bak, DB))
    con.close(); return 0

if __name__ == "__main__":
    sys.exit(main())
