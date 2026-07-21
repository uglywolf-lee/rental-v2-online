# 부동산 관리 시스템 — 전역 규칙 + 인터페이스 명세 (최종본)

## 1. 핵심 DB 규칙 (1~23)

### 기본 규칙
1. 주소 기반 데이터베이스 — 부동산의 근원은 주소지
2. 핵심키는 별도 고유 ID — 주소는 속성일 뿐
3. 증가는 가능, 삭제는 불가능 (영구 폐기 절대 금지)
4. 부동산 특성에 따라 테이블값 형식 특정
5. 데이터베이스 수정 가능
6. 동일 주소 + 동일 층수/호실 조합에서만 중복 불가
7. DB 직접 조작 시 로그 기록 필수
8. **수정 시 신규 INSERT + 기존 비활성화 (is_active=0, DELETE 금지)**

### 전역 표준
| 번호 | 규칙 | 예시/형식 |
|:--:|---|---|
|9| 시간/날짜 (DB저장) | YYYY-MM-DD HH:MM:SS KST(+9h)|
|10| 전화번호 필수 형식 | NN-NNNN-NNNN (하이픈 14자리)|
|11| 이메일 소문자 강제 | lowercase_text@domain.tld|
|12| 금액 저장 | BigInt 원단위 정수. 공과금만 원단위 고정 |
|13| 금액 화면표시 | 공과금 외 천/만원 단위 |
|14| KST 한국타임 통일 | 부동산 항목: YYYY-MM-DD (요일) 표시 |

### 권한/백업 (Rules 15~23)
| 번호 | 내용 |
|:--:|---|
|15 | super_admin — 모든 데이터 조작, 불특정사용자 차단 |
|16 | office_worker — 검색+입력만 (수정/삭제 불가)|
|17 | maintenance_staff — 시설만 입력+조회 / 계약서 수정불가 |
|18 | DB_logs 필수저장 (모든작업 추적) |
|19 | system_snapshots: 수정 전 반드시 이전 상태 JSON 자동저장 |
|20 | ROLLBACK: 실수시 data_snapshot_json로 INSERT/UPDATE — 즉시 복구 가능 |
|21 | users+role_name 기준 매핑 |
|22 | audit_logs.detail_log_json에 변경전후값 기록 |
|23 | 핵심데이터(contacts/bills/contracts)수정전 ALWAYS 롤백-스냅샷 필수 |

## 2. 페이지 제작+빌드 규칙 (24~32)
1. 모든 페이지 독립 HTML+CSS+JS 단일파일로 구성
1. 디자인 토큰 통일: --primary / --border / --bg 만 사용. Inline 스타일 금지
3. 영문 필드명 화면에 노출 절대 불가 -> 우리말 치환
4. 파일 구조: {page}.html + styles.css + api.js + data.json

## 3. 핵심 테이블 구조 명세

### buildings (부동산)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK) | 필수 | 건물 고유KEY |
| name | Varchar(255) | 필수 | 건물명 |
| address | Varchar(500) | 필수 | 실제住所핵심(A-부동산매핑기준)|
| floors | Integer | 선택 | 총층수 |
| rooms_count | Integer | 선택 | 전체호실수 |
| is_active | Boolean | 필수 | 1=활성 0=비활성 (DELETE 절대금지) |

### rooms (호실)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|호실고유키|
| building_id | INT FK->buildings.id |필수|소속건물ID|
| floor_no | Integer | 필수 | 층수(중복가능) |
| room_no | Varchar(50) | 필수 | '101호' 등 |
| area_sqm | Decimal(10,3) | 선택 | 면적 sqm |
| current_room_status | Varchar(50) | 선택 | 비어있다/입주중/리모델링|

### contacts (계약자+B2B통합)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK) | 필수 | 고유키 |
| category | Varchar(50) | 필수 | tenant/broker/partner |
| company_or_name | Varchar(255) | 필수 | 상호명 또는 성명 |
| representative_name | Varchar(100)|선택|대표자 실명 (법인/중개사)|
| contact_info | Varchar(50) | 필수 | 전화번호 NN-NNNN-NNNN |
| email | Varchar(255) | 선택 | 소문자 강제변환저장 |
| documents_json | JSON/Text | 선택 | 사업자등록증 or 신분증 경로|

### contracts (계약서 핵심)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|계약서 고유키|
| room_id | INT FK->rooms.id | 필수 | 해당호실ID (B-부동산매핑) |
| owner_contact_id | INT FK->contacts.id | 필수 | 임대인소유주(C번 매핑) |
| tenant_contact_id | INT FK->contacts.id | 필수 | 임차인실세사용자(C번 매핑) |
| broker_id | INT FK->contacts.id | 선택 | 중개사B2B협력사매칭 (자동채움+대표자명)|
| lease_type | Varchar(50)|필수|전세/월세/반전세 등|
| deposit_amount|BigInt(원)|필수|보증금(E-월세납입매핑)|
| monthly_rent|BigInt(원)|필수|월임대료(E+G통합총계매핑)|
| commission_fee|BigInt(원)|선택|중개수수료(C-category=broker 연동필수)|
| start_date,end_date|Date|필수|YYYY-MM-DD 계약시작/종료|
| is_active|Boolean|필수|0:해지/만료 1:진행중(삭제금지스냅샷필수)|

### bills (공과금)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|청구용ID|
| room_id | INT FK->rooms.id|필수|청구대상호실|
| contact_id | INT FK->contacts.id|선택|고지대상최신계약자id|
| bill_type | Varchar(50)|**필수**|전기/수도/난방비/관리비/통신비/가스요금 (D-통합검침+고지확장)|
| amount|BigInt(원)|**필수**|청구금액(원단위정수). 규칙=FIELDS.md완전히통일|
| due_date|Date|필수|YYYY-MM-DD 납부기한. E-연체처리매핑|
| is_paid|Boolean|필수/선택|0:미납 1:결제완료|

### meter_readings (계량검침·D전용)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|검침고유번호|
| room_id | INT FK->rooms.id|필수|어느호실연결고리|
| bill_type | Varchar(50)|필수|전기/수도 등 유형구분. bills.bill_type 매핑|
| last_cumulative_reading|BigInt|선택|전월 최종누적량(kWh/톤 기준)|
| current_cumulative_reading|BigInt|**필수**|이번달 실제검침누적값 (실제입력)|
| usage_amount|BigInt|선택|사용량 계산결과(current-last). bills.amount생성기준|
| billing_amount_won|BigInt(원)|**필수**|확정요금. 고지서금액 그대로 저장|
| billing_period_start,end_date|Date|필수|YYYY-MM-DD 실제사용기간|

### incidents (유지보수+사건)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|유지보수기록ID|
| room_id | INT FK->rooms.id|필수|이슈호실ID (F-파손신고매핑)|
| category | Varchar(50)|선택|시설파손/무단점유/일반유지보수|
| description|Text|**필수**|실제내용 ('2층102화장실관 파열')|
| reported_by_id|INT FK->users.id|**필수**|누가신고했는지 F+I-신고자매핑|
| estimated_cost|BigInt(원)|선택|수리비추산액(F/I정산금액연결고리핵심)|
| status|Varchar(50)|**필수**|접수중->보급완료 I-처리상태변경매핑|

### users (내부직원+권한관리)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|고유키|
| employee_no|Varchar(20)|**필수**|사원고용번호 EMP-001 형식 고정(팀페이지규칙40)|
| role_name|Varchar(50)|필수|super_admin/office_worker/maintenance_staff|
| password_hash|Varchar(255)|필수|SHA256+Salt. 평문 절대 금지. minimum_length=6|

### audit_logs (감사로그)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|고유키|
| executed_by_id|INT FK->users.id|필수|로그인한실제사용자 ID. 누구의짓인지추적|
| action_table_name|Varchar(50)|필수|조작된테이블명(ex:'contracts')|
| action_type|Varchar(50)|필수|INSERT/UPDATE/LOGIN/LOGOUT |
| target_id | Integer|선택|변경된실제데이터로우ID|
| detail_log_json|JSON/Text|**필수**|{'monthly_rent':{'old', 'new'}} 등 변경내용|
| created_at,updated_at|Datetime(KST)|자동|YYYY-MM-DD HH:MM:SS 형식 준수 |

### memos (G/HI 실무 수납 메모)
| 필드 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| id | Integer(PK)|필수|메모고유번호(중복불가)|
| room_id | INT FK->rooms.id|필수|어느호실 수납과정출력메모연결고리 |
| contact_id | INT FK->contacts.id|**필수**|어떤임차인 상호/성명과 얽힌대화연결고리|
| writer_user_id | INT FK->users.id|**필수**|전화를 돌리고이 메모를작성한직원ID|
| memo_text|Text|**필수**|오늘오후3시입금약속 등 실제진행상황내용 |
| created_at|Datetime(KST)|자동|YYYY-MM-DD HH:MM:SS 기록일시|

## 4. A~I 인터페이스 매핑 정리 (Rules Engine + FIELDS 완전일치)

**[A 번] 부동산관리** (interface-a.html)  
- 필드매핑: buildings.name/address/floors/rooms_count + rooms.floor_no,room_no,area_sqm(FIELDS01+02완전일치)  
- 수정/검색기준: is_active=0->신규ROW(8번규칙). 검색 by address LIKE '%주소%'  

**[B 번] 계약서관리** (contract_master.html)  
- 주요 매핑: contracts.lease_type,deposit_amount,monthly_rent,commission_fee + owner_contact_id,tenant_contact_id(FIELDS③매칭)|  
- 계약서원본PDF/JPG->uploads/contracts/(가칭_2025_001.pdf) / is_active=0 -> 신규ROW(8번규칙+스냅샷자동저장) 매핑  

**[C 번] 계약자관리** (contractor_roster.html)  
- contacts.company_or_name(representative_name 필드명FIXED), contact_info 'NN-NNNN-NNNN'Fixed, email 소문자강제. / is_active=0 -> 신규ROW + company_or_name LIKE '%연체조회/해지여부일관매핑|

**[D 번] 공과금검침+고지관리** (utility_bills.html)  
- bills.bill_type <- meter_readings.bill_type 매핑. 검침입력(전월/당월누적)->사용량자동산출(billing_amount_won)->bills.amount생성연동. 청구항목: 전기요금, 수도요금, 난방비, 관리비, 통신비, 가스요금 (D-통합검침+고지확장)  

**[E 번] 월세납입관리** (monthly_rent_collection.html)  
- deposit_amount + monthly_rent(bills.amount)/납부일/정산내역(보증금반환) / 납부이력변경 연체처리 / 월별납현황총계요약+미납자리스트 매핑  

**[F 번] 시설유지보수/파손신고** (incidents_maintenance.html)  
- incidents.description(room_id FK + reported_by_id FK->users.id 매핑필드) / estimated_cost(정산금액항목) / status('접수중'->'완'
**[G 번] 통합 월세관리 인터페이스** (g_h_i_dashboard.html)  
- 전체: 부동산별·계약자별월세총입금+모든공과금(bills.amount)/보증금반환현황한눈에매핑필드  

**[H 번] 통합 계약 관리 인터페이스**  
- 전체: 모든계약의만기/갱신/해지현황 + 다음행위추적표 — 계약서+계약자+부동산연결고리 한눈에  

**[I 번] 직원용 대시보드** (전체종합)  
- 부동산총수량·계약현황·미납월세(contacts.bills.is_paid+Bills.amount연결고리)/예외사건 통합.
- users.role_name('super_admin'/'office_worker'/'maintenance_staff')로접근제한
- audit_logs.detail_log_json전부매핑  

**[J 번] 팀원등록페이지** (team_management.html)  
사번/고용번호 = users.employee_no FK·role_name(FIELDS⑦매핑). 이메일제거, 비밀번호 minimum_length=6 필수.

**[K 번] 시스템 복구 및 데이터 백업 관리**
핵심 데이터 수정 전 생성된 system_snapshots의 JSON을 추적하여 1초 만에 원상복구(Rollback)하는 마스터 제어판.

---
*최종 확인: rules.html 필드명 = FIELDS.md = interfaces.html 일치완료·bills.amount/representative_name/broker_id모두FIXED ·모든테이블소문자_스네이크케이스명·DB삭제절대불가·is_active=0만비활성화(규칙3·8)·system_snapshots rollback:핵심데이터수정전반드시자동저장→is_restored=1마킹(23번규칙)*
