#!/usr/bin/env python3
"""
routes.py - API 라우팅 모듈
- GET/POST /api/v1/* 엔드포인트 처리
- 테이블 CRUD 연동
"""

import sqlite3, hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_db


def _audit(cur, actor, action, target, detail=''):
    """누가·언제·무엇을 했는지 기록 (실패해도 본작업엔 영향 없음)"""
    try:
        cur.execute("""INSERT INTO audit_logs (actor, action, target, detail, created_at)
                       VALUES (?,?,?,?,datetime('now','localtime'))""",
                    (str(actor or '알수없음'), str(action), str(target), str(detail)[:300]))
    except Exception:
        pass


def _snapshot(cur, table, target_id, snap_type='auto_snapshot'):
    """수정 전 현재 행을 system_snapshots에 JSON으로 저장(되돌리기용). 실패해도 본작업엔 영향 없음."""
    try:
        if not target_id:
            return
        row = cur.execute("SELECT * FROM %s WHERE id=?" % table, (target_id,)).fetchone()
        if row:
            cur.execute(
                "INSERT INTO system_snapshots (snapshot_type, table_name, target_id, data_snapshot_json) VALUES (?,?,?,?)",
                (snap_type, table, target_id, json.dumps(dict(row), ensure_ascii=False)))
    except Exception:
        pass


def handle_get_api(path):
    """GET API 라우팅 - 모든 /api/v1/* 엔드포인트 처리"""
    
    from urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(path)
    endpoint = parsed_url.path.replace('/api/v1/', '')
    qs = parse_qs(parsed_url.query)
    conn = get_db()
    cur = conn.cursor()
    try:
        if endpoint.startswith('contacts'):
            cat = qs.get('category', [None])[0]
            if cat:
                cur.execute("SELECT * FROM contacts WHERE category = ?", (cat,))
            else:
                cur.execute("SELECT * FROM contacts")
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'buildings':
            cur.execute("SELECT * FROM buildings ORDER BY id DESC")
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'rooms':
            cur.execute("""
                SELECT r.*,
                       b.name AS building_name,
                       b.address AS building_address,
                       r.room_no AS room,
                       r.floor_no AS floor,
                       r.area_sqm AS area,
                       r.current_room_status AS status
                FROM rooms r
                LEFT JOIN buildings b ON r.building_id = b.id
                ORDER BY r.id DESC
            """)
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'contracts':
            cur.execute("""
                SELECT c.*, t.company_or_name AS tenant_name, t.contact_info AS tenant_phone
                FROM contracts c
                LEFT JOIN contacts t ON c.tenant_contact_id = t.id
            """)
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'bills':
            cur.execute("SELECT * FROM bills ORDER BY id DESC")
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'incidents':
            cur.execute("SELECT * FROM incidents ORDER BY id DESC")
            rows = [dict(r) for r in cur.fetchall()]
            return 200, rows

        elif endpoint == 'payments':
            cur.execute("SELECT * FROM payments ORDER BY id DESC")
            return 200, [dict(r) for r in cur.fetchall()]

        elif endpoint.startswith('auditlogs'):
            # 로그는 절대 삭제하지 않음. 날짜별로 조회.
            day = qs.get('date', [None])[0]          # 'YYYY-MM-DD'
            if day == 'dates':                        # 기록이 있는 날짜 목록
                cur.execute("""SELECT substr(created_at,1,10) AS d, COUNT(*) AS n
                               FROM audit_logs GROUP BY d ORDER BY d DESC""")
                return 200, [dict(r) for r in cur.fetchall()]
            if day:
                cur.execute("""SELECT id, actor, action, target, detail, created_at
                               FROM audit_logs WHERE substr(created_at,1,10)=?
                               ORDER BY id DESC""", (day,))
            else:                                     # 기본: 가장 최근 기록일
                cur.execute("""SELECT id, actor, action, target, detail, created_at
                               FROM audit_logs
                               WHERE substr(created_at,1,10) =
                                     (SELECT substr(MAX(created_at),1,10) FROM audit_logs)
                               ORDER BY id DESC""")
            return 200, [dict(r) for r in cur.fetchall()]

        elif endpoint.startswith('snapshots'):
            cur.execute("SELECT id, snapshot_type, table_name, target_id, is_restored, created_at FROM system_snapshots ORDER BY id DESC LIMIT 300")
            return 200, [dict(r) for r in cur.fetchall()]

        else:
            return 404, {'error': f'존재하지 않는 GET API: {path}'}
    except Exception as e:
        return 500, {'error': f'GET API 데이터 로딩 실패: {str(e)}'}
    finally:
        conn.close()


def handle_auth_endpoint(path, data):
    """로그인 검증 API"""
    if path not in ['/api/v1/login', '/api/v1/auth', '/api/v1/auth/login']:
        return None

    emp_no = data.get('employee_no') or data.get('username') or data.get('emp')
    password = data.get('password', '')
    input_pw_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    conn = get_db()
    cur = conn.cursor()
    try:
        # 입력한 아이디(사번/이메일)로만 조회. 비활성(is_active=0) 계정은 로그인 불가.
        cur.execute("""SELECT * FROM contacts
                       WHERE representative_name = ? AND category='staff'
                         AND (is_active IS NULL OR is_active = 1)
                       ORDER BY id LIMIT 1""", (emp_no,))
        user = cur.fetchone()

        if user:
            u = dict(user)
            db_pw = u.get('password_hash', '') or ''

            if db_pw and (password == db_pw or input_pw_hash == db_pw):
                return 200, {
                    'status': 'success',
                    'message': '로그인 성공',
                    'user': {
                        'employee_no': u.get('representative_name') or emp_no,
                        'name': u.get('company_or_name') or '',
                        'role': u.get('role') or 'office_worker'
                    },
                    'token': 'sess_' + str(u.get('id'))
                }

        return 401, {'status': 'error', 'message': '아이디 또는 비밀번호가 일치하지 않습니다.'}
    finally:
        conn.close()


def _mark_room_leased(cur, room_id):
    """계약이 생기면 그 호실 상태를 '임대중'으로 자동 변경 (공실로 남아 통계가 틀리는 것 방지).
       단독층/사옥 등 별도 표기된 상태는 건드리지 않음."""
    try:
        if not room_id:
            return
        row = cur.execute("SELECT current_room_status FROM rooms WHERE id=?", (room_id,)).fetchone()
        if not row:
            return
        cur_status = str((row['current_room_status'] if hasattr(row, 'keys') else row[0]) or '')
        if (not cur_status) or ('공실' in cur_status) or ('비어' in cur_status) or ('빈' in cur_status):
            cur.execute("UPDATE rooms SET current_room_status='임대' WHERE id=?", (room_id,))
    except Exception:
        pass


def _resolve_tenant(cur, data):
    """계약서에 입력한 임차인 이름/연락처 → contacts(tenant) 찾거나 새로 등록하고 id 반환"""
    name = str(data.get('tenant_name') or '').strip()
    phone = str(data.get('tenant_phone') or '').strip()
    if not name and not phone:
        return None
    try:
        row = None
        if name and phone:
            row = cur.execute("""SELECT id FROM contacts WHERE category='tenant'
                                 AND company_or_name=? AND contact_info=?""", (name, phone)).fetchone()
        if not row and name:
            row = cur.execute("""SELECT id FROM contacts WHERE category='tenant'
                                 AND company_or_name=? ORDER BY id LIMIT 1""", (name,)).fetchone()
        if not row and phone:
            row = cur.execute("""SELECT id FROM contacts WHERE category='tenant'
                                 AND contact_info=? ORDER BY id LIMIT 1""", (phone,)).fetchone()
        if row:
            tid = row['id'] if hasattr(row, 'keys') else row[0]
            if phone:      # 연락처가 바뀌었으면 갱신
                cur.execute("UPDATE contacts SET contact_info=? WHERE id=?", (phone, tid))
            if name:
                cur.execute("UPDATE contacts SET company_or_name=? WHERE id=?", (name, tid))
            return tid
        cur.execute("""INSERT INTO contacts (category, company_or_name, representative_name, contact_info, is_active)
                       VALUES ('tenant', ?, ?, ?, 1)""", (name or phone, name, phone))
        return cur.lastrowid
    except Exception:
        return None


LABELS = {
    '/api/v1/buildings': '건물', '/api/v1/rooms': '호실', '/api/v1/contacts': '연락처/직원',
    '/api/v1/contracts': '계약', '/api/v1/bills': '공과금', '/api/v1/incidents': '유지보수',
    '/api/v1/payments': '수납',
}


def handle_post_api(path, data):
    """POST API CRUD 처리"""
    conn = get_db()
    try:
        cur = conn.cursor()
        # ── 작업 로그: 누가 무엇을 했는지 자동 기록 ──
        _actor = data.get('_actor') or data.get('actor') or ''
        if path in LABELS:
            _audit(cur, _actor,
                   ('수정' if data.get('id') else '등록'),
                   LABELS[path],
                   (data.get('company_or_name') or data.get('name') or data.get('room_no')
                    or data.get('description') or data.get('common_area') or ''))

        if path == '/api/v1/buildings':
            bid_edit = data.get('id')
            if bid_edit:                      # 수정
                _snapshot(cur, 'buildings', bid_edit)
                fields, vals = [], []
                for k in ('name', 'address', 'floors', 'rooms_count', 'is_active'):
                    if k in data:
                        fields.append(k + '=?'); vals.append(data[k])
                if fields:
                    vals.append(bid_edit)
                    cur.execute("UPDATE buildings SET %s WHERE id=?" % ','.join(fields), vals)
                    conn.commit()
                return 200, {'id': bid_edit, 'success': True, 'message': '건물 정보 수정 완료'}
            name = data.get('name')
            addr = data.get('address')
            floors = int(data.get('floors', 1) or 1)
            rooms_cnt = int(data.get('rooms_count', 1) or 1)
            cur.execute("INSERT INTO buildings (name, address, floors, rooms_count) VALUES (?, ?, ?, ?)",
                        (name, addr, floors, rooms_cnt))
            bid = cur.lastrowid
            conn.commit()
            return 201, {'id': bid, 'success': True, 'message': '건물 등록 완료'}

        elif path == '/api/v1/rooms':
            rid_edit = data.get('id')
            if rid_edit:                      # 수정
                _snapshot(cur, 'rooms', rid_edit)
                fields, vals = [], []
                mapping = {
                    'building_id': 'building_id', 'floor_no': 'floor_no', 'floor': 'floor_no',
                    'room_no': 'room_no', 'room': 'room_no',
                    'area_sqm': 'area_sqm', 'area': 'area_sqm',
                    'current_room_status': 'current_room_status', 'status': 'current_room_status',
                    'is_active': 'is_active',
                }
                used = set()
                for k, col in mapping.items():
                    if k in data and col not in used:
                        used.add(col); fields.append(col + '=?'); vals.append(data[k])
                if fields:
                    vals.append(rid_edit)
                    cur.execute("UPDATE rooms SET %s WHERE id=?" % ','.join(fields), vals)
                    conn.commit()
                return 200, {'id': rid_edit, 'success': True, 'message': '호실 정보 수정 완료'}
            b_id = int(data.get('building_id') or 0)
            floor = int(data.get('floor_no') or data.get('floor') or 1)
            room_no = str(data.get('room_no') or data.get('room') or '')
            area = float(data.get('area_sqm') or data.get('area') or 0.0)
            status = str(data.get('current_room_status') or data.get('status') or '공실')
            cur.execute("INSERT INTO rooms (building_id, floor_no, room_no, area_sqm, current_room_status) VALUES (?, ?, ?, ?, ?)",
                        (b_id, floor, room_no, area, status))
            rid = cur.lastrowid
            conn.commit()
            return 201, {'id': rid, 'success': True, 'message': '호실 등록 완료'}

        elif path == '/api/v1/contacts':
            cid = data.get('id')
            if cid:
                _snapshot(cur, 'contacts', cid)   # 수정 전 스냅샷
                if 'is_active' in data and len(data.keys()) <= 3:
                    cur.execute("UPDATE contacts SET is_active=? WHERE id=?", (int(data['is_active']), cid))
                    conn.commit()
                    return 200, {'id': cid, 'message': '직무 상태 변경 완료'}

                if 'password_hash' in data and len(data.keys()) <= 3:
                    cur.execute("UPDATE contacts SET password_hash=? WHERE id=?", (str(data['password_hash']), cid))
                    conn.commit()
                    return 200, {'id': cid, 'message': '비밀번호 변경 완료'}

                fields, vals = [], []
                for k in ['category', 'company_or_name', 'representative_name', 'contact_info', 'email', 'password_hash', 'role', 'role_name', 'is_active', 'documents_json', 'account_no']:
                    if k in data:
                        fields.append(f"{k}=?")
                        vals.append(data[k])
                if fields:
                    vals.append(cid)
                    cur.execute(f"UPDATE contacts SET {','.join(fields)} WHERE id=?", vals)
                    conn.commit()
                return 200, {'id': cid, 'success': True, 'message': '연락처/팀원 수정 완료'}
            else:
                cat = data.get('category', 'tenant')
                name = data.get('company_or_name') or data.get('name', '')
                rep = data.get('representative_name') or data.get('rep') or data.get('employee_no', '')
                phone = data.get('contact_info') or data.get('phone', '')
                email = data.get('email', '')
                pw = data.get('password_hash') or data.get('password', '')
                role = data.get('role', 'office_worker')
                docs = data.get('documents_json', '[]')
                acct = data.get('account_no', '')
                cur.execute("""
                    INSERT INTO contacts (category, company_or_name, representative_name, contact_info, email, password_hash, role, role_name, is_active, documents_json, account_no)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (cat, name, rep, phone, email, pw, role, role, docs, acct))
                new_cid = cur.lastrowid
                conn.commit()
                return 201, {'id': new_cid, 'success': True, 'message': '연락처/팀원 등록 완료'}

        elif path == '/api/v1/bills':
            bill_edit = data.get('id')
            if bill_edit:                        # 수정 (되돌리기용 스냅샷 후 갱신)
                _snapshot(cur, 'bills', bill_edit)
                fields, vals = [], []
                for k in ('room_id', 'building_id', 'scope', 'common_area', 'bill_type',
                          'elec_usage', 'elec_cost', 'water_cost', 'gas_cost', 'net_cost',
                          'due_date', 'status'):
                    if k in data:
                        fields.append(k + '=?'); vals.append(data[k])
                if fields:
                    vals.append(bill_edit)
                    cur.execute("UPDATE bills SET %s WHERE id=?" % ','.join(fields), vals)
                    conn.commit()
                return 200, {'id': bill_edit, 'success': True, 'message': '공과금 수정 완료'}
            room_id = int(data.get('room_id') or 0)
            scope = str(data.get('scope') or 'room')
            building_id = int(data.get('building_id') or 0)
            common_area = str(data.get('common_area') or '')
            # 공용(복도/공동화장실 등)은 호실 대신 건물 기준
            if scope == 'common':
                if not building_id:
                    return 400, {'error': '공용 비용은 건물을 선택해 주세요.'}
            elif not room_id:
                return 400, {'error': '올바른 호실(room_id FK)을 선택해 주세요.'}
            elec = int(data.get('elec_usage', 0) or 0)
            elec_cost = int(data.get('elec_cost', 0) or 0)
            water = int(data.get('water_cost', 0) or 0)
            gas = int(data.get('gas_cost', 0) or 0)
            net = int(data.get('net_cost', 0) or 0)
            due = str(data.get('due_date', '') or '')
            status = str(data.get('status', '미납(고지대기)'))
            cur.execute("""
                INSERT INTO bills (room_id, building_id, scope, common_area, elec_usage, elec_cost, water_cost, gas_cost, net_cost, due_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (room_id, building_id, scope, common_area, elec, elec_cost, water, gas, net, due, status))
            bid = cur.lastrowid
            conn.commit()
            return 201, {'id': bid, 'success': True, 'message': '공과금 고지 등록 완료'}

        elif path == '/api/v1/incidents':
            inc_edit = data.get('id')
            if inc_edit:                       # 수정
                _snapshot(cur, 'incidents', inc_edit)
                fields, vals = [], []
                for k in ('room_id', 'building_id', 'scope', 'common_area', 'category',
                          'reported_at', 'completed_at', 'description', 'reported_by_name',
                          'estimated_cost', 'status', 'photos_json'):
                    if k in data:
                        fields.append(k + '=?'); vals.append(data[k])
                if fields:
                    vals.append(inc_edit)
                    cur.execute("UPDATE incidents SET %s WHERE id=?" % ','.join(fields), vals)
                    conn.commit()
                return 200, {'id': inc_edit, 'success': True, 'message': '유지보수 내역 수정 완료'}
            room_id = int(data.get('room_id') or 0)
            i_scope = str(data.get('scope') or 'room')
            i_building = int(data.get('building_id') or 0)
            i_common = str(data.get('common_area') or '')
            if i_scope == 'common':
                if not i_building:
                    return 400, {'error': '공용 유지보수는 건물을 선택해 주세요.'}
            elif not room_id:
                return 400, {'error': '올바른 호실(room_id FK)을 선택해 주세요.'}
            cat = str(data.get('category', '시설파손'))
            rep_at = str(data.get('reported_at', ''))
            comp_at = str(data.get('completed_at', ''))
            desc = str(data.get('description', ''))
            staff = str(data.get('reported_by_name', ''))
            cost = int(data.get('estimated_cost', 0) or 0)
            status = str(data.get('status', '접수중'))
            photos = str(data.get('photos_json') or '[]')
            cur.execute("""
                INSERT INTO incidents (room_id, building_id, scope, common_area, category, reported_at, completed_at, description, reported_by_name, estimated_cost, status, photos_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (room_id, i_building, i_scope, i_common, cat, rep_at, comp_at, desc, staff, cost, status, photos))
            iid = cur.lastrowid
            conn.commit()
            return 201, {'id': iid, 'success': True, 'message': '유지보수/파손신고 등록 완료'}

        elif path == '/api/v1/contracts':
            cid = data.get('id')
            special_terms = data.get('special_terms')

            if cid and special_terms is not None and len(data.keys()) <= 3:
                cur.execute("UPDATE contracts SET special_terms = ? WHERE id = ?", (str(special_terms).strip(), cid))
                conn.commit()
                return 200, {'id': cid, 'success': True, 'message': '수납 메모 자동 저장 완료'}

            if cid:
                _snapshot(cur, 'contracts', cid)   # 수정 전 스냅샷
                # 임차인 이름/연락처 → contacts 연결 (계약자 명부 연동)
                t_id = data.get('tenant_contact_id') or _resolve_tenant(cur, data)
                cur.execute("""
                    UPDATE contracts SET
                        room_id=?, host_address_full=?, lease_type=?, deposit_amount=?,
                        monthly_rent=?, maintenance_fee=?, commission_fee=?, start_date=?,
                        end_date=?, documents_json=?, special_terms=?
                    WHERE id=?
                """, (
                    data.get('room_id'), data.get('host_address_full', ''), data.get('lease_type', '월세'),
                    data.get('deposit_amount', 0), data.get('monthly_rent', 0), data.get('maintenance_fee', 0),
                    data.get('commission_fee', 0), data.get('start_date', ''), data.get('end_date', ''),
                    data.get('documents_json', '[]'), str(special_terms or '').strip(), cid
                ))
                if t_id:
                    cur.execute("UPDATE contracts SET tenant_contact_id=? WHERE id=?", (t_id, cid))
                _mark_room_leased(cur, data.get('room_id'))
                conn.commit()
                return 200, {'id': cid, 'success': True, 'message': '계약 정보 수정 완료'}

            # 신규 계약 등록
            room_id = int(data.get('room_id') or 0)
            host_addr = str(data.get('host_address_full', ''))
            owner_cid = int(data.get('owner_contact_id', 1) or 1)
            # 임차인 이름/연락처가 오면 contacts(tenant)에 자동 등록/연결
            tenant_cid = int(data.get('tenant_contact_id') or 0) or int(_resolve_tenant(cur, data) or 0)
            broker_id = int(data.get('broker_id', 0) or 0)
            lease_type = str(data.get('lease_type', '월세'))
            deposit = int(data.get('deposit_amount', 0) or 0)
            monthly = int(data.get('monthly_rent', 0) or 0)
            maint_fee = int(data.get('maintenance_fee', 0) or 0)
            comm_fee = int(data.get('commission_fee', 0) or 0)
            s_date = str(data.get('start_date', ''))
            e_date = str(data.get('end_date', ''))
            docs_json = str(data.get('documents_json') or '[]')

            if not lease_type:
                return 400, {'error': '계약 종류 필수'}
            if not s_date:
                return 400, {'error': '계약 시작일 필수'}

            cur.execute("""
                INSERT INTO contracts (room_id, host_address_full, owner_contact_id, tenant_contact_id, broker_id,
                                      lease_type, deposit_amount, monthly_rent, maintenance_fee, commission_fee,
                                      start_date, end_date, documents_json, special_terms, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (room_id, host_addr, owner_cid, tenant_cid, broker_id, lease_type, deposit, monthly, maint_fee, comm_fee, s_date, e_date, docs_json, str(special_terms or '').strip()))
            new_cid = cur.lastrowid
            _mark_room_leased(cur, room_id)
            conn.commit()
            return 201, {'id': new_cid, 'success': True, 'message': '계약서 등록 완료'}

        elif path == '/api/v1/payments':
            pay_edit = data.get('id')
            if pay_edit:                       # 수정
                _snapshot(cur, 'payments', pay_edit)
                fields, vals = [], []
                for k in ('contract_id', 'room_id', 'period', 'pay_date', 'amount', 'pay_type', 'memo'):
                    if k in data:
                        fields.append(k + '=?'); vals.append(data[k])
                if fields:
                    vals.append(pay_edit)
                    cur.execute("UPDATE payments SET %s WHERE id=?" % ','.join(fields), vals)
                    conn.commit()
                return 200, {'id': pay_edit, 'success': True, 'message': '수납 내역 수정 완료'}
            room_id = int(data.get('room_id') or 0)
            cur.execute("""INSERT INTO payments (contract_id, room_id, period, pay_date, amount, pay_type, memo)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (data.get('contract_id'), room_id, str(data.get('period', '')), str(data.get('pay_date', '')),
                 int(data.get('amount', 0) or 0), str(data.get('pay_type', '정상완납')), str(data.get('memo', ''))))
            pid = cur.lastrowid
            conn.commit()
            return 201, {'id': pid, 'success': True, 'message': '수납 기록 완료'}

        elif path == '/api/v1/snapshots/restore':
            sid = data.get('id')
            if not sid:
                return 400, {'error': 'snapshot id 필요'}
            row = cur.execute("SELECT * FROM system_snapshots WHERE id=?", (sid,)).fetchone()
            if not row:
                return 404, {'error': '스냅샷을 찾을 수 없습니다.'}
            snap = dict(row)
            tbl = snap.get('table_name'); tid = snap.get('target_id')
            if tbl not in ('contacts', 'contracts', 'bills', 'rooms', 'incidents'):
                return 400, {'error': '복구 불가 테이블'}
            payload = json.loads(snap.get('data_snapshot_json') or '{}')
            cols = [k for k in payload.keys() if k != 'id']
            if not cols:
                return 400, {'error': '복구할 데이터 없음'}
            setclause = ','.join('%s=?' % k for k in cols)
            vals = [payload[k] for k in cols] + [tid]
            cur.execute("UPDATE %s SET %s WHERE id=?" % (tbl, setclause), vals)
            cur.execute("UPDATE system_snapshots SET is_restored=1 WHERE id=?", (sid,))
            conn.commit()
            return 200, {'success': True, 'message': '되돌리기 완료'}

        return 404, {'error': '요청한 API 엔드포인트가 없습니다.'}
    except Exception as e:
        return 500, {'error': f'서버 내부 오류: {str(e)}'}
    finally:
        conn.close()
