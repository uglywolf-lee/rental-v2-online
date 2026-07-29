window.REAL_ESTATE_SYSTEM_SPEC = `
# REAL_ESTATE_SYSTEM_SPEC (v2.4 - 2026-07-29 현장배포판 / 계약서개편·공용부·검색UI·패키징 반영본)
# 서버 포트: 8899 (기존 8080에서 변경)
# 서버: server.py(엔트리/정적서빙/업로드) + routes.py(API라우팅) + db.py(DB스키마) | DB: building_manager.db (SQLite)
# (주: v2.0 문서상 'db_app.py' 명칭 → 실제 구현은 server.py/routes.py/db.py 로 분리 운영)

## 0. GLOBAL_STANDARDS
* AUTH: 모든 접근은 /api/v1/ 라우팅으로 통일
* DATETIME: DB=TEXT('YYYY-MM-DD HH:MM:SS') | UI표시=TEXT('YYYY-MM-DD') | UI입력=숫자8자리(YYYYMMDD) — 공용모듈 date8.js 가 8자리로 입력받아 저장 시 'YYYY-MM-DD'로 변환
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
**node**: DB에reported_by_id(users.id FK없음. 실명만저장. users테이블존재안함.**

## 3. TEAM_MEMBERS (contacts.category='staff')
* **별도테이블아니고contacts로동적관리.** DB는 contacts.category==staff 로 필터.
* UI(team_management.html): 사번(employee_no→representative_name), 실명(company_or_name), 비밀번호(password_hash), role(role)

## 4. API_SPECIFICATION (db_app_484줄최종본) - 최종확정본
### 인증/AUTH_FLOW (2026-07-23 패치)
+ **로그인 엔드포인트**: POST /api/v1/auth/login {emp, password} (프론트 index.html 연동). 별칭 경로 /api/v1/login, /api/v1/auth 도 동일 처리.
+ **응답형식**: 성공 {status:'success', user:{employee_no,name,role}, token} / 실패 {status:'error', message}. 클라이언트는 user.role 로 권한 판정.
+ **비밀번호 검증 적용**: 마스터 계정 포함 저장된 password_hash 와 일치해야 로그인 성공 (이전의 '무조건 승인' 및 db_pw=='admin123' 무조건통과 로직 제거).
* URL 바이패스 = **제거됨(2026-07-24)**: 기존 ?access=master_sys_884621 우회 경로·"관리시스템접속" 링크·creatorBypass/제작자모드 배지 로직 전부 삭제. 이제 정식 로그인만 유효.
* 마스터 계정(2026-07-24 변경): 아이디=이메일(representative_name), 비밀번호는 **sha256 해시로만 저장**(소스·DB 어디에도 평문 없음). db.py init_db_schema 가 id=999에 강제 보장.
+ **로그인 게이트(guard.js, 2026-07-23 신규)**: 모든 콘텐츠 페이지 <head>에 삽입. sessionStorage.loginOk 없으면 index.html로 강제이동, 로그인됐어도 콘텐츠를 단독(top-level)으로 열면 main.html 셸로 복귀. server.py 루트('/')·404 폴백을 index.html(로그인)으로 변경, main.html 미로그인 차단(기존 무조건통과 제거).

### REST API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/buildings | GET/POST | 건물목록 조회/신규등록 |
| /api/v1/rooms | GET/POST 호실조회/신규 등록 |
| /api/v1/contacts?category=X | GET | contacts 목록 (필터링가능). category별테이블분리아님**동적데이터**|
| /api/v1/contacts | POST | INSERT신규등록 OR ID기반 UPDATE role/pasword_hash/update지원 **is_active변경도제공**|
| /api/v1/bills | GET/POST 공과금 고지목록 조회/등록 (elec_usage/water_cost/gas_cost/net_cost/due_date/status) |
| /api/v1/incidents | GET/POST incidents CRUD + estimated_cost추적 |
| /api/v1/contracts | GET/POST contracts CRUD+UPDATE special_terms지원 |
| /api/v1/auth/login | POST | 로그인 검증 {emp,password}. 별칭 /api/v1/login · /api/v1/auth |
| /api/v1/upload | POST | 파일 업로드(헤더 X-File-Name, body=바이너리). 종류별 저장구역 분류 후 {filepath,filename,category} 반환 |
| /api/v1/ocr | POST | 업로드 문서 OCR 필드 추정 {filepath,doc_type} → {engine,fields,confidence,raw_text,warnings}. 사람 검토 전제 |

### API_HEADERS_REQ (Content-Type:application/json) 

## 5. INTERFACE_MAPPING (db_app.py 연동확인완료본)
* [A] 부동산 관리 (interface-a.html): buildings.name/address+rooms.room/floor 검색연동.GET/api/v1/buildings(name,address,floors,rooms_count,is_active)·POST /api/v1/rooms{building_name,floor,room,area,status}._duplicate 체크:buildings name+address조합으로기존건물이면 rooms만 insert.
* [B] 계약서 관리: (1)임차인정보탭→contacts.company_or_name+representative_name+NN-NNNN-NNNN입력→자동INSERT,(2)계약조건탭→lease_type/deposit_amount/monthly_rent/start_date/end_date 입력,(3)문서업로드탭→신분증사본·사업자등록증사본계약서원본 documents_json저장.모두고유번호(FK매핑)는DB에서만연동된UI화면에는노출안됨.상시고정뷰어노출.
* [C] 계약자관리: contacts.company_or_name,representative_name 필수, 연락처 NN-NNNN-NNNN 유효성 검증 적용.
* [D] 공과금 검침/고지: 양방향 멀티 입력 UI. 당월 검침 등록 시 사용량 및 요금 실시간 파생 생성 연동.(elec/water/gas/net_cost)
* [E] 월세 납부: 수납 요약, 보증금 반환 정산, bills.status 수납 확인 처리 및 미납 리스트 자동 추출.
* [F] 유지보수 신고: 파손신고 접수, 상태값 변경 및 incidents.estimated_cost 수리비 추적 정산.
* [G/H/I] 실무 대시보드: 월세 총합/만기/갱신 현황 통합 시각화. 행별 메모장 (contracts.special_terms에저장-UPDATE API로반환)자동저장(R35). 권한별 차등 격리.
* [J] 팀원 관리 (team_management.html): contacts.category=='staff'동적처리. 사번식별자고정, 패스워드최소6자 검증(R40).
* [L] 협력사 (partner_roster.html): contacts.category in ('partner','broker') 명부 관리.
* [RPT] 금일 관리 현황 (daily_report.html) — 임대인 일일 브리핑/출력물(2026-07-23 신규, 메뉴 최상단): 카드4(이번달월세 전액수납시·미납·공실·30일내만기)+예외목록4(미납·공실·만기임박60일·처리대기 유지보수)+오늘의 연락리스트(전화 중복제거). @media print A4 인쇄/PDF 저장버튼, 외부 라이브러리 없음. rooms/contracts/bills/incidents API 집계. 6장 임대인리포트(옵션A)의 '본인 전체용' 구현체.
* contacts에role/is_active필드추가완료. role: 'super_admin'|'office_worker'|'maintenance_staff', is_active=1활성/0정지

## 6. FILE_STORAGE (업로드 저장구역) - 2026-07-23 추가
* 엔드포인트: POST /api/v1/upload | 헤더 X-File-Name(URL인코딩 원본파일명) | body=파일 바이너리
* 저장 루트: <서버폴더>/uploads/ 하위를 파일 종류별 구역으로 분류
  - 사진(.jpg/.jpeg/.png/.gif/.webp/.bmp) → uploads/photos/
  - 문서(.pdf) → uploads/documents/
  - 기타 → uploads/etc/
* 파일명 규칙: '<epoch초>_<원본파일명>' (중복 방지, 한글 파일명 허용)
* 응답: {message, filepath:'uploads/<구역>/<파일명>', filename, category}
* 저장된 파일은 정적 URL(/uploads/...)로 즉시 열람 가능
* 연동: 협력사 증빙서류(partner_roster→contacts.documents_json), 유지보수 사진(incidents.photos_json)이 이 구역에 저장되고 경로만 DB에 기록

## 7. PATCH_HISTORY
### 2026-07-23 (오류수정 및 기능추가)
* [로그인] 프론트 호출 경로 POST /api/v1/auth/login 을 서버 인증 핸들러가 처리하도록 추가 (이전 404 → 로그인 불가).
* [로그인] index.html 응답 파싱을 user.role/user.employee_no 기준으로 교정 (이전 data.role 부재로 office_worker 폴백 → 마스터도 메뉴 축소되던 버그).
* [보안] routes.py 인증에서 db_pw=='admin123' 무조건통과 조건 제거 → 비밀번호 일치 필수.
* [데이터] GET /api/v1/contracts 조인 컬럼 c.contact_id → c.tenant_contact_id 수정 (이전 500으로 대시보드 데이터 미표시).
* [데이터] GET /api/v1/rooms 를 buildings 조인 + 별칭(building_name/building_address/room/floor/area/status) 반환으로 정합화 → 자산목록/호실 드롭다운 표시 정상화.
* [UI] main.html 상단 메뉴를 window.authModule.getButtonsByRole 로 #menuArea 에 렌더, 클릭 시 iframe 로드. 사용자/제작자모드 배지 연동.
* [입력] 전 페이지 날짜 입력을 숫자8자리(YYYYMMDD) 방식으로 통일 (공용 date8.js). 화면은 8자리, 스크립트/DB는 'YYYY-MM-DD' 유지.
* [파일] /api/v1/upload 종류별 저장구역(photos/documents/etc) 도입. partner_roster 증빙서류 업로드 로직 연결, contacts.documents_json 컬럼/라우트 반영.
* [정리] property_asset.html 제거 (미사용 구버전 자산등록 페이지).
* [기능] 계약서 OCR 자동채움 도입: contract_master.html + ocr_engine.py + POST /api/v1/ocr + install_ocr.sh. 계약서/신분증/여권 지원, 추정값→사람검토, 주민번호 마스킹.

### 2026-07-23 (2차 — 로그인게이트 / 자동백업 / 금일현황 리포트 / UI정리)
* [보안] 로그인 게이트 guard.js 신규 + 전 콘텐츠 페이지 주입. server.py 루트→index.html, main.html 미로그인 차단. (4장 AUTH_FLOW)
* [백업] db.py backup_db()/start_auto_backup() 구현 — 서버시작 1회 + 저장/수정(mtime변화) 감지 시 5분마다 building_manager.db를 _backups/auto/db_시각_사유.db 로 SQLite 스냅샷 롤링(최근30). server.py main() 호출. (행단위 system_snapshots·[K]복구UI는 미구현)
* [기능] 금일 관리 현황 리포트 daily_report.html 신규([RPT]) + auth.js 메뉴 최상단 등록(super_admin·office_worker). 인쇄/PDF. 미납·공실·만기·유지보수 예외집계 + 오늘의 연락리스트.
* [버그] auth.js '월세납부' 경로 rent_payment_ledger.html(없음)→monthly_rent_collection.html 교정.
* [UI] 계약서(B) 좌상단 안내박스 제거→업로드라벨 옆 "⚠️ 대조확인", 2단 35:65 복원. 월세납부·유지보수·관리비 하단 흰박스 제거. body높이 100vh 통일(하단 흰띠 제거), 부동산 표 flex:0 1 auto(빈박스 제거).
* [UI] 유지보수(F) '연락처(임차인)' 열 추가(계약 조인 tenant_phone·tel:링크)·대상호실 room_id→빌딩명+호실. 월세납부(E) 대상호실 빌딩명+호실·열폭 축소.
* [데이터] 테스트 더미 채움(건물5·호실10·계약11·공과금5·유지보수5·직원5·협력사5·임차인13), 옛 더미 이름/전화 정상화.
* [정리] 미사용 파이썬 5개(db_app.py 등) 삭제, 백업파일 _backups/ 이동, .gitignore 추가, Git 커밋+GitHub push.
* [잔여TODO] 수납장부 테이블(수납률/받은금액 집계) · system_snapshots 행단위+[K]복구UI · 구글드라이브 오프사이트 백업 · 임대인별 리포트필터 · 제작자 백도어 제거(운영전).

### 2026-07-24 (관리자 보안 + 수납장부 + 되돌리기)
* [보안] 제작자 URL 바이패스(master_sys_884621)·creatorBypass·제작자모드 전부 제거. 관리자 아이디=이메일, 비밀번호 sha256 해시 저장(평문 없음). 로그인창 아래 문의 이메일 1줄.
* [백업] 일자별 백업(_backups/daily 30일) + PC 내장드라이브 사본(~/부동산백업, USB 유실 대비) + 구글드라이브 동기화 폴더 복사(backup_to_drive, 설정파일/자동탐지). 앱에 인증정보 없음.
* [#1 수납장부] payments 테이블 + GET/POST /api/v1/payments + 월세납부(E) 수납 시 기록 + 금일현황(RPT)에 "수납률/월세미납" 반영.
* [#2 되돌리기] system_snapshots 테이블 + routes._snapshot()(contacts/contracts 수정 직전 자동 저장) + [K] 되돌리기 화면(auditlog.html) + POST /api/v1/snapshots/restore. 메뉴 [K] 라벨 '감사로그'→'되돌리기'.
* [제외] 임대인별 리포트 필터 = 불필요(임대인 1명·프로그램 1개 운영).

### 2026-07-25~29 (v1 현장배포 준비 — 계약서 개편 / 공용부 / 검색UI / 패키징)

[A] 부동산 (interface-a)
* 우측 목록 행 클릭 → 좌측 폼 자동 채움(수정 모드, 선택행 하이라이트+배너). [현황 변경] 실제 동작.
* 좌측에 '상태' 입력칸 추가(공실/임대중/임대중(단독층)/단독층 통합/사옥/수리중 자동완성).
* **신규 API**: POST /api/v1/rooms {id,...} = 호실 수정, POST /api/v1/buildings {id,...} = 건물 수정. 둘 다 수정 전 자동 스냅샷.

[B] 계약서 (contract_master) — 대폭 개편
* **OCR 전면 제거** → 순수 '원본 대조 뷰어'로 전환 (ocr_engine.py·/api/v1/ocr 은 서버에 남아있으나 화면에서 미사용).
* **임대인 입력란 삭제** (임대인 본인이 쓰는 프로그램).
* 업로드 **2칸 좌우 배치**: 📄계약서 원본 / 🪪신분증 사본. 각각 **여러 장** 업로드.
* 뷰어에 **[📄계약서][🪪신분증] 전환 버튼** + 여러 장일 때 ◀ n/m ▶ 이동.
* **특약사항을 우측 뷰어 상단으로 이동**(가로 전체·3줄) → 좌측 폼 세로 축소(스크롤 최소화).
* **부가세 체크박스** 추가(기본 켬, 단기계약은 해제) → documents_json.vat_applied 저장.
* **소재지 자동 연동**: 호실 선택 시 건물주소+호수 자동 입력(직접 수정하면 보존).
* **보증금·월차임 단위 = 만원 입력** → 저장 시 ×10,000 원 단위 변환. 환산액 실시간 표기.
* documents_json 구조: {files:[계약서들], id_files:[신분증들], file:대표1장, tenant:{...}, vat_applied:bool}

[C] 계약자 (contractor_roster)
* **명세서 출력 버튼** 추가 — 임차인 방문 시 월세·관리비·전기·수도·가스·통신·합계 A4 인쇄/PDF.
* 좌측 상단에 "명세서는 여기서 출력" 안내 배너.

[D] 공과금 (utility_bills)
* **전기 '요금(원)' 칸 신설** — 검침값·금액 **둘 중 하나만 있어도 저장**(한전 총액 고지 대응).
* **공용부 비용 등록**: [호실별]/[🏢공용부] 선택 → 건물+구역명(복도·공동화장실·계단·주차장 등)으로 등록.
* 우측 연속입력판: **검색창 신설**(440 입력 → 4층 전체 표시), 기존 '앞 10개 고정' 버그 제거, 좌우 연동.
* **일괄 저장 버튼**(화면의 층 전체 한 번에), 값 없는 줄 자동 건너뜀.
* **수정 지원**: 저장된 호실은 기존값이 채워진 채 [수정] 버튼으로 표시 → 중복행 없이 갱신.
* **신규 API**: POST /api/v1/bills {id,...} = 공과금 수정(스냅샷 후 갱신).

[E] 월세납부 (monthly_rent_collection)
* 계약서의 **부가세 설정 자동 반영**(미적용이면 체크 해제+0원), 화면에서 임시 변경 가능.
* 호실 선택을 **드롭다운 → 검색+층버튼** 방식으로 변경.

[F] 유지보수 (incidents_maintenance)
* **공용부 신고 등록** 지원(건물+구역명).
* 호실 선택을 **드롭다운(74개) → 검색+층버튼** 방식으로 변경.

[J] 팀원관리 (team_management)
* **직원 정보 수정 기능**: 행 클릭 → 폼 자동 채움 → [수정 내용 저장]. 비밀번호는 비우면 기존 유지.
* 마스터(id=999) 계정 **명부에서 숨김**, 비밀번호 열은 ●●●●●● 마스킹.

[L] 협력사 (partner_roster)
* **등록 계좌번호** 필드 추가(입력·수정·목록). 전화번호 미표시 버그(contact_info 매핑) 수정.

인증/보안
* **직원 로그인 불가 버그 수정** — 조회 쿼리가 'WHERE 사번=? OR id=999' 라 항상 마스터 행이 잡히던 것 → 입력 아이디로만 조회. 비활성(is_active=0) 계정 로그인 차단.
* 관리자 계정: 아이디=이메일, 비밀번호 sha256 해시 저장(평문 없음). 비밀번호 재변경(2026-07-25).
* 로그인 화면: **엔터키 로그인**(아이디→비번→로그인), **접속 주소 자동 표시**(GET /api/v1/serverinfo → LAN IP:포트).

서버/네트워크 (server.py)
* 포트 **8899**. 정적 파일을 **앱 폴더 절대경로**로 서빙(경로 탈출 차단) + **URL 인코딩** → 한글·공백 파일명 원본이 안 열리던 문제 해결.
* allow_reuse_address / request_queue_size 적용 → 종료 직후 재실행 실패(TIME_WAIT) 해소.
* 포트 점유 시 조용히 죽지 않고 원인·조치 안내 후 종료. 종료 시 server_close()로 포트 반납.
* 시작 시 '이 컴퓨터 / 다른 기기' 접속 주소 동시 출력.

DB 스키마 추가
* payments(수납장부), system_snapshots(되돌리기)
* contacts.account_no
* bills.elec_cost / building_id / scope('room'|'common') / common_area
* incidents.building_id / scope / common_area
* 기존 데이터는 scope 기본값 'room' 으로 자동 처리(영향 없음)

백업 (db.py)
* 3중 백업: _backups/auto(5분 단위 30개) + _backups/daily(하루 1개 30일) + **PC 내장드라이브 ~/부동산백업**(USB 유실 대비).
* 구글드라이브 동기화 폴더 자동탐지/설정(drive_backup_path.txt) → <드라이브>/부동산백업 복사. **앱에 인증정보 저장 안 함.**

배포 패키징
* build_windows.bat: py 3.13 우선 사용, **python DLL 자동 포함**(pythonXXX.dll 누락 해결), 화면·스크립트·안내문만 선별 복사(설계문서·구버전 제외).
* **install_service.bat**(현장 1회 실행): 관리자 권한 자동 요청 → 옛 방화벽 규칙 삭제 → **모든 프로필(개인/공용/도메인) 허용** → 부팅 자동실행 등록 → **절전·최대절전 해제** → 등록 결과 출력.
  - '인증창이 뜬 한 번만 접속되고 이후 차단'되던 원인 = 개인 프로필로만 허용된 규칙. profile=any 재등록으로 해결.
* **필독_사용안내.txt**: 비전문가(어르신) 기준 안내문. 전문용어 배제("중심 컴퓨터", "두 번 누릅니다" 등).

초기 데이터
* **seed_daerim.py**: 대림빌딩(서울특별시 영등포구 도림로 140) 74호실 일괄 등록. 중복 방지·재실행 안전.
  - B2(B201)/B1(B101)/1층 101~103/2층 201~203/3층 301~303/4~7층 각10실/8층 11실(880~889+800)/9층 11실(990~999+900)/10층 1000(사옥)
  - 단독층 사용 반영: 대표 호실 '임대중(단독층)', 나머지 '단독층 통합'. 1층만 개별 사용.

## 8. OCR_AUTOFILL (계약서/신분증/여권 자동채움) - 2026-07-23 추가
* 목적: 계약서(B) 화면에서 원본(PDF/사진) 업로드 시 OCR로 칸을 채우고 사람이 확인·수정 후 저장
* 방식: 오프라인 엔진(Tesseract, 한글 kor + eng). 개인정보 외부전송 없음. PDF는 poppler(pdftoppm)로 이미지 변환 후 인식
* 구성요소
  - contract_master.html : 업로드→[OCR 채우기]→추정값(노란칸+신뢰도 배지)→우측 원본뷰어 대조→저장. 날짜는 date8(8자리)
  - ocr_engine.py : 표준 임대차계약서 라벨앵커 필드추출, 여권 MRZ 파싱, 신분증 기본필드, 주민번호 마스킹
  - POST /api/v1/ocr : {filepath, doc_type('lease'|'id'|'passport')} → {engine, fields, confidence, raw_text, warnings}. BASE_DIR 하위 경로만 허용(경로탈출 방지)
  - install_ocr.sh / OCR_README.md : 구동 PC 엔진 설치(tesseract+kor+poppler) 및 사용안내
* 추출 필드(계약서): lease_type, host_address_full, room_no, deposit_amount, monthly_rent, maintenance_fee, start_date, end_date, owner/tenant rrn(마스킹)·phone, special_terms
* 추출 필드(여권): surname_en, given_names_en, passport_no, nationality, birth_date (MRZ 기반)
* 저장 연동: 계약필드는 /api/v1/contracts 로 저장, 당사자·여권·원본문서 메타는 documents_json(JSON)에 함께 보관(스키마 변경 없음)
* 원칙(R): 모든 OCR 값은 '추정치'이며 저장 전 사람이 원본과 대조·수정 필수. 주민등록번호는 뒷자리 자동 마스킹(예 480910-1******)
* 폴백: OCR 엔진 미설치 시 서버는 정상 동작하고 {engine.ready:false} 안내만 반환(무설치 포터블 성격은 OCR 기능에 한해서만 예외)


`;
