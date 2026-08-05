# REAL_ESTATE_SYSTEM_SPEC (v2.8 - 2026-08-05 현장운영 보정판)
# 서버: server.py + db.py + routes.py 분할구조 | DB: building_manager.db (SQLite) | 포트: 8899

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
* **auto_extend**(INTEGER DEFAULT 0) — 깔세 자동 연장. 1이면 종료일이 지나도 공실로 세지 않고 이번 기간 종료일을 한 달씩 민다
* **pay_day**(INTEGER DEFAULT 0) — 수납 약정일(1~31). 0=미지정이며 이때는 **계약 시작일과 같은 날**로 본다
* **collect_memo**(TEXT DEFAULT '') — 금일현황의 **수납 통화 메모**. `special_terms`(계약서 특약)와 **다른 칸이다**
* ⚠️ `special_terms` 는 **계약서 화면에서만**, `collect_memo` 는 **금일현황에서만** 쓴다. 섞으면 특약이 덮인다 (10-7)
* ⚠️ 위 두 컬럼의 판정 규칙은 **`guard.js` 한 곳에만** 둔다 (`contractEnd`/`contractAlive`/`contractExtended`/`contractPayDay`/`contractPayDayText`). 화면에 복사 금지
* ⚠️ GET `/api/v1/contracts` 는 `SELECT c.*` 이며 **ORDER BY가 없다.** 화면에서 '첫 번째'를 집으면 옛 계약이 잡힌다 → id로 명시 선택할 것
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
* **구현 현황 (2026-07-23)**: ✅ **파일 단위 롤링 백업 = 구현 완료** — db.py `backup_db()`/`start_auto_backup()`: 서버 시작 시 1회 + 저장/수정(DB mtime 변화) 감지 시 5분마다 `building_manager.db`를 `_backups/auto/db_시각_사유.db`로 SQLite 스냅샷 롤링(최근 30개) 저장. server.py main()에서 호출. ✅ **구현 완료(2026-07-24)**: (1) system_snapshots 테이블, (2) routes.py `_snapshot()` — contacts/contracts UPDATE 직전 자동 행단위 JSON 스냅샷, (4) [K] 되돌리기 UI(auditlog.html) + `POST /api/v1/snapshots/restore` 복구. (GET /api/v1/snapshots 목록)
* **오프사이트 백업 — ✅ 구현(2026-07-24)**: db.py `backup_to_drive()`(드라이브 동기화 폴더 자동탐지/설정파일 drive_backup_path.txt → `<드라이브>/부동산백업`으로 일자별 복사, 앱에 비번 없음) + `backup_to_pc()`(PC 내장드라이브 `~/부동산백업`에 사본 — USB 유실 대비). 폴더 없으면 로컬 백업만.
  - **채택 방식**: 구글 드라이브 데스크톱(동기화 폴더)에 파일 복사. 앱이 `~/내 드라이브/부동산백업/db_YYYYMMDD_HHMM.db`로 통째 복사만 하면 드라이브가 자동 업로드. **OAuth·API키·로그인 코드 불필요.** 사용자는 최초 1회 드라이브 데스크톱 설치·로그인만.
  - **근거**: DB 소용량(~70KB)이라 매 저장/수정마다 통째 복사해도 부담 없음. 롤링 보관(최근 N개).
  - **비채택**: Google Drive API(OAuth) 방식 — 최초 구글 계정 인증 동의 화면이 비전문 사용자에게 마찰. 이 사용자층엔 부적합.
  - **설정값 필요**: 드라이브 동기화 폴더 경로(사용자 환경마다 다름 → 셋업 시 1회 지정/자동탐지), 롤링 보관 개수.
* **현상태 경고**: 현재 DB에 본 테이블 없음 + 저장/수정 시 스냅샷 미생성 → 수정 시 이전 값 복구 불가. 자산가 대상 운영 전 최우선 구현 대상.

## 3. TEAM_MEMBERS (contacts.category='staff')
* **별도테이블아니고contacts로동적관리.** DB는 contacts.category==staff 로 필터.
* UI(team_management.html): 사번(employee_no→representative_name), 실명(company_or_name), 비밀번호(password_hash), role(role)

## 4. API_SPECIFICATION (현재 구현본 기준)
### 인증/AUTH_FLOW (2026-07-23 갱신 — 실제 구현 반영)
* **실제 인증**: /api/v1/auth(/login) POST → routes.py `handle_auth_endpoint`가 contacts에서 사번(representative_name) 조회 후 비밀번호 비교(평문 또는 sha256) → 성공 {status:'success', user, token:'master_sys_884621'}, 실패 401. (구 db_app.py의 "무조건 success" 백도어 서술은 폐기됨 — 현재는 자격증명 검증함)
* **로그인 게이트(guard.js)** — 신규: 모든 콘텐츠 페이지 <head>에 삽입. sessionStorage.loginOk 없으면 index.html(로그인)로 강제 이동; 로그인됐어도 콘텐츠를 단독(top-level)으로 열면 main.html 셸로 복귀. server.py 루트('/')·404 폴백도 index.html로. main.html은 미로그인 시 index.html로 리다이렉트(기존 무조건통과 제거).
* **제작자 백도어 — 제거됨(2026-07-24)**: ?access=master_sys_884621 우회·"관리시스템접속" 링크·creatorBypass 로직 전부 삭제. 이제 정식 로그인만 유효. 마스터 계정 아이디=이메일, 비밀번호는 sha256 해시 저장(평문 없음). 로그인 페이지에 문의 이메일 1줄 표시.

### REST API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/buildings | GET/POST | 건물목록 조회/신규등록 |
| /api/v1/rooms | GET/POST 호실조회/신규 등록 |
| /api/v1/contacts?category=X | GET | contacts 목록 (필터링가능). category별테이블분리아님**동적데이터**|
| /api/v1/contacts | POST | INSERT신규등록 OR ID기반 UPDATE role/pasword_hash/update지원 **is_active변경도제공**|
| /api/v1/bills | GET/POST 공과금 고지목록 조회/등록 (elec_usage/water_cost/gas_cost/net_cost/due_date/status) |
| /api/v1/incidents | GET/POST incidents CRUD + estimated_cost추적 |
| /api/v1/contracts | GET/POST contracts CRUD + `{id,collect_memo}` 수납메모 단독저장 + `{id,special_terms}` 옛화면 안전망

### API_HEADERS_REQ (Content-Type:application/json)

**server.py**: entrypoint(8899)+HTTPServer(ThreadingMixin)
**db.py**: get_db()/init_db_schema()
**routes.py**: handle_get_api()/handle_auth_endpoint()/handle_post_api()

## 5. INTERFACE_MAPPING (연동확인완료본)
* [A] 부동산 관리 (interface-a.html): buildings.name/address+rooms.room/floor 검색연동.GET/api/v1/buildings(name,address,floors,rooms_count,is_active)·POST /api/v1/rooms{building_name,floor,room,area,status}._duplicate 체크:buildings name+address조합으로기존건물이면 rooms만 insert.
* [B] 계약서 관리: (1)임차인정보탭→contacts.company_or_name+representative_name+NN-NNNN-NNNN입력→자동INSERT,(2)계약조건탭→lease_type/deposit_amount/monthly_rent/start_date/end_date 입력,(3)문서업로드탭→신분증사본·사업자등록증사본계약서원본 documents_json저장.모ugo유번호(FK매핑)는DB만연동UI화면엔노출안됨.상시고정뷰어노출.
* [C] 계약자관리: contacts.company_or_name,representative_name 필수, 연락처 NN-NNNN-NNNN 유효성 검증 적용.
* [D] 공과금 검침/고지: 양방향 멀티 입력 UI. 당월 검침 등록 시 사용량 및 요금 실시간 파생 생성 연동.(elec/water/gas/net_cost)
* [E] 월세 납부: 수납 요약, 보증금 반환 정산, bills.status 수납 확인 처리 및 미납 리스트 자동 추출.
* [F] 유지보수 신고: 파손신고 접수, 상태값 변경 및 incidents.estimated_cost 수리비 추적 정산.
* [G/H/I] 실무 대시보드: 월세 총합/만기/갱신 현황 통합 시각화. 행별 메모장 (contracts.**collect_memo**에저장-UPDATE API로반환)자동저장(R35). ⚠️ special_terms(특약)에 쓰지 말 것 → 10-7. 권한별 차등 격리.
* [J] 팀원 관리 (team_management.html): contacts.category'=='staff'동적처리. 사번식별자고정, 패스워드최소6자 검증(R40).
* [L] 협력사 (partner_roster.html): contacts.category in ('partner','broker') 명부 관리.
* [RPT] 금일 관리 현황 (daily_report.html) — 임대인 일일 브리핑/출력물 (2026-07-23 신규, 메뉴 최상단): 상단 카드 4개(이번달 월세 전액수납시·미납·공실·30일내 만기) + 예외 목록 4개(미납·공실·만기임박60일·처리대기 유지보수) + 오늘의 연락 리스트(전화 중복제거). @media print A4 인쇄/PDF 저장 버튼, 별도 라이브러리 없음. rooms/contracts/bills/incidents API 집계. **6장 EXTERNAL_VIEW(옵션 A) 리포트의 "본인 전체용" 구현체.** (임대인별 필터는 6장 TODO)

## 6. EXTERNAL_VIEW (임대인 외부 열람) - ⚠️ 설계확정(옵션 A), 코드 미구현 (2026-07-23)
* **목적**: 직원은 로컬에서 사용(원본), 임대인은 자기 물건 현황을 **열람만**. 수정 전면 불가.
* **채택 방식 = 리포트 전달 (옵션 A)**: 실시간 셀프접속·클라우드 호스팅·계정 전부 없음. 앱이 임대인 요청 시 또는 주기적으로 **읽기전용 리포트**(PDF 또는 데이터가 박힌 자체완결 HTML 파일 1개)를 생성 → 직원이 임대인에게 전달(이메일·메신저·드라이브 링크). **완전 오프라인·USB 배포 대전제 유지.**
* **근거(설계 제1원칙 준수)**: "누구나·어르신도 쉽게". 클라우드 미러/터널(옵션 B/C)은 계정·세팅·인터넷 상시연결이 붙어 대전제·어르신 사용성과 충돌 → 제외.
* **성격**: 임대인이 아무 때나 스스로 접속하는 실시간 셀프열람이 아니라, "최신 리포트를 받아보는" 방식. 소규모·비전문 임대인엔 이걸로 충분.
* **비채택**: (B/C) 클라우드 읽기 미러·서버 터널 — 실시간이나 계정·인터넷 세팅 필요. (D) 포트포워딩+DDNS — 보안·CGNAT.
* **구현 현황(2026-07-23)**: ✅ 본인 전체용 리포트 = daily_report.html([RPT], 5장). ⬜ (4) 전달 자동화 미구현. ❌ (2) 임대인별 소유 물건 필터 = **제외**(2026-07-24, 임대인 1명·프로그램 1개 운영이라 불필요).

## 7. 구현 이력 / 변경 로그 (2026-07-23 작업 세션)
* **로그인 게이트**: guard.js 신규 + 전 콘텐츠 페이지 주입, server.py 루트→index.html, main.html 미로그인 차단. (→4장 AUTH_FLOW)
* **자동 백업(파일 단위)**: db.py backup_db()/start_auto_backup() 구현, `_backups/auto/` 롤링 30개. (→2장 system_snapshots)
* **금일 관리 현황 리포트**: daily_report.html 신규 + auth.js 메뉴 최상단 등록(super_admin·office_worker). (→5장 [RPT])
* **UI 정리**:
  - 계약서(B): 좌상단 안내박스 제거 → 업로드 라벨 옆 "⚠️ 대조확인", 2단 35:65 복원.
  - 하단 흰 뷰어박스 제거(display:none): 월세납부·유지보수·관리비 3화면.
  - body 높이 100vh 통일: interface-a·contract_master가 calc(100vh-64px)라 하단 흰띠 나던 것 교정. 부동산 표 컨테이너 flex:0 1 auto로 빈 박스 제거.
  - 유지보수(F): '연락처(임차인)' 열 추가(계약 조인 tenant_phone, tel:링크), 대상호실 room_id→빌딩명+호실.
  - 월세납부(E): 대상 호실 주소→빌딩명+호실, 열 폭 축소.
* **버그 수정**: auth.js '월세납부' 경로 rent_payment_ledger.html(없음)→monthly_rent_collection.html.
* **더미 데이터(테스트용)**: 건물5·호실10·계약11(전 호실 계약자 연결)·공과금5·유지보수5·직원5·협력사5·임차인13. 옛 더미 이름/전화 정상화.
* **정리/형상관리**: 미사용 파이썬 5개(db_app.py 등) 삭제, 백업파일 `_backups/` 이동, `.gitignore` 추가. Git 커밋 + GitHub push 완료(origin/main).
* **✅ 완료(2026-07-24)**: ① 수납 장부 = payments 테이블 + GET/POST /api/v1/payments + 월세납부(E) 연동 + 금일현황 "수납률/월세미납" 반영. ② 행단위 스냅샷/되돌리기 = system_snapshots + 수정 전 자동 스냅샷 + [K] 되돌리기(auditlog.html).
* **미구현 잔여**: (설계 항목 완료.)
* **✅ 완료(2026-07-24 추가분)**: ① 구 자격증명 문구 삭제 — server.py 시작 콘솔 + team_management.html 안내박스에서 "EMP-001/admin123" 제거. ② 계약서(B) **임차인 신분증(앞면) 사본 저장** — tenantIdFront 업로드 → documents_json.tenant_id_front 보관.
* **후순위(남음)**: 리포트 전달 자동화, 전기요금 자동계산(한전 요금표).

## 8. v1 현장배포 준비 (2026-07-25~29)
### 화면 개편
* **[B] 계약서**: OCR 제거 → 원본 뷰어 전용 / 임대인 입력란 삭제 / 업로드 2칸(계약서·신분증) 좌우배치·다중업로드 / 뷰어 전환버튼 + ◀▶ / 특약을 우측 상단 가로전체(3줄) / **부가세 체크박스**(documents_json.vat_applied) / 소재지 호실연동 자동입력 / **보증금·월차임 만원 단위 입력(저장 시 ×10,000)**
* **[A] 부동산**: 목록 행 클릭 → 좌측 폼 자동채움·수정 / 상태 입력칸 추가 / 호실·건물 **수정 API 신설**
* **[C] 계약자**: **명세서 출력**(월세+공과금 합계 A4 인쇄/PDF)
* **[D] 공과금**: 전기 **금액칸 신설**(검침·금액 중 하나만 있어도 저장) / **공용부 등록**(건물+구역) / 우측 검색창(440→4층 전체) / **일괄 저장** / **수정 지원**
* **[E] 월세납부**: 계약서 부가세 설정 자동반영 / 호실 검색방식
* **[F] 유지보수**: 공용부 신고 / 호실 검색방식
* **[J] 팀원관리**: **직원정보 수정 기능** / 마스터 숨김 · 비번 마스킹
* **[L] 협력사**: 계좌번호 필드
* 호실 선택 UI 통일: 드롭다운(74개) → **번호 입력 + 같은 층 버튼**(440 입력 시 4층 전체)

### 인증·서버
* **직원 로그인 버그 수정**(쿼리의 `OR id=999`로 항상 마스터가 잡히던 문제) / 비활성 계정 차단
* 로그인 **엔터키**, **접속주소 자동표시**(/api/v1/serverinfo)
* 정적파일 **절대경로 + URL 인코딩**(한글·공백 파일명 원본 표시 문제 해결)
* 포트 재사용(allow_reuse_address)·점유 시 안내 종료·종료 시 포트 반납

### DB 추가
* `bills`: elec_cost, building_id, scope('room'|'common'), common_area
* `incidents`: building_id, scope, common_area
* `contacts`: account_no

### 백업 3중화
* `_backups/auto`(5분·30개) + `_backups/daily`(하루1개·30일) + **PC 내장드라이브 `~/부동산백업`**(USB 유실 대비) + 구글드라이브 폴더(선택, 인증정보 저장 안 함)

### 배포 패키징
* `build_windows.bat`: py 3.13 우선, **DLL 자동 포함**, 필요한 파일만 선별 복사
* **`install_service.bat`**(현장 1회): 관리자 자동승격 → 옛 방화벽 규칙 삭제 → **모든 프로필 허용** → 부팅 자동실행 → **절전 해제**
  - "인증창 뜬 한 번만 접속되고 이후 차단" 원인 = 개인 프로필로만 허용된 규칙 → profile=any 재등록으로 해결
* **`필독_사용안내.txt`**: 비전문가 기준 안내문(전문용어 배제)

### 초기 데이터
* **`seed_daerim.py`**: 대림빌딩(영등포구 도림로 140) **74호실** 등록. 재실행 안전(중복 방지)
  - B2·B1 각1 / 1~3층 각3 / 4~7층 각10 / 8층 11(880~889+800) / 9층 11(990~999+900) / 10층 1000(사옥)
  - 단독층 사용: 대표호실 '임대중(단독층)', 나머지 '단독층 통합' (1층만 개별 사용)
* **제외 결정(2026-07-24)**: ③ 임대인별 리포트 필터 = 불필요. 임대인 1명이 프로그램 1개를 운영하는 형태라 필터가 무의미 → 금일현황은 "본인 전체용" 그대로 유지.
* **✅ 완료(원래 잔여 중)**: 제작자 백도어 제거 / 오프사이트 백업(구글드라이브 폴더 + PC 내장드라이브 사본 + 일자별) / 로그인 게이트 / 자동 백업 / 금일현황 리포트 / 관리자 계정 해시화.

## 9. 운영 안정화 (2026-07-29~30) — v2.5 / v2.6

### 9-1. 수정(편집) 기능 전면 도입 + 진입점 노출
* 기존엔 **부동산 외 화면에 수정 수단이 없었음** → 전 화면에 **눈에 보이는 [✏️ 수정] 버튼** 배치.
| 화면 | 진입점 |
|---|---|
| 부동산 | 목록 [✏️ 수정] · 좌측 검색 후 불러오기 |
| 계약서 | 호실 선택 시 [✏️ 불러와 수정하기] 배너 |
| 계약자 | 목록 [수정] → 계약서로 이동(`contract_master.html?id=N`) |
| 공과금 | 저장된 호실 [수정] (기존값 자동 표시) |
| 월세납부 | 목록 [✏️ 수납수정] · 당월 기록 있으면 자동 수정모드 |
| 유지보수 | 목록 [✏️ 수정] |
| 팀원관리 | 목록 [✏️ 수정] (비번 비우면 기존 유지) |
| 협력사 | 목록 [수정] |
* **신규 수정 API**: rooms / buildings / bills / incidents / payments (contracts·contacts는 기존). 전부 **수정 전 자동 스냅샷** → [K] 되돌리기 가능.

### 9-2. 작업 기록(감사로그)
* `audit_logs` 재정비(actor/action/target/detail/created_at) + `GET /api/v1/auditlogs`(`?date=YYYY-MM-DD`, `?date=dates`).
* `guard.js`가 모든 POST에 로그인 사용자(`_actor`) 자동 첨부 → 화면 수정 없이 전 기능 기록.
* **팀원관리 우측 [📜 작업 기록] 탭** — 날짜 선택(건수 표시) + 검색. **로그는 삭제하지 않고 날짜별 누적 보관**.

### 9-3. 데이터 정합성 (중요 버그 수정)
* **계약↔계약자 미연동**: 계약서의 임차인 이름/연락처가 `documents_json`에만 저장돼 계약자 명부가 비어 보임 → 서버 `_resolve_tenant()`가 contacts(tenant)를 **찾거나 생성해 tenant_contact_id 연결**. 수정 시 연락처 갱신, 중복 생성 없음.
* **호실 중복 등록**: 같은 건물+호실번호 재등록 가능했음 → **409 차단** + 해당 호실을 폼에 자동 로드.
* **계약 중복 생성**: 한 호실에 계약 여러 건 생성 가능했음 → 진행 중 계약이 있으면 **409 차단**, "불러와 수정" 확인창. (만료 후에는 신규 등록 허용)
* **공실 오집계**: 계약해도 호실 상태가 '공실'로 남음 → 계약 시 `_mark_room_leased()`로 자동 '임대'. 금일현황은 **유효 계약 기준**으로 재판정.
* **호실 상태 3분류 확정**: `공실 / 임대 / 공사중` (select). 기존값(임대중(단독층)·단독층 통합·사옥) 9건은 '임대'로 마이그레이션. 편집 시 미등록 값은 "(기존값)" 옵션으로 보존.

### 9-4. 화면 연동 정상화
* **통합대시보드**: 부가세를 무조건 10% 계산하던 것 → **계약의 vat_applied 반영**(미적용 시 '면제' 표기). 가짜 고정 공과금·가짜 전화번호(010-1234-5678) 제거 → 실제 bills·임차인 연락처 사용.
* **월세납부**: 우측 표가 **항상 '완납'** 하드코딩 → 당월 payments 기준 실제 상태(완납/일부미납/미납) 색상 표기, 기록 없으면 '미납'. 공과금 입력칸 자동값(120000/45200…) **전부 0**으로 변경 후, 호실 선택 시 **검침 화면에서 입력한 bills 자동 반영**. 정산 유형에 **미납(연체료 면제)·미납** 추가, 선택 시 버튼이 🔴 미납 기록 저장으로 전환.

### 9-5. 호실 선택 UI 통일
* 전 화면 드롭다운(74개) 제거 → **번호 입력 + 같은 층 버튼**(440 → 4층 전체, `4`·`B1`·`1000` 인식).
* 적용: 계약서 · 공과금(좌/우 연동, 우측 검색창 신설·'앞 10개 고정' 버그 제거) · 월세납부 · 유지보수 · 부동산(좌측 검색 신설, 우측 즉시 필터).

### 9-6. 금일현황(RPT) 프린트 최적화
* 카드·제목·표 폰트 축소, **오늘의 연락 리스트 삭제**(미납/만기 표에 연락처 중복).
* 공실 목록을 **건물별 묶음 + 층별 호실 한 줄**로 압축(65줄 → 7줄). 지하는 '지하 1층/2층' 빨간 표기·최상단 정렬. 면적·상태 열 제거.

### 9-7. 기타
* 공용부(복도·공동화장실) 비용/유지보수 등록: `scope`('room'|'common')·`building_id`·`common_area`.
* 관리자 비밀번호 재변경(sha256), 직원 계정 추가(사번 121 · 손승연 · office_worker).
* `build_windows.bat` 한글 파일명으로 인한 실행 오류 → `copy *.txt` 방식으로 수정(순수 ASCII 유지).
* 노션에 **터미널 명령어 모음 / 폴더 구조 메모** 페이지 작성.

## 10. 현장 운영 보정 (2026-08-01 ~ 08-05) — v2.8

### 10-1. 깔세 '자동 연장' (2026-08-01)
* 깔세는 매달 내면서 나갈 때까지 사는 계약인데, 정부가 달 단위 계약을 인정하지 않아
  **계약서에는 1년·2년으로 적고 실제로는 달마다 받는다.** 그래서 프로그램이 만기로 보고 공실로 셌다.
* `contracts.auto_extend` 신설 + 계약 화면 **[자동 연장]** 체크박스.
* **이번 기간 종료일 = 시작일 + n개월 − 1일.** 자동 연장은 **한 달씩** 민다.
  종료일이 아니라 **시작일 기준**이어야 월말 계약(1월 31일 시작 등)이 하루씩 밀리지 않는다.
* 깔세 11건(444·449·552·555·660·661·666·668·778·779·882) 적용 → 공실 38→**27실**, 만료 11→**0건**.

### 10-2. 휴대폰 화면 / PWA (2026-08-01)
* `mobile.html`(보기 전용) + `manifest.json` + 아이콘 3종. 홈 화면 아이콘으로 실행.
* 좁은 화면으로 로그인하면 자동 전환. `?pc=1` 평소 화면, `?m=1` 컴퓨터에서도 휴대폰 화면.
* 휴대폰만 로그인 **30일** 기억(컴퓨터·서류창은 12시간 유지). 보기 전용 + Tailscale 내부 주소라 허용.

### 10-3. 수납 약정일 (2026-08-05)
* 전 화면에 `매월 15일`이 **글자로 박혀** 있었고 계약서에 고칠 칸조차 없었다.
* `contracts.pay_day` 신설 + 계약 화면 **[수납 약정일]** 칸.
* 기준은 **계약 시작일과 같은 날**. 이래야 '이번 기간 종료일'이 다음 납입일 바로 전날이 되어 10-1과 맞는다.
* 비우면 0 저장 → 시작일 기준. **기존 계약 43건은 손댈 필요 없음.**
* 반영: 통합 대시보드 `약정일`, 월세납부 `수납 약정일`(표 제목 '약정 약정일' 오타 정정).

### 10-4. 데이터 정합성 (2026-08-05)
* **공과금 0원 수정 불가** — 기존값 채우기에 `ex[n] ? ex[n] : ''` 를 써서 **JS가 숫자 0을 거짓으로** 봤다.
  0원을 저장해도 다시 열면 빈칸 → 네 칸이 다 비면 "이 줄은 비어 있습니다"로 저장 거부.
  0원은 실제 값이다(공실·한전 단독계약). 빈칸과 0을 구분하도록 수정. 합계칸도 0 표시.
* **금일현황이 되돌린 값을 반영 못함** — 되돌리기(스냅샷 복구)는 정상. 원인은 표시 쪽이었다.
  검침할 때마다 고지 줄이 새로 생기는데 미납 목록에 **전부** 올려서, 한 줄을 고치거나 되돌려도
  **옛 줄이 남아 이전 값이 계속 보였다.** 미납 **132건 → 66건**(중복 66곳 제거).
  → 호실별(공용부는 건물+구역별) **최신 1건**만 본다.
* **금일현황 임차인·연락처가 '먼저 나온 계약'** 이었다 → 방을 옮긴 이력이 있으면 **나간 세입자**가 잡힐 수 있었다.
  → 가장 최근 계약(id 최대)으로. `/api/v1/contracts` 에 ORDER BY가 없어 순서를 믿으면 안 된다.

### 10-5. 부가세 — 자동 계산하지 말 것 (2026-08-05 확인)
* 기본 규칙은 **관리비 × 10%** 지만 **가구마다 다르다.**
  월세에 관리비가 포함된 가구, 부가세가 포함된 가구가 있고 **세금 환급을 받는 가구만 부가세를 따로** 받는다.
* → **월세납부 화면 좌측 폼의 계산을 고치지 말 것.** `부가세 적용`·`월세`·`관리비` 체크박스와
  금액칸으로 **직원이 가구별로 정한다.** 우측 목록의 `(월세+관리비)×10%` 는 수납 전 **어림값**이다.
* 화면 하나만 보고 "이중청구 버그"로 판단한 오판이 있었다. 반복 금지.

### 10-6. 형상·운영
* `building_manager.db` 를 git 추적에서 제외 — `git pull` 이 현장 실데이터를 덮어쓰던 사고 방지.
  **배포는 rsync 로만** (CLAUDE.md 3-1의 제외 목록을 하나도 빼지 말 것).
* 승인 규칙(.claude/settings.local.json) 38개 → **5개**. 임의 파이썬 실행·SSH 비밀키 읽기·
  현장 DB 덮어쓰기 rsync 는 **일부러 제외**(확인 없이 나가면 안 되는 것들).
* ⚠️ **API 시험을 실제 DB에 대고 하지 말 것.** POST 본문에 없는 항목은 빈 값으로 덮인다.
  계약 1건(554호)의 주소·관리비·첨부·특약이 날아간 적 있다(복구 완료). 시험은 **DB 사본**에서.

### 10-7. 특약과 수납 메모 분리 (2026-08-05)
* 계약서 **특약**과 금일현황 **수납 통화 메모**가 `contracts.special_terms` **한 칸을 공유**하고 있었다.
  금일현황 메모칸은 `onchange` 로 `{id, special_terms}` 를 보내 그 칸을 통째로 덮어썼다.
  → 금일현황에 "오후 3시 입금 확약" 한 줄만 적어도 **계약서 특약이 전부 사라진다.**
* 여태 안 터진 이유는 특약이 실제로 들어간 계약이 없었기 때문. 885호 신규 계약(특약 6개 항목)이
  들어오면서 즉시 위험해졌다. **부동산 계약은 특약이 없는 경우가 거의 없다.**
* 조치 — `contracts.collect_memo` 신설로 완전 분리.

| 칸 | 뜻 | 쓰는 화면 | 보내는 키 |
|---|---|---|---|
| `special_terms` | 계약서에 적힌 특약 (textarea, 여러 줄) | 계약서 관리 | 계약 전체 payload |
| `collect_memo` | 그날의 수납 통화 메모 (한 줄) | 금일현황 | `{id, collect_memo}` |

* 금일현황 메모칸에 마우스를 올리면 그 계약의 **특약을 읽기 전용 말풍선**으로 보여준다(수정은 불가).
* ⚠️ routes.py 의 `{id, special_terms}` **안전망 갈래를 지우지 말 것.** 옛 화면이 브라우저 캐시에
  남아 그 형태로 보내면, 갈래가 없을 때 전체 UPDATE로 떨어져 **계약서가 통째로 비워진다.**
* 검증: DB 사본 샌드박스(포트 8977)에서 6개 항목 전수 통과 — 메모 저장·삭제 시 특약 보존,
  옛 화면 안전망, 계약 전체 수정 시 메모 보존, 목록 API 양쪽 노출, 기존 43건 무영향.
