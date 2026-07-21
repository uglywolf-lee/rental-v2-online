window.REAL_ESTATE_SYSTEM_SPEC = `
# REAL_ESTATE_SYSTEM_SPEC (v1.1)
## 0. GLOBAL_STANDARDS
* DATETIME: DB=${'`'}YYYY-MM-DD HH:MM:SS${'`'} (KST) | UI=${'`'}YYYY-MM-DD (요일)${'`'} (시간 배제)
* PHONE: ${'`'}NN-NNNN-NNNN${'`'} (14자 고정, 공백/괄호 금지)
* EMAIL: ${'`'}lowercase_text@domain.tld${'`'} (소문자 강제 변환)
* AMOUNT_RE: DB=BigInt(원단위) | UI=Varchar(천/만원 단위 변환)
* AMOUNT_BILL: DB=BigInt(원단위) | UI=원단위 고정

## 1. CORE_RULES
* R1: 주소 기반 DB (부동산 근원은 주소지)
* R2: 고유 ID가 PK (주소는 속성일 뿐)
* R3: INSERT/UPDATE만 가능, DELETE 영구 금지
* R4: 부동산 특성(상가/오피스텔/아파트/토지)별 테이블 구조 특정
* R5: DB 수정 허용 (이력 추적 필수)
* R6: [CRITICAL] 동일 주소 + 동일 층 + 동일 호 조합 중복 절대 불가
* R7: DB 직접 조작 시 로그 강제 기록 (${'`'}audit_logs${'`'})
* R8: [CRITICAL] 수정 시 신규 ${'`'}INSERT${'`'} + 기존 비활성화 (${'`'}is_active=0${'`'})
* R15: ${'`'}super_admin${'`'}(전권, 접근차단) / ${'`'}office_worker${'`'}(검색/입력만) / ${'`'}maintenance_staff${'`'}(시설입력/조회만, 계약서불가)
* R18: 감사로그 필수 저장 (${'`'}audit_logs.detail_log_json${'`'} 변경 전후 기록)
* R19: 수정 전 상태 JSON 백업 (${'`'}system_snapshots.data_snapshot_json${'`'} -> 복구 시 ${'`'}is_restored=1${'`'})
* R24: 독립 단일 HTML/CSS/JS 구조, REST API(${'`'}/api/v1/${'`'}) 분리
* R25: 디자인 토큰 변수만 사용 (${'`'}--primary${'`'}, ${'`'}--border${'`'}, ${'`'}--bg${'`'}), 인라인 스타일 금지
* R26: 영문 필드명 UI 노출 절대 금지 -> 우리말 치환 필수
* R27: 페이지 컴포넌트 4종 세트 (${'`'}{page}.html${'`'}, ${'`'}-styles.css${'`'}, ${'`'}-api.js${'`'}, ${'`'}-data.json${'`'})
* R28: Rebuild 순서: DB Scripts -> Rules Engine -> API -> UI Pages

## 2. DATABASE_SCHEMA
### buildings (부동산 목록)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}name${'`'} (Varchar(255), Req)
* ${'`'}address${'`'} (Varchar(500), Req, 검색기준)
* ${'`'}floors${'`'} (Integer)
* ${'`'}rooms_count${'`'} (Integer)
* ${'`'}is_active${'`'} (Boolean, Req, Def 1)
* ${'`'}created_at${'`'} / ${'`'}updated_at${'`'} (Datetime)

### rooms (호실 정보)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}building_id${'`'} (Integer, FK -> buildings.id, Req)
* ${'`'}floor_no${'`'} (Integer, Req)
* ${'`'}room_no${'`'} (Varchar(50), Req, ex: '101호')
* ${'`'}area_sqm${'`'} (Decimal(10,3))
* ${'`'}current_room_status${'`'} (Varchar(50), ex: '비어있다', '입주중')

### contacts (관계자 마스터 통합)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}category${'`'} (Varchar(50), Req, 'tenant'|'landlord'|'broker'|'partner')
* ${'`'}company_or_name${'`'} (Varchar(255), Req, 인터페이스C 매핑 - 인간용 이름/상호)
* ${'`'}representative_name${'`'} (Varchar(100), 대표자 실명 / UI노출용실명)
* ${'`'}contact_info${'`'} (Varchar(50), Req, ${'`'}NN-NNNN-NNNN${'`'} 고정 - UI에연락처로표시)
* ${'`'}email${'`'} (Varchar(255), 소문자 고정 - UI이메일용)
* ${'`'}documents_json${'`'} (JSON/Text, 주민번호 뒷자리 저장 금지 - 신분증사업자증사본경로저장)

### contracts (계약서 내역)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}room_id${'`'} (Integer, FK -> rooms.id, Req 실세호실UID연동 - DB에서만고유번호처리UI노출제외)
* ${'`'}host_address_full${'`'} (Text,Req 대상호실실제이름예A동201호입주일 - UI상표시용 인간인식정보 DB저장용)
* ${'`'}owner_contact_id${'`'} (Integer, FK -> contacts.id, Req 임대인FK연동 - UI에ID노출안됨)
* ${'`'}tenant_contact_id${'`'} (Integer, FK -> contacts.id, Req 임차인FK연동contacts.company_or_name+representative_name 연결)
* ${'`'}broker_id${'`'} (Integer, FK -> contacts.id 중개사B2B선택사항 - UI노출제외DB저장연동만)
* ${'`'}lease_type${'`'} (Varchar(50Req '전세'|'월se'/반전세') - 계약종류탭에서선택
* ${'`'}deposit_amount${'`'} (BigInt Req 보증금정수저장원단위BigInt)UI보증금입력칸과매핑
* ${'`'}monthly_rent${'`'} (BigInt Req 월임대료원단위 BigInt)UI월세입력칸연동
* ${'`'}commission_fee${'`'} (BigInt 중개수수료 - UI선택사항항목DB저장용정산)
* ${'`'}start_date${'`'} / ${'`'}end_date${'`'}(Date Req 계약일지탭입력값연동)
* ${'`'}documents_json${'`'} (JSON/Text 신분증사본·사업자등록증사본계약서원본업로드파일경로배열또는JSON)UI문서업로드탭저장고유번호DB에서만처리UI노출안됨.

### bills (공과금 및 청구 마스터)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}room_id${'`'} (Integer, FK -> rooms.id, Req)
* ${'`'}contact_id${'`'} (Integer, FK -> contacts.id)
* ${'`'}bill_type${'`'} (Varchar(50), Req, '전기요금'|'수도요금'|'난방비'|'관리비'|'가스요금'|'통신요금'|'부가세')\n* ${'`'}amount${'`'} (BigInt, Req, 청구금액 필드명 고정)
* ${'`'}billing_period_start${'`'} / ${'`'}billing_period_end${'`'} (Date, Req)
* ${'`'}due_date${'`'} (Date, Req, 초과 시 연체 상태 전환)
* ${'`'}is_paid${'`'} (Boolean, Req, Def 0)

### meter_readings (계량 검침 기록 - D인터페이스 전용)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}room_id${'`'} (Integer, FK -> rooms.id, Req)
* ${'`'}bill_type${'`'} (Varchar(50), Req)
* ${'`'}last_cumulative_reading${'`'} (BigInt, 전월누적값)
* ${'`'}current_cumulative_reading${'`'} (BigInt, Req, 당월누적값 실제 입력 필드)
* ${'`'}usage_amount${'`'} (BigInt, 자동계산 결과: current - last)
* ${'`'}billing_amount_won${'`'} (BigInt, Req, 확정요금 -> bills.amount 필드로 변환 연동)
* ${'`'}billing_period_start${'`'} / ${'`'}billing_period_end${'`'} / ${'`'}due_date${'`'} (Date, Req)

### incidents (유지보수 및 사건사고)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}room_id${'`'} (Integer, FK -> rooms.id, Req)
* ${'`'}category${'`'} (Varchar(50), '시설파손'|'무단점유'|'일반유지보수')
* ${'`'}description${'`'} (Text, Req)
* ${'`'}reported_by_id${'`'} (Integer, FK -> users.id, Req)
* ${'`'}estimated_cost${'`'} (BigInt, 수리비 추산액 -> 임차인 청구 연계 핵심 필드)
* ${'`}reported_by_name${{'}} (Varchar(50), Req, 담당자실명 - DB저장용/실제조회UI필드)
* ${'`'}status${'`'} (Varchar(50), Req, '접수중'|'보급완료'|'처리완료')

### memos (실무 수납 메모 - G/H/I 대시보드 규칙35 매핑)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}room_id${'`'} (Integer, FK -> rooms.id, Req)
* ${'`'}contact_id${'`'} (Integer, FK -> contacts.id, Req)
* ${'`'}writer_user_id${'`'} (Integer, FK -> users.id, Req)
* ${'`'}memo_text${'`'} (Text, Req, ✍️ 실무 진행 대화 기입)
* ${'`'}created_at${'`'} (Datetime, KST 자동 생성)

### users (내부 직원 계정 - 규칙40 매핑)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}employee_no${'`'} (Varchar(20), Req, Unique, 'EMP-001' 사번 포맷 고정)
* ${'`'}role_name${'`'} (Varchar(50), Req, 'super_admin'|'office_worker'|'maintenance_staff')
* ${'`'}password_hash${'`'} (Varchar(255), Req, 평문 금지, 최소 길이 6자 제약 검증 필수)

### audit_logs (감사로그 - K인터페이스 전용)
* ${'`'}id${'`'} (Integer, PK, AI)
* ${'`'}worker_id${'`'} (Integer, FK -> users.id, Req 누구작업)
* ${'`'}target_table${'`'} (Varchar(50), Req 대상테이블명)
* ${'`'}action_type${'`'} (Varchar(10), Req INSERT/UPDATE/SELECT)
* ${'`'}detail_log_json${'`'} (Text, Req 변경전후 JSON저장, R7,R18)
* ${'`'}exec_time${'`'} (Datetime, KST자동생성)

### contracts_tenants (계약-임차인 연결테이블 - many-to-many 중계)
* ${'`'}contract_id${'`'} (Integer, FK -> contracts.id, Req)
* ${'`'}tenant_contact_id${'`'} (Integer, FK -> contacts.id, Req 임차인FK)

## 3. INTERFACE_MAPPING
* [A] 부동산 관리: ${'`'}buildings${'`'} & ${'`'}rooms${'`'} 등록, 주소 검색 (${'`'}LIKE${'`'}), 수정 시 R8 버전관리 적용.
* [B] 계약서 관리: (1)임차인정보탭→contacts.company_or_name+representative_name+NN-NNNN-NNNN입력→자동INSERT,(2)계약조건탭→lease_type/deposit_amount/monthly_rent/start_date/end_date 입력,(3)문서업로드탭→신분증사본·사업자등록증사본·계약서원본 documents_json저장.모든고유번호(KFK매핑)은DB에서만연동된UI화면에는노출안됨.상시고정뷰어노출.
* [C] 계약자 관리: ${'`'}contacts.company_or_name${'`'}, ${'`'}representative_name${'`'} 필수, 연락처 ${'`'}NN-NNNN-NNNN${'`'} 유효성 검증 적용.
* [D] 공과금 검침/고지: 양방향 멀티 입력 UI. 당월 검침 등록 시 사용량 및 요금(${'`'}bills.amount${'`'}) 실시간 파생 생성 연동.
* ${'`'}[E] 월세 납입${'`'}: 수납 요약, 보증금 반환 정산, ${'`'}bills.is_paid${'`'} 수납 확인 처리 및 미납 리스트 자동 추출.
* [F] 시설 유지보수: 파손 신고 접수, 상태값 변경 및 ${'`'}incidents.estimated_cost${'`'} 수리비 추적 정산.
* [G/H/I] 통합 실무 대시보드: 월세 총합/만기/갱신 현황 통합 시각화. 행별 메모장(${'`'}<input class="ledger-memo-input">${'`'}) 변경 시 ${'`'}onChange${'`'} -> ${'`'}POST /api/v1/memos${'`'} 자동 저장 (R35). 권한별 차등 격리.
* [J] 팀원 관리: ${'`'}team_management.html${'`'}, 구형 이메일 칸 제거, 사번 식별자 고정, 패스워드 최소 6자 검증 적용 (R40).
`;