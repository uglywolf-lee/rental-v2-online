# REAL_ESTATE_SYSTEM_SPEC (v2.0 - 2026-07-23 최종확정본)
# 서버: server.py + db.py + routes.py 분할구조 | DB: building_manager.db (SQLite)

## ★ 설계 제1원칙 (2026-07-23 확정) — 모든 결정의 최상위 기준
* **"누구나·어르신도 쉽게"**: 할아버지·할머니가 그냥 쓸 수 있는 관리프로그램이 최상위 목표. 이하 모든 설계·구현 결정은 이 원칙에 종속된다.
  - **오프라인·USB 배포**: 인터넷 설정·계정가입 없이 USB로 건네 바로 사용.
  - **자동**: 백업·복구 등은 사용자가 신경 쓰지 않아도 앱이 알아서 처리.
  - **단순**: 큰 글씨, 버튼 최소, 한 화면에 한 가지, 선택지 적게.
  - **비파괴**: 초기화·전체삭제 버튼 없음. 실수해도 데이터가 날아가지 않음(R3 소프트삭제 + 자동 스냅샷).
  - **기술 비노출**: 서버·클라우드·API 같은 개념을 사용자에게 드러내지 않는다.

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

## 2. DATABASE_SCHEMA (현재 db_app.py 기반)
### buildings
* id(Integer/_PK/AI), name(VARCHAR,Req), address(VARCHAR,500,Req), floors(INTEGER), rooms_count(INTEGER), is_active(BIT/1,Default)
**server_sql**: SELECT id,name,address,floors,rooms_count,is_active FROM buildings WHERE is_active=1 ORDER BY id

### rooms
* id(Integer/AI), building_id(Integer/FK→buildings.id), floor_no(INTEGER), room_no(VARCHAR,50), area_sqm(REAL), current_room_status(VARCHAR)
**server_sql**: SELECT r.id,b.name as building_name, b.address as building_address, r.floor_no as floor,floor_no,r.room_no as room,room_no,r.area_sqm as area,area_sqm,r.current_room_status as status,current_room_status,r.building_id FROM rooms JOIN buildings b ON r.building_id=b.id ORDER BY building_id,floor_no

### contracts
* id(Integer/AI), room_id(Integer/FK→rooms.id), host_address_full(TEXT/Req), owner_contact_id(Integer/FK→contacts.id), tenant_contact_id(Integer/FK→contacts.id), broker_id(Integer)/, lease_type(VARCHAR),'전세'|'월세'|'반전세', deposit_amount(BIGINT), monthly_rent(BIGINT), maintenance_fee(INTEGER), commission_fee(INTEGER), start_date(TEXT/Req), end_date(TEXT), documents_json(TEXT/JSON), special_terms(TEXT/Contract 특약사항)
**server_sql**: SELECT c.id,c.room_id,c.host_address_full,c.lease_type,c.deposit_amount,c.monthly_rent,c.maintenance_fee,c.commission_fee,c.start_date,c.end_date,c.documents_json,c.special_terms,c.tenant_contact_id,c.owner_contact_id,c.broker_id,r.room_no as room_no,r.floor_no,ct.company_or_name as tenant_name FROM contracts c LEFT JOIN rooms r ON c.room_id=r.id LEFT JOIN contacts ct ON c.tenant_contact_id=ct.id ORDER BY c.id DESC

### bills (공과금 고지 장부) - 현재 DDL
* id(Integer/AI), room_id(INTEGER/FK→rooms.id/Req)
* elec_usage(INTEGER/Default0), water_cost(INTEGER/Default0), gas_cost(INTEGER/Default0)
* net_cost(INTEGER/Default0), due_date(TEXT), status(TEXT/Default'미납(고지대기)')
**server_sql**: SELECT bi.id,bi.room_id,bi.elec_usage,bi.water_cost,bi.gas_cost,bi.net_cost,bi.due_date,bi.status,r.room_no,b.name as building_name FROM bills LEFT JOIN rooms r ON bi.room_id=r.id LEFT JOIN buildings b ON r.building_id=b.id

### contacts (관계자+staff 통합) - 현재 DDL
* id(Integer/AI), category(VARCHAR:tenant/landlord/broker/partner/staff), company_or_name(VARCHAR/100,Req)
* representative_name(VARCHAR/RepresentativeName UI용), contact_info(VARCHAR/연락처 NN-NNNN-NNNN)
* email(VARCHAR/lowercase), documents_json(TEXT), **password_hash**(TEXT/평문비번저장), **role**(TEXT:super_admin|office_worker|maintenance_staff), **is_active**(INTEGER DEFAULT1/0=정지)

### incidents (유지보수 신고) - 현재 DDL
* id(Integer/AI), room_id(INTEGER/FK), category(TEXT), reported_at(TEXT/신고일시), completed_at(TEXT/완료일시), description(TEXT), reported_by_name(VARCHAR/담당자실명DB저장용)
* estimated_cost(INTEGER), status(TEXTDEFAULT'접수중'), photos_json(TEXT)

### system_snapshots (자동 백업/롤백) - ⚠️ 설계확정, 코드 미구현 (2026-07-23 확인)
* id(Integer/AI), snapshot_type(VARCHAR50: 'full_backup'|'contract_undo'|'auto_snapshot'), table_name(TEXT/대상테이블), target_id(INTEGER/대상 행 ID), data_snapshot_json(TEXT/JSON: 변경 전 원본 통째 저장), requested_by_id(INTEGER/FK→users.id), is_restored(BIT/0:미회복 1:복구완료), created_at(TEXT)
* **규칙(R19/R20/R23)**: contacts/bills/contracts/rooms 등 핵심데이터 INSERT아닌 UPDATE·비활성화 직전, 변경 전 행을 data_snapshot_json에 자동 스냅샷 → 실수 시 재INSERT/UPDATE로 1초 복구
* **구현 필요분(TODO)**: (1) db.py에 위 테이블 CREATE 추가, (2) routes.py의 모든 UPDATE/is_active=0 직전 스냅샷 저장 로직 삽입, (3) 서버 시작 시 building_manager.db 파일 단위 롤링 백업(재해 대비, 행 스냅샷과 별개), (4) 인터페이스 [K] 복구 UI(비전문 사용자용 "되돌리기" 단일 버튼)
* **오프사이트 백업 = 구글 드라이브 (설계확정, 미구현)**: 대상 사용자(자산가) 본인 구글 드라이브에 DB 사본 자동 백업.
  - **채택 방식**: 구글 드라이브 데스크톱(동기화 폴더)에 파일 복사. 앱이 `~/내 드라이브/부동산백업/db_YYYYMMDD_HHMM.db`로 통째 복사만 하면 드라이브가 자동 업로드. **OAuth·API키·로그인 코드 불필요.** 사용자는 최초 1회 드라이브 데스크톱 설치·로그인만.
  - **근거**: DB 소용량(~70KB)이라 매 저장/수정마다 통째 복사해도 부담 없음. 롤링 보관(최근 N개).
  - **비채택**: Google Drive API(OAuth) 방식 — 최초 구글 계정 인증 동의 화면이 비전문 사용자에게 마찰. 이 사용자층엔 부적합.
  - **설정값 필요**: 드라이브 동기화 폴더 경로(사용자 환경마다 다름 → 셋업 시 1회 지정/자동탐지), 롤링 보관 개수.
* **현상태 경고**: 현재 DB에 본 테이블 없음 + 저장/수정 시 스냅샷 미생성 → 수정 시 이전 값 복구 불가. 자산가 대상 운영 전 최우선 구현 대상.

## 3. TEAM_MEMBERS (contacts.category='staff')
* **별도테이블아니고contacts로동적관리.** DB는 contacts.category==staff 로 필터.
* UI(team_management.html): 사번(employee_no→representative_name), 실명(company_or_name), 비밀번호(password_hash), role(role)

## 4. API_SPECIFICATION (현재 구현본 기준)
### 인증/AUTH_FLOW
+ **/api/v1/auth** POST → 무조건 {success:true,token:'master_bypass_token',role:'super_admin',emp:'EMP-001',name:'김자산(최상위관리자)'}반환. DB검증없이모든로그인승인. 백도어용도로이유로안바꾸는것이다 **서버에서** 고정됨 (db_app.py #217)
* GET /?access=master_bypass_token → 서버내부 바이패스토큰

### REST API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/buildings | GET/POST | 건물목록 조회/신규등록 |
| /api/v1/rooms | GET/POST 호실조회/신규 등록 |
| /api/v1/contacts?category=X | GET | contacts 목록 (필터링가능). category별테이블분리아님**동적데이터**|
| /api/v1/contacts | POST | INSERT신규등록 OR ID기반 UPDATE role/pasword_hash/update지원 **is_active변경도제공**|
| /api/v1/bills | GET/POST 공과금 고지목록 조회/등록 (elec_usage/water_cost/gas_cost/net_cost/due_date/status) |
| /api/v1/incidents | GET/POST incidents CRUD + estimated_cost추적 |
| /api/v1/contracts | GET/POST contracts CRUD+UPDATE special_terms지원

### API_HEADERS_REQ (Content-Type:application/json)

**server.py**: entrypoint(8080)+HTTPServer(ThreadingMixin)
**db.py**: get_db()/init_db_schema()
**routes.py**: handle_get_api()/handle_auth_endpoint()/handle_post_api()

## 5. INTERFACE_MAPPING (연동확인완료본)
* [A] 부동산 관리 (interface-a.html): buildings.name/address+rooms.room/floor 검색연동.GET/api/v1/buildings(name,address,floors,rooms_count,is_active)·POST /api/v1/rooms{building_name,floor,room,area,status}._duplicate 체크:buildings name+address조합으로기존건물이면 rooms만 insert.
* [B] 계약서 관리: (1)임차인정보탭→contacts.company_or_name+representative_name+NN-NNNN-NNNN입력→자동INSERT,(2)계약조건탭→lease_type/deposit_amount/monthly_rent/start_date/end_date 입력,(3)문서업로드탭→신분증사본·사업자등록증사본계약서원본 documents_json저장.모ugo유번호(FK매핑)는DB만연동UI화면엔노출안됨.상시고정뷰어노출.
* [C] 계약자관리: contacts.company_or_name,representative_name 필수, 연락처 NN-NNNN-NNNN 유효성 검증 적용.
* [D] 공과금 검침/고지: 양방향 멀티 입력 UI. 당월 검침 등록 시 사용량 및 요금 실시간 파생 생성 연동.(elec/water/gas/net_cost)
* [E] 월세 납부: 수납 요약, 보증금 반환 정산, bills.status 수납 확인 처리 및 미납 리스트 자동 추출.
* [F] 유지보수 신고: 파손신고 접수, 상태값 변경 및 incidents.estimated_cost 수리비 추적 정산.
* [G/H/I] 실무 대시보드: 월세 총합/만기/갱신 현황 통합 시각화. 행별 메모장 (contracts.special_terms에저장-UPDATE API로반환)자동저장(R35). 권한별 차등 격리.
* [J] 팀원 관리 (team_management.html): contacts.category'=='staff'동적처리. 사번식별자고정, 패스워드최소6자 검증(R40).

## 6. EXTERNAL_VIEW (임대인 외부 열람) - ⚠️ 설계확정(옵션 A), 코드 미구현 (2026-07-23)
* **목적**: 직원은 로컬에서 사용(원본), 임대인은 자기 물건 현황을 **열람만**. 수정 전면 불가.
* **채택 방식 = 리포트 전달 (옵션 A)**: 실시간 셀프접속·클라우드 호스팅·계정 전부 없음. 앱이 임대인 요청 시 또는 주기적으로 **읽기전용 리포트**(PDF 또는 데이터가 박힌 자체완결 HTML 파일 1개)를 생성 → 직원이 임대인에게 전달(이메일·메신저·드라이브 링크). **완전 오프라인·USB 배포 대전제 유지.**
* **근거(설계 제1원칙 준수)**: "누구나·어르신도 쉽게". 클라우드 미러/터널(옵션 B/C)은 계정·세팅·인터넷 상시연결이 붙어 대전제·어르신 사용성과 충돌 → 제외.
* **성격**: 임대인이 아무 때나 스스로 접속하는 실시간 셀프열람이 아니라, "최신 리포트를 받아보는" 방식. 소규모·비전문 임대인엔 이걸로 충분.
* **비채택**: (B/C) 클라우드 읽기 미러·서버 터널 — 실시간이나 계정·인터넷 세팅 필요. (D) 포트포워딩+DDNS — 보안·CGNAT.
* **구현 필요분(TODO)**: (1) 기존 화면 데이터를 담은 읽기전용 리포트 생성기(PDF 또는 자체완결 HTML 1파일), (2) 임대인별 소유 물건 필터, (3) 리포트에 생성 시각 표기, (4) 전달은 직원이 익숙한 채널(이메일/메신저) 수동 — 자동화는 후순위.
