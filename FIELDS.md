# 부동산 관리 시스템: 필드명 명세서 (Schema Reference)

> **규칙**: 실제 데이터베이스는 이 파일을 기준으로 작성. 테이블명은 반드시 복수형, 컬럼명은 소문자_스네이크케이스를 사용하며 여기와 일치해야 합니다. 

---

## 0. 전역 데이터 형식 표준 (Global Type Standards)
모든 테이블에 일관성을 위해 아래 형식을 필수로 지켜야 합니다:

| 항목 | 형식 정의 | 예시 / 설명 |
|---|---|---|
| **시간/날짜 (DB저장)** | `YYYY-MM-DD HH:MM:SS` (32400초 오프셋 기준) | DB에는 UTC를 KST(+9h)로 정확히 변환하여 저장해야 합니다. |
| **부동산 시간 표시 규칙** | `'YYYY-MM-DD (요일)'`(Date only + Day of week) | 부동산 관련 데이터(Rooms, Buildings 등 물리적 정보 중심)는 데이터상에서는 시간이 있지만 화면에 출력될 때는 시간(HH:MM:SS)은 완전히 배제하고 오직 **일자와 요일만** 보여줘야 합니다. ('2024-01-30 (화)') |
| **전화번호** | `NN-NNNN-NNNN` (하이픈 포함 14자리) | 반드시 고정: `'010-1234-5678'`. 모바일/유선 상관없이 숫자와 하이픈만 사용합니다. 공백( )과 괄호는 허용하지 않습니다. |
| **이메일** | `lowercase_text@domain.tld` (소문자 고정) | 소문자로 강제 변환 저장해야 합니다. |
| **금액 (저장)** | BigInt (숫자, 원단위) | DB에는 소수점 없이 정수로 저장. (예: 5000000) |
| **금액 (화면표시)** | 변환형 Varchar | 공과금 외는 천/만원 단위 표시(예: 50000 → '5만원'), 공과금은 원단위로 고정. |

---

## 1. buildings (부동산 목록 테이블)
*모든 현장과 건물의 물리적 정보를 담는 근원으로, 수정 시 신규 ROW를 추가하고 기존 ROW는 is_active를 0으로 내립니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 (중복 불가) |
| `name` | Varchar(255) | 필수 | 건물명 또는 현장별 고유 명칭 |
| `address` | Varchar(500) | 필수 | 실제 주소 (검색 및 계약의 주 기준) |
| `floors` | Integer | 선택 | 총 층수 (중고/신규/파손 포함 시 업데이트 필요) |
| `rooms_count` | Integer | 선택 | 전체 호실 수 |
| `is_active` | Boolean | 필수 | 활성 상태(1)/삭제 상태(0). 데이터 영구 폐기 절대 금지. |
| `created_at`, `updated_at` | Datetime (KST) | 자동 | 생성/수정 시점 (`YYYY-MM-DD HH:MM:SS`형식 준수) |

---

## 2. rooms (개별 호실 리스트 테이블)
*한 건물 안의 각 호실이 담기는 테이블입니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `building_id` | Integer (FK→buildings.id) | 필수 | 매칭될 건물 정보 ID |
| `floor_no` | Integer | 필수 | 층수 (중복 가능: A동 2층과 B동 2층이 각각 존재) |
| `room_no` | Varchar(50) | 필수 | 호실명 (예: '101호') |
| `area_sqm` | Decimal(10,3) | 선택 | 전용/전체 면적 (㎡) |
| `current_room_status` | Varchar(50) | 선택 | 비어있다, 입주민중, 리모델링 등. 관리자의 시각화용 필드입니다. |

---

## 3. contacts (계약자 및 B2B 파트너 통합 테이블)
*실세 계약자인 임차인·임대인을 포함하여 모든 중개사, 관리사무소, 협력사가 이 테이블 안에 들어갑니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유키 |
| `category` | Varchar(50) | 필수 | 구분자: 'tenant'(실세임차인·소유주), 'broker'(중개사), 'partner'(B2B협력사) 등 모든 관계를 하나의 테이블에서 관리할 수 있게 합니다. |
| `company_or_name` | Varchar(255) | 필수 | 상호명 또는 성명 |
| `representative_name` | Varchar(100) | 선택 | 법인/중개사 명의면 실제 대표자나 계약담당자의 실명입니다. (실제 계약 시 필요) |
| `contact_info` | Varchar(50) | 필수 | 전화번호 (`NN-NNNN-NNNN` 형식 고정 - 하이픈 포함 최대 16자리) |
| `email` | Varchar(255) | 선택 | 이메일 주소 (소문자 강제 변환 저장) |
| `documents_json` | JSON / Text | 선택 | 사업자등록증 or 신분증 사본의 파일 경로 및 ID 정보입니다. 주민등록번호 뒷자리는 절대 DB 저장 금지. |

---

## 4. contracts (계약서 내역 테이블 - 가장 핵심)
*중개사 개입이 많아 중개수수료, 기간, 금액 등 상세하게 관리해야 합니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `room_id` | Integer (FK→rooms.id) | 필수 | 해당 계약이 있는 구체적인 호실 ID |
| `owner_contact_id` | Integer (FK→contacts.id) | 필수 | 임대인/소유주 매칭 ID |
| `tenant_contact_id` | Integer (FK→contacts.id) | 필수 | 임차인/실세사용자 ID |
| `broker_id` | Integer (FK→contacts.id) | 선택 | 실제 중매를 선 중개사 매칭 ID. B2B 계약 시 사용 |
| `lease_type` | Varchar(50) | 필수 | 유형: '전세', '월세', '반전세' 등. |
| `deposit_amount` | BigInt (원) | 필수 | 보증금 (단위: 원 -> 전체 금액을 정수로 저장) |
| `monthly_rent` | BigInt (원) | 필수 | 월 임대료 (단위: 원) |
| `commission_fee` | BigInt (원) | 선택 | 이 계약서의 중개수수료. 중개사와의 정산 및 관리에 필요. |
| `start_date`, `end_date` | Date | 필수 | 실제 계약 만기일 / 시작일 (기간 계산 핵심) |
| `is_active` | Boolean | 필수 | 현재 유효한지 (0: 해지/만료, 1: 진행중). 계약서는 영구 삭제되면 안 됩니다. |

---

## 5. bills (공과금 및 정산 테이블 - 관리비, 전기, 수도)
*계약의 세부 항목으로, 각 호실에서 발생한 공과금을 매달 기록하는 테이블입니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `room_id` | Integer (FK→rooms.id) | 필수 | 청구 대상 호실 ID |
| `contact_id` | Integer (FK→contacts.id) | 선택 | 누구에게 고지할지 (계약서가 여러 개일 경우, 최신 계약자의 ID가 자동 매칭됩니다) |
| `bill_type` | Varchar(50) | 필수 | '전기요금','수도요금','난방비','관리비','통신비','가스요금' 등 bills.bill_type 매핑(D-통합검침+고지확장) |
| `amount` | BigInt (원) | 필수 | 청구 금액 (`NN-NNNN-NNNN` 형식 고정 - 하이픈 포함 최대 16자리) |
| `billing_period_start`, `billing_period_end` | Date | 필수 | 실제 사용기간 (예: 1월 1일 ~ 1월 31일) |
| `due_date` | Date | 필수 | 납부기한. 이 날짜를 넘어가면 연체 상태가 됩니다. |
| `is_paid` | Boolean | 필수 / 선택 | 0=미납, 1=결제완료. 실세 입금 확인 시 업데이트해야 합니다. |

|---|

## 6-A. meter_readings (계량검침 기록 테이블) — D인터페이스 전용
*전기/수도 미터기의 실제 누적 검침값을 매월 입력·저장하는 테이블입니다. bills.amount는 이 데이터를 기준으로 요금 계산 후 생성됩니다.*

|| 필드명 | 타입 | 필수/선택 | 설명 |
||---|---|---|---|
|| `id` | Integer (PK) | 필수 | 검침기록고유번호 |
|| `room_id` | Integer (FK→rooms.id) | 필수 | 어느 호실의 검침인지 연결고리 |
|| `bill_type` | Varchar(50) | 필수 | '전기요금' / '수도요금' 등 유형구분 |
|| `last_cumulative_reading` | BigInt (kWh/톤) | 선택 | 지난달 최종 누적 계량값 (전월비교용). 전기=kWh, 수도=톤 단위 |
|| `current_cumulative_reading` | BigInt (kWh/톤) | 필수 | 이번달 실제 검침 누적값. 전월빼면사용량 자동계산됨 |
|| `usage_amount` | BigInt (kWh/톤) | 선택 | 사용량 계산결과: current - last. bills.amount 생성시 기준이 됨 |
|| `billing_amount_won` | BigInt (원) | 필수 | 확정요금 (원단위 정수). 한전/수도공사 고지서 금액 그대로 저장 |
|| `billing_period_start` | Date | 필수 | 사용기간 시작일 ('YYYY-MM-DD') |
|| `billing_period_end` | Date | 필수 | 사용기간 종료일 ('YYYY-MM-DD') |
|| `due_date` | Date | 필수 | 납부기한. bills.due_date와 동일 |

|---|

## 6. incidents (유지보수 및 사건사고 테이블)
*건물의 파손, 무단점유 등 계약서와 별개로 별도 관리해야 하지만 해당 건물의 ID를 통해 한눈에 볼 수 있습니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `room_id` | Integer (FK→rooms.id) | 필수 | 이슈가 생긴 호실 ID. |
| `category` | Varchar(50) | 선택 | 유형 ('시설파손', '무단점유', '일반유지보수') |
| `description` | Text | 필수 | 실제 내용 (예: '2층 102호 화장실 관 파열'). |
| `reported_by_id` | Integer (FK→users.id) | 필수 | 누가 신고했는지 (건물유지보수인 등 내부 직원의 ID). |
| `estimated_cost` | BigInt (원) | 선택 | 수리비 추산액. 실제 정산 시 이 비용은 계약서와 연결하여 임차인으로부터 청구받습니다. |
| `status` | Varchar(50) | 필수 | 상태 ('접수중', '보급완료'). 내부 업데이트의 핵심 열입니다. |

---

## 7. users (내부 직원 및 권한관리 테이블 - B2B 포함)
*모든 작업을 하는 관리자와 사무원, 유지보수인의 아이디와 비밀번호를 저장합니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
|| `employee_no` | Varchar(20) | 필수 | 사원고용번호EMP-001 형식 고정 — team_management.html의사번과 매핑됨 ||
| `role_name` | Varchar(50) | 필수 | 권한 구분 ('super_admin', 'office_worker', 'maintenance_staff'). 역할별로 다른 UI화면이 열립니다. |
| `password_hash` | Varchar(255) | 필수 | MD5/SHA256 등 해시된 비밀번호 (평문 절대 금지). |

---

## 8. audit_logs (감사로그 - Who did what?)
*누가 언제, 어떤 데이터(호실/계약서)에 대한 수정을 했는지 추적하는 테이블 입니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `executed_by_id` | Integer (FK→users.id) | 필수 | 로그인한 실제 사용자의 ID. 누구의 짓인지 추적합니다. |
| `action_table_name` | Varchar(50) | 필수 | 조작된 테이블명(ex: 'contracts' 또는 'rooms') |
| `action_type` | Varchar(50) | 필수 | 작업종류 ('INSERT', 'UPDATE', 'LOGIN', 'LOGOUT') |
| `target_id` | Integer | 선택 | 변경된 실제 데이터의 로우 ID. |
| `detail_log_json` | JSON / Text | 필수 | 변경 내용 (예: '{ "monthly_rent": {"old": 500, "new": 600} }') |
| `created_at`, `updated_at` | Datetime (KST) | 자동 | KST 기준 타임스탬프 (`YYYY-MM-DD HH:MM:SS`형식 준수). |

|---|

## 10. memos (G/HI 실무 수납 메모 테이블)
*전화통화 중 확인된 수납 진행상황을 실시간 기록하는 테이블입니다.*

|| 필드명 | 타입 | 필수/선택 | 설명 |
||---|---|---|---|
|| `id` | Integer (PK) | 필수 | 메모고유번호 (중복불가) |
|| `room_id` | Integer (FK→rooms.id) | 필수 | 어느호실의 수납과정에서 나온 메모인지 연결고리 |
|| `contact_id` | Integer (FK→contacts.id) | 필수 | 어떤임차인 상호/성명과 얽힌 대화인지 연결고리 |
|| `writer_user_id` | Integer (FK→users.id) | 필수 | 전화를 돌리고이 메모를 작성한 직원 ID |
|| `memo_text` | Text | 필수 | "오늘 오후 3시 입금 약속" 등 실제 진행상황 내용 |
|| `created_at` | Datetime (KST) | 자동 | 메모 기록일시 (`YYYY-MM-DD HH:MM:SS` KST 형식) |

|---|

## 9. system_snapshots (데이터 복원을 위한 백업 및 변경 로그 테이블)
*실수가 발생했을 시 모든 데이터를 즉시 복구(rollback)하기 위한 핵심 작업 테이블입니다.*

| 필드명 | 타입 | 필수/선택 | 설명 |
|---|---|---|---|
| `id` | Integer (PK) | 필수 | 고유 키값 |
| `snapshot_type` | Varchar(50) | 필수 | 백업 종류 ('full_backup', 'contract_undo', 'auto_snapshot' 등 자동저장) |
| `target_table_name` | Varchar(50) | 필수 | 대상 테이블명 (예: 'contracts', 'rooms') |
| `target_id` | Integer | 필수 | 변경되거나 백업된 데이터의 로우 ID. 이 데이터가 현재 상태임을 추적합니다. |
| `data_snapshot_json` | JSON / Text | 필수 | **중요**: 변경 전이나 수정 시 원본 데이터를 통으로 저장합니다. (실수 발생 시 이 JSON을 다시 DB에 INSERT/UPDATE하여 1초 만에원상복구 가능) |
| `requested_by_id` | Integer (FK→users.id) | 필수 | 백업을 요청한 실제 관리자 ID (누가 언제 백업했는지 파악). |
| `is_restored` | Boolean | 선택 | 0: 미회복, 1: 복구완료. 해당 스냅샷이 이미 사용되었는지 확인합니다. |

### 📌 데이터 복원(ROLLBACK) 및 백업 규칙 (운영 필수)

> **규칙**: 시스템에 로그인한 모든 권한(user)은 `contracts`, `rooms`, `bills` 같은 핵심 데이터를 수정하기 전, 반드시 `system_snapshots`(이전 상태 JSON 저장) 테이블에 자동 스냅샷을 등록해야 합니다. 
실수로 잘못된 돈을 입력하거나 임차인 정보를 지울 경우, 해당 스크립션의 `id`와 `data_snapshot_json` 값을 찾아 삽입 혹은 업데이트를 실행하면 데이터가 즉시 원래대로 돌아갑니다. 모든 데이터 삭제(delete)는 무조건 `system_snapshots`에 기록한 뒤, 비활성화(`is_active = 0`)만 수행해야 합니다.
