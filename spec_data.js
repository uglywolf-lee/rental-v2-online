window.REAL_ESTATE_SYSTEM_SPEC = `
# REAL_ESTATE_SYSTEM_SPEC (v2.3 - 2026-07-23 로그인게이트/자동백업/금일현황리포트 반영본)
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
* URL 바이패스: GET /?access=master_sys_884621 → auth.js 가 sessionStorage(creatorBypass=true, userRole=super_admin) 주입 + 제작자모드 배지 노출. 서버 인증과 별개인 클라이언트 우회 경로.
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
