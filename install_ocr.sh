#!/usr/bin/env bash
# install_ocr.sh - 계약서/신분증/여권 OCR 기능용 오프라인 엔진 설치
# 지원: macOS(Homebrew) / Ubuntu·Debian(apt)
# 설치 항목: tesseract + 한글데이터(kor) + poppler(PDF변환) + python 패키지
set -e
echo "=== 부동산관리시스템 OCR 엔진 설치 ==="

install_mac() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "[!] Homebrew가 필요합니다: https://brew.sh 설치 후 다시 실행하세요."; exit 1
  fi
  brew install tesseract tesseract-lang poppler
}

install_debian() {
  sudo apt-get update
  sudo apt-get install -y tesseract-ocr tesseract-ocr-kor poppler-utils
}

OS="$(uname -s)"
case "$OS" in
  Darwin) install_mac ;;
  Linux)
    if command -v apt-get >/dev/null 2>&1; then install_debian
    else echo "[!] apt 계열이 아닙니다. tesseract, tesseract-ocr-kor, poppler 를 배포판 패키지매니저로 설치하세요."; exit 1; fi ;;
  *) echo "[!] 지원하지 않는 OS: $OS"; exit 1 ;;
esac

echo "--- python 패키지 (선택: 없어도 CLI로 동작) ---"
python3 -m pip install --user pytesseract Pillow pdf2image passporteye 2>/dev/null || \
python3 -m pip install --break-system-packages pytesseract Pillow pdf2image passporteye || true

echo
echo "=== 설치 검증 ==="
command -v tesseract >/dev/null && tesseract --version | head -1 || echo "tesseract 미검출"
echo "설치된 언어:"; tesseract --list-langs 2>/dev/null | grep -E "kor|eng" || echo "  (언어 확인 실패)"
command -v pdftoppm >/dev/null && echo "poppler(pdftoppm) OK" || echo "poppler 미검출"
echo
echo "완료. 'kor' 이 목록에 보이면 한글 계약서 OCR 준비 끝입니다."
echo "서버를 재시작한 뒤 계약서(B) 화면에서 문서 업로드 → [OCR 채우기] 를 사용하세요."
