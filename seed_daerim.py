#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_daerim.py - 대림빌딩 부동산 자료 초기 등록 스크립트

  실행:  python3 seed_daerim.py            (같은 폴더의 building_manager.db)
         python3 seed_daerim.py 다른DB경로

  - 이미 있는 건물/호실은 건너뜁니다(여러 번 실행해도 중복 안 생김).
  - 기존 데이터는 삭제하지 않습니다.

[구성]
  지하2층 B201 / 지하1층 B101 / 1~3층 상가(각 3호) / 4~9층 오피스 / 10층 사옥
  ※ 상가는 호실이 나뉘어 있으나 현재 1층을 제외하고 모두 '단독층 사용'
"""
import sqlite3, os, sys

BUILDING_NAME = '대림빌딩'
BUILDING_ADDR = '서울특별시 영등포구 도림로 140'

# 상태값
ST_SOLO   = '임대중(단독층)'   # 층 전체를 한 임차인이 사용
ST_MERGED = '단독층 통합'      # 위 단독층에 포함되어 개별 임대 불가
ST_EMPTY  = '공실'
ST_OWN    = '사옥(자가사용)'


def build_rooms():
    """(층, 호실번호, 상태, 비고) 목록 생성"""
    rooms = []
    # --- 지하 (단독층 사용) ---
    rooms.append((-2, 'B201', ST_SOLO,  '지하2층 상가 / 단독층'))
    rooms.append((-1, 'B101', ST_SOLO,  '지하1층 상가 / 단독층'))
    # --- 1층 상가: 유일하게 호실 개별 사용 ---
    for n in ('101', '102', '103'):
        rooms.append((1, n, ST_EMPTY, '1층 상가 / 개별 호실'))
    # --- 2·3층 상가: 단독층 사용 (대표 호실 1개가 층 전체) ---
    for fl, nums in ((2, ('201', '202', '203')), (3, ('301', '302', '303'))):
        for i, n in enumerate(nums):
            rooms.append((fl, n,
                          ST_SOLO if i == 0 else ST_MERGED,
                          '%d층 상가 / 단독층%s' % (fl, '' if i == 0 else ' 통합(%s)' % nums[0])))
    # --- 4~9층 오피스 ---
    office = {4: range(440, 450), 5: range(550, 560), 6: range(660, 670),
              7: range(770, 780), 8: range(880, 890), 9: range(990, 1000)}
    for fl in sorted(office):
        for n in office[fl]:
            rooms.append((fl, str(n), ST_EMPTY, '%d층 오피스' % fl))
    # --- 8층 800호, 9층 900호 (각 층 별도 1실) ---
    rooms.append((8, '800', ST_EMPTY, '8층 오피스'))
    rooms.append((9, '900', ST_EMPTY, '9층 오피스'))
    # --- 10층 사옥 ---
    rooms.append((10, '1000', ST_OWN, '10층 사옥(자가사용)'))
    return rooms


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'building_manager.db')
    if not os.path.exists(db_path):
        print('[오류] DB를 찾을 수 없습니다:', db_path); return 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rooms = build_rooms()

    # 1) 건물 (주소 기준 중복 방지)
    row = cur.execute("SELECT id FROM buildings WHERE address = ? OR name = ?",
                      (BUILDING_ADDR, BUILDING_NAME)).fetchone()
    if row:
        bid = row[0]
        print('건물 이미 존재 → 사용 (id=%s)' % bid)
    else:
        cur.execute("INSERT INTO buildings (name, address, floors, rooms_count, is_active) VALUES (?,?,?,?,1)",
                    (BUILDING_NAME, BUILDING_ADDR, 10, len(rooms)))
        bid = cur.lastrowid
        print('건물 등록: %s (id=%s)' % (BUILDING_NAME, bid))

    # 2) 호실 (같은 건물+호실번호 중복 방지)
    added = skipped = 0
    for floor_no, room_no, status, memo in rooms:
        ex = cur.execute("SELECT id FROM rooms WHERE building_id=? AND room_no=?",
                         (bid, room_no)).fetchone()
        if ex:
            skipped += 1
            continue
        cur.execute("""INSERT INTO rooms (building_id, floor_no, room_no, area_sqm, current_room_status, is_active)
                       VALUES (?,?,?,?,?,1)""", (bid, floor_no, room_no, 0.0, status))
        added += 1

    cur.execute("UPDATE buildings SET rooms_count = (SELECT COUNT(*) FROM rooms WHERE building_id=?) WHERE id=?",
                (bid, bid))
    conn.commit()

    print('호실 등록: %d개 추가 / %d개 건너뜀(이미 있음)' % (added, skipped))
    print('총 호실 수:', cur.execute("SELECT COUNT(*) FROM rooms WHERE building_id=?", (bid,)).fetchone()[0])
    print('\n[층별 현황]')
    for fl, cnt in cur.execute("""SELECT floor_no, COUNT(*) FROM rooms WHERE building_id=?
                                  GROUP BY floor_no ORDER BY floor_no""", (bid,)):
        label = ('B%d' % abs(fl)) if fl < 0 else ('%d층' % fl)
        print('  %-4s : %2d실' % (label, cnt))
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
