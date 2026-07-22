"""db_rooms_query — rooms 관련 쿼리 빌더 (Server utility)"""
__version__ = "1.0.0"

def build_rooms_sql(building_id=None, search=None):
    """rooms 조회 SQL + args 튜플 반환
    
    Args:
        building_id: int or 'all' - 건물 ID 필터
        search: str or None - 검색 키워드 (건물명/호실명)
    
    Returns:
        tuple (sql_clause, args) where sql_clause is the full query string
              and args is a tuple of bind parameters
    """
    base = (
        "SELECT r.id, b.name, r.floor_no, r.room_no, "
        "r.area_sqm, r.current_room_status "
        "FROM rooms r JOIN buildings b ON r.building_id=b.id"
    )
    
    conditions = []
    args = []  # type: list
    
    if building_id is not None and building_id != 'all':
        try:
            conditions.append("r.building_id = ?")
            args.append(building_id)
        except (TypeError, ValueError):
            pass
    
    if search:
        kw = f"%{search.lower()}%"
        conditions.append("(LOWER(b.name) LIKE ? OR LOWER(r.room_no) LIKE ?)")
        args += [kw, kw]
    
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    
    base += " ORDER BY r.building_id, r.floor_no, r.room_no"
    return (base, tuple(args))

def format_rooms_row(row):
    """DB row → dict for JSON response"""
    return {
        'id': row[0],
        'building_name': row[1],
        'floor': row[2],
        'room': row[3],
        'area': row[4],
        'status': row[5],
    }
