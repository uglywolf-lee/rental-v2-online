window.REAL_ESTATE_SYSTEM_SPEC = `
# REAL_ESTATE_SYSTEM_SPEC (v2.0 - 2026-07-22 최종확정본)
# 서버: db_app.py 484줄 | DB: building_manager.db (SQLite)

## 0. GLOBAL_STANDARDS
* AUTH: 모든 접근은 /api/v1/ 라우팅으로 통일
* DATETIME: DB=TEXT('YYYY-MM-DD HH:MM:SS') | UI=TEXT('YYYY-MM-DD')
* PHONE_FORMAT: 'NN-NNNN-NNNN' (14자 고정)
* EMAIL: lowercase_only @domain.tld
* AMOUNT_BILL: DB=INTEGER(원단위) | UI='원단위' 고정

## 1. CORE_RULES
* R1: 주소 기반 DB (부동산 근원은 주소지)
* R2: 고유 ID가 PK
* R3: INSERT/UPDATE만 가능, DELETE 영구 금지
* R5: DB 수정 허용 (이력 추적 필수)
* R6: 동일 주소 + 동일 층 + 동일 호 조합 중복 절대 불가
* R8: 수정 시 is_active=0 처리
* R15: super_admin(전권) / office_worker(검색/입력만) / maintenance_staff(신고접수/조회만, 계약서불가)
* R24: 독립 단일 HTML/CSS/JS 구조, REST API('/api/v1/') 분리
* R26: 영문 필드명 UI 노출 절대 금지 -> 우리말 치환 필수

## 2. DATABASE_SCHEMA (db_app.py 기준)
### buildings
* id(Integer/_PK/AI), name(VARCHAR,Req), address(VARCHAR,500,Req), floors(INTEGER), rooms_count(INTEGER), is_active(BIT/1,Default)
**server_sql**: SELECT id,name,address,floors,rooms_count,is_active FROM buildings WHERE is_active=1 ORDER BY id

### rooms
* id(Integer/AI), building_id(Integer/FK→buildings.id), floor_no(INTEGER), room_no(VARCHAR,50), area_sqm(REAL), current_room_status(VARCHAR)
**server_sql**: SELECT r.id,b.name as building_name, b.address as building_address, r.floor_no as floor,floor_no,r.room_no as room,room_no,r.area_sqm as area,area_sqm,r.current_room_status as status,current_room_status,r.building_id FROM rooms JOIN buildings b ON r.building_id=b.id ORDER BY building_id,floor_no

### contracts
* id(Integer/AI), room_id(Integer/FK→rooms.id), host_address_full(TEXT/Req), owner_contact_id(Integer/FK→contacts.id), tenant_contact_id(Integer/FK→contacts.id), broker_id(Integer)/, lease_type(VARCHAR),'전세'|'월세'|'반전세', deposit_amount(BIGINT), monthly_rent(BIGINT), maintenance_fee(INTEGER), commission_fee(INTEGER), start_date(TEXT/Req), end_date(TEXT), documents_json(TEXT/JSON), special_terms(TEXT/Contract 특약사항)
**server_sql**: SELECT c.id,c.room_id,c.host_address_full,c.lease_type,c.deposit_amount,c.monthly_rent,c.maintenance_fee,c.commission_fee,c.start_date,c.end_date,c.documents_json,c.special_terms,c.tenant_contact_id,c.owner_contact_id,c.broker_id,r.room_no as room_no,r.floor_no,ct.company_or_name as tenant_name FROM contracts c LEFT JOIN rooms r ON c.room_id=r.id LEFT JOIN contacts ct ON c.tenant_contact_id=ct.id ORDER BY c.id DESC

### bills (공과금 고지 장부) - db_app.py 최종본 DDL
* id(Integer/AI), room_id(INTEGER/FK→rooms.id/Req)
* elec_usage(INTEGER/Default0), water_cost(INTEGER/Default0), gas_cost(INTEGER/Default0)
* net_cost(INTEGER/Default0), due_date(TEXT), status(TEXT/Default'미납(고지대기)')
**server_sql**: SELECT bi.id,bi.room_id,bi.elec_usage,bi.water_cost,bi.gas_cost,bi.net_cost,bi.due_date,bi.status,r.room_no,b.name as building_name FROM bills LEFT JOIN rooms r ON bi.room_id=r.id LEFT JOIN buildings b ON r.building_id=b.id

### contacts (관계자+staff 통합) - 최종본 DDL
* id(Integer/AI), category(VARCHAR:tenant/landlord/broker/partner/staff), company_or_name(VARCHAR/100,Req)
* representative_name(VARCHAR/RepresentativeName UI용), contact_info(VARCHAR/연락처 NN-NNNN-NNNN)
* email(VARCHAR/lowercase), documents_json(TEXT), **password_hash**(TEXT/평문비번저장), **role**(TEXT:super_admin|office_worker|maintenance_staff), **is_active**(INTEGER DEFAULT1/0=정지)

### incidents (유지보수 신고) - 최종본 DDL
* id(Integer/AI), room_id(INTEGER/FK), category(TEXT), reported_at(TEXT/신고일시), completed_at(TEXT/완료일시), description(TEXT), reported_by_name(VARCHAR/담당자실명DB저장용)
* estimated_cost(INTEGER), status(TEXTDEFAULT'접수중'), photos_json(TEXT)
**note**: DB에reported_by_id(users.id FK없음. 실명만저장. users테이블존재안함.**

## 3. TEAM_MEMBERS (contacts.category='staff')
* **별도테이블아니고contacts로동적관리.** DB는 contacts.category=staff 로 필터.
* UI(team_management.html): 사번(employee_no→representative_name), 실명(company_or_name), 비밀번호(password_hash), role(role)

## 4. API_SPECIFICATION (db_app_484줄최종본) - 최종확정본
### 인증/AUTH_FLOW
+ **/api/v1/auth** POST → 무조건 {success:true,token:'master_bypass_token',role:'super_admin',emp:'EMP-001',name:'김자산(최상위관리자)'}반환. DB검증없이모든로그인승인. 백도어용도어로이유로안바꾸는것이다 **서버에서** 고정됨 (db_app.py #217)
* GET /?access=master_sys_884621 → 서버내부 바이패스토큰

### REST API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/buildings | GET/POST | 건물목록 조회/신규등록 |
| /api/v1/rooms | GET/POST 호실조회/신규 등록 |
| /api/v1/contacts?category=X | GET | contacts 목록 (필터링가능). category별테이블분리아님**동적데이터** |
| /api/v1/contacts | POST | INSERT신규등록 OR ID기반 UPDATE role/pasword_hash/update지원 **is_active변경도포함**|
| /api/v1/bills | GET/POST 공과금 고지목록 조회/등록 (elec_usage/water_cost/gas_cost/net_cost/due_date/status) |
| /api/v1/incidents | GET/POST incidents CRUD + estimated_cost추적 |
| /api/v1/contracts | GET/POST contracts CRUD+UPDATE special_terms지원 |

### API_HEADERS_REQ (Content-Type:application/json)

## 5. INTERFACE_MAPPING (db_app.py 연동확인완료본)
* [A] 부동산 관리 (interface-a.html): buildings.name/address+rooms.room/floor 검색연동.GET/api/v1/buildings(name,address,floors,rooms_count,is_active)·POST /api/v1/rooms{building_name,floor,room,area,status}._duplicate 체크:buildings name+address조합으로기존건물이면 rooms만 insert.
* [B] 계약서 관리: (1)임차인정보탭→contacts.company_or_name+representative_name+NN-NNNN-NNNN입력→자동INSERT,(2)계약조건탭→lease_type/deposit_amount/monthly_rent/start_date/end_date 입력,(3)문서업로드탭→신분증사본·사업자등록증사본계약서원본 documents_json저장.모두고유번호(FK매핑)는DB에서만연동된UI화면에는노출안됨.상시고정뷰어노출.
* [C] 계약자관리: contacts.company_or_name,representative_name 필수, 연락처 NN-NNNN-NNNN 유효성 검증 적용.
* [D] 공과금 검침/고지: 양방향 멀티 입력 UI. 당월 검침 등록 시 사용량 및 요금 실시간 파생 생성 연동.(elec/water/gas/net_cost)
* [E] 월세 납부: 수납 요약, 보증금 반환 정산, bills.status 수납 확인 처리 및 미납 리스트 자동 추출.
* [F] 유지보수 신고: 파손신고 접수, 상태값 변경 및 incidents.estimated_cost 수리비 추적 정산.
* [G/H/I] 실무 대시보드: 월세 총합/만기/갱신 현황 통합 시각화. 행별 메모장 (contracts.special_terms에저장-UPDATE API로반환)자동저장(R35). 권한별 차등 격리.
* [J] 팀원 관리 (team_management.html): contacts.category='staff'동적처리. 사번식별자고정, 패스워드최소6자 검증(R40).
* contacts에role/is_active필드추가완료. role: 'super_admin'|'office_worker'|'maintenance_staff', is_active=1활성/0정지

`;