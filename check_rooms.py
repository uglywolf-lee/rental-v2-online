import sqlite3

conn = sqlite3.connect('building_manager.db')
print('=== rooms 테이블 필드명 ===')
for col in conn.execute('PRAGMA table_info(rooms)').fetchall():
    print(f'  column={col[1]}, type={col[2]}')
print()

print('=== 모든 rooms 데이터 ===')
for r in conn.execute('SELECT id, building_id, floor_no, room_no, area_sqm, current_room_status FROM rooms').fetchall():
    row_type = [type(v).__name__ for v in r]
    print(f'  {r}  (types: {row_type})')

print()
print('=== buildings ===')
for r in conn.execute('SELECT id, name, address FROM buildings').fetchall():
    print(f'  id={r[0]}, name={repr(r[1])}, address={repr(r[2])}')
    
conn.close()
