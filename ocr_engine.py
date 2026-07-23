#!/usr/bin/env python3
"""
ocr_engine.py - 오프라인 OCR 모듈 (계약서/신분증/여권)
- 이미지/PDF -> 텍스트 (Tesseract, 한글 kor + eng)
- 표준 부동산임대차계약서 라벨 앵커 기반 필드 추출
- 여권 MRZ 파싱(있을 때), 신분증 기본 필드
- 엔진 미설치 시 graceful 안내 반환 (서버는 죽지 않음)
사람이 반드시 검토/수정하는 것을 전제로 '추정값 + confidence' 를 돌려준다.
"""
import os, re, subprocess, tempfile, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff')


# ---------------------------------------------------------------- 엔진 상태
def engine_status():
    """설치된 OCR 도구 상태를 확인한다."""
    tess = shutil.which('tesseract')
    langs = []
    if tess:
        try:
            out = subprocess.run([tess, '--list-langs'], capture_output=True, text=True, timeout=10)
            langs = [l.strip() for l in out.stdout.splitlines()[1:] if l.strip()]
        except Exception:
            pass
    poppler = shutil.which('pdftoppm') is not None
    try:
        import pytesseract  # noqa
        has_pytess = True
    except Exception:
        has_pytess = False
    return {
        'tesseract': bool(tess),
        'pytesseract': has_pytess,
        'poppler_pdf': poppler,
        'langs': langs,
        'has_korean': 'kor' in langs,
        'ready': bool(tess) and ('kor' in langs or 'eng' in langs),
    }


# ---------------------------------------------------------------- 텍스트 추출
def _pdf_first_pages_to_images(pdf_path, out_dir, max_pages=2, dpi=200):
    prefix = os.path.join(out_dir, 'ocrpage')
    subprocess.run(['pdftoppm', '-png', '-r', str(dpi), '-l', str(max_pages), pdf_path, prefix],
                   check=True, timeout=120)
    return sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.startswith('ocrpage')])


def image_to_text(img_path, lang):
    """tesseract 로 이미지 -> 텍스트. pytesseract 있으면 사용, 없으면 CLI."""
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(img_path), lang=lang)
    except Exception:
        out = subprocess.run(['tesseract', img_path, 'stdout', '-l', lang, '--psm', '6'],
                             capture_output=True, text=True, timeout=120)
        return out.stdout


def extract_text(path):
    """이미지/PDF -> OCR 텍스트. 엔진 상태와 함께 반환."""
    st = engine_status()
    if not st['ready']:
        return '', st
    lang = 'kor+eng' if st['has_korean'] else 'eng'
    ext = os.path.splitext(path)[1].lower()
    text = ''
    if ext == '.pdf':
        if not st['poppler_pdf']:
            return '', st
        tmp = tempfile.mkdtemp(prefix='ocr_')
        try:
            for img in _pdf_first_pages_to_images(path, tmp):
                text += image_to_text(img, lang) + '\n'
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    elif ext in IMAGE_EXTS:
        text = image_to_text(path, lang)
    return text, st


# ---------------------------------------------------------------- 유틸
def _digits(s):
    return re.sub(r'\D', '', s or '')


def mask_rrn(rrn):
    """주민등록번호 뒷자리 마스킹: 480910-1****** (개인정보 보호)"""
    m = re.search(r'(\d{6})[-\s]?(\d)\d{6}', rrn or '')
    if m:
        return '{}-{}******'.format(m.group(1), m.group(2))
    return rrn


def _find_amount_near(text, label_regex):
    """라벨 근처의 금액(콤마/원 포함) 숫자를 찾는다."""
    m = re.search(label_regex, text)
    if not m:
        return None
    window = text[m.start(): m.start() + 120]
    nums = re.findall(r'[\d][\d,]{2,}', window)
    nums = [int(_digits(n)) for n in nums if _digits(n)]
    nums = [n for n in nums if n >= 1000]
    return max(nums) if nums else None


def _norm_date(y, mo, d):
    try:
        return '{:04d}-{:02d}-{:02d}'.format(int(y), int(mo), int(d))
    except Exception:
        return None


# ---------------------------------------------------------------- 계약서 필드 추출
def extract_lease_fields(text):
    """표준 부동산임대차계약서에서 필드 추정. 각 필드에 confidence 부여."""
    f, conf = {}, {}

    def put(k, v, c):
        if v not in (None, '', []):
            f[k] = v
            conf[k] = c

    # 계약종류 (전세/월세) — 차임 존재하면 월세로 추정
    put('lease_type', '월세' if re.search(r'차\s*임', text) else '', 'low')

    # 소재지 (주소)
    m = re.search(r'소\s*재\s*지\s*[:\|]?\s*([^\n]+)', text)
    if m:
        put('host_address_full', m.group(1).strip(' :|'), 'medium')

    # 임대할부분(호실) — '임대할부분' 뒤 숫자
    m = re.search(r'임\s*대\s*할\s*부\s*분\s*[:\|]?\s*([0-9]{2,4})', text)
    if m:
        put('room_no', m.group(1), 'medium')

    # 금액 후보들: ₩표기 및 괄호 안 숫자 (엔진/한글유무 무관 폴백)
    won_amts = [int(_digits(x)) for x in re.findall(r'[₩WwＷ]\s*([\d]{1,3}(?:,\d{3})+)', text)]
    paren_amts = [int(_digits(x)) for x in re.findall(r'\(\s*([\d][\d,]{3,})', text)]  # 닫는 괄호 없어도 허용
    paren_amts = [n for n in paren_amts if 10000 <= n <= 99999999]

    # 보증금: 라벨근처 > ₩표기 최댓값
    dep = _find_amount_near(text, r'보\s*증\s*금')
    if dep is None and won_amts:
        dep = max(won_amts)
    if dep is None:
        big = [int(_digits(x)) for x in re.findall(r'[\d]{1,3}(?:,\d{3}){2,}', text)]
        big = [n for n in big if n >= 1000000]
        if big:
            dep = max(big)
    put('deposit_amount', dep, 'high' if dep else 'low')

    # 월차임: 라벨근처 > 괄호안 금액(보증금 제외) 최댓값
    rent = _find_amount_near(text, r'차\s*임')
    if rent is None:
        cand = [n for n in paren_amts if n != dep]
        if cand:
            rent = max(cand)
    put('monthly_rent', rent, 'medium' if rent else 'low')

    # 관리비 (특약 '월관리비 N만원')
    m = re.search(r'월\s*관리비\s*([\d]+)\s*만', text)
    if m:
        put('maintenance_fee', int(m.group(1)) * 10000, 'medium')

    # 기간: 존속기간 시작일 / 종료일
    dates = re.findall(r'(\d{4})\s*년?\s*(\d{1,2})\s*월?\s*(\d{1,2})?\s*일?', text)
    ymd = []
    for y, mo, d in dates:
        if 2000 <= int(y) <= 2100 and 1 <= int(mo) <= 12:
            ymd.append((y, mo, d or '1'))
    if ymd:
        # 인도일(시작)과 종료일 추정: 가장 이른 날짜 / 가장 늦은 날짜
        norm = sorted({_norm_date(*t) for t in ymd if _norm_date(*t)})
        if norm:
            put('start_date', norm[0], 'medium')
            put('end_date', norm[-1], 'medium')

    # 주민등록번호 (임대인=owner, 임차인=tenant 순서 추정) — 마스킹 저장
    rrns = re.findall(r'\d{6}[-\s]?\d{7}', text)
    rrns = [r.replace(' ', '') for r in rrns]
    if len(rrns) >= 1:
        put('owner_rrn_masked', mask_rrn(rrns[0]), 'high')
    if len(rrns) >= 2:
        put('tenant_rrn_masked', mask_rrn(rrns[1]), 'high')

    # 전화번호
    phones = re.findall(r'0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}', text)
    if len(phones) >= 1:
        put('owner_phone', phones[0].replace(' ', '-'), 'medium')
    if len(phones) >= 2:
        put('tenant_phone', phones[1].replace(' ', '-'), 'medium')

    # 특약사항 블록
    m = re.search(r'특\s*약\s*사\s*항([\s\S]{0,600})', text)
    if m:
        put('special_terms', m.group(1).strip()[:500], 'low')

    return f, conf


# ---------------------------------------------------------------- 여권 MRZ / 신분증
def extract_passport_fields(text):
    """여권 MRZ(P<...) 파싱: 영문 성/이름, 여권번호, 국적, 생년월일."""
    f, conf = {}, {}
    lines = [re.sub(r'\s', '', l) for l in text.splitlines() if l.strip()]
    mrz = [l for l in lines if l.startswith('P<') or re.match(r'^[A-Z0-9<]{30,}$', l)]
    if len(mrz) >= 2:
        l1, l2 = mrz[0], mrz[1]
        m = re.match(r'P<([A-Z]{3})([A-Z<]+)<<([A-Z<]+)', l1)
        if m:
            f['nationality'] = m.group(1)
            f['surname_en'] = m.group(2).replace('<', ' ').strip()
            f['given_names_en'] = m.group(3).replace('<', ' ').strip()
            conf['surname_en'] = conf['given_names_en'] = 'high'
        if len(l2) >= 20:
            f['passport_no'] = l2[0:9].replace('<', '')
            b = l2[13:19]
            if b.isdigit():
                f['birth_date'] = '20{}-{}-{} (세기 확인필요)'.format(b[0:2], b[2:4], b[4:6])
            conf['passport_no'] = 'high'
    return f, conf


def extract_id_fields(text):
    """주민등록증 기본 필드: 주민번호(마스킹), 이름 후보."""
    f, conf = {}, {}
    m = re.search(r'\d{6}[-\s]?\d{7}', text)
    if m:
        f['rrn_masked'] = mask_rrn(m.group(0).replace(' ', ''))
        conf['rrn_masked'] = 'high'
    return f, conf


# ---------------------------------------------------------------- 진입점
def run_ocr(path, doc_type='lease'):
    """파일 -> {engine, fields, confidence, raw_text, warnings}"""
    warnings = []
    if not os.path.exists(path):
        return {'error': '파일을 찾을 수 없습니다: {}'.format(path)}
    text, st = extract_text(path)
    if not st['ready']:
        return {
            'engine': st, 'fields': {}, 'confidence': {}, 'raw_text': '',
            'warnings': ['OCR 엔진이 설치되어 있지 않습니다. install_ocr.sh 로 tesseract(+kor)/poppler 를 설치하세요.']
        }
    if not st['has_korean']:
        warnings.append('한글 데이터(kor) 미설치 — 숫자/영문만 신뢰. 한글 라벨/성명 정확도 낮음. install_ocr.sh 실행 권장.')

    if doc_type == 'passport':
        fields, conf = extract_passport_fields(text)
    elif doc_type == 'id':
        fields, conf = extract_id_fields(text)
    else:
        fields, conf = extract_lease_fields(text)

    warnings.append('모든 값은 OCR 추정치입니다. 저장 전 반드시 원본과 대조해 확인/수정하세요.')
    return {
        'engine': st, 'doc_type': doc_type,
        'fields': fields, 'confidence': conf,
        'raw_text': text[:4000], 'warnings': warnings,
    }


if __name__ == '__main__':
    import sys, json
    p = sys.argv[1] if len(sys.argv) > 1 else ''
    dt = sys.argv[2] if len(sys.argv) > 2 else 'lease'
    print(json.dumps(run_ocr(p, dt), ensure_ascii=False, indent=2))
