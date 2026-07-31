#!/bin/bash
# ============================================================
#  대림빌딩 관리 프로그램 — 오렌지파이 서버 업데이트
#  더블클릭하면 실행됩니다.
#
#  ★ 현장 자료(계약·수납·검침)는 절대 건드리지 않습니다.
#    DB, 계약서 스캔, 백업은 아예 보내지 않기 때문입니다.
# ============================================================

SRC="$HOME/rental-v2-online/"
PI="uglywolf@100.114.91.81"

clear
echo ""
echo "  =============================================="
echo "   오렌지파이 서버 업데이트"
echo "  =============================================="
echo ""
echo "   보내는 곳 : 이 맥의 rental-v2-online 폴더"
echo "   받는 곳   : 오렌지파이 (100.114.91.81)"
echo ""
echo "   보내지 않는 것 (현장 자료 보호)"
echo "     - 입력한 자료 (building_manager.db)"
echo "     - 계약서 스캔 (uploads)"
echo "     - 자동 백업 (_backups)"
echo "     - 백업 경로 설정 (drive_backup_path.txt)"
echo ""
read -r -p "   진행할까요? (엔터=진행 / n=취소) " ANS
if [ "$ANS" = "n" ] || [ "$ANS" = "N" ]; then
  echo ""; echo "   취소했습니다."; echo ""
  read -r -p "   엔터를 누르면 창이 닫힙니다. "
  exit 0
fi

echo ""
echo "  ----------------------------------------------"
echo "   1/3  서버가 살아있는지 확인"
echo "  ----------------------------------------------"
if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "$PI" "echo ok" >/dev/null 2>&1; then
  echo ""
  echo "   [실패] 오렌지파이에 연결할 수 없습니다."
  echo ""
  echo "   확인해 보세요"
  echo "     1) 맥 위쪽 메뉴막대에서 Tailscale 이 켜져 있는지"
  echo "     2) 오렌지파이 전원이 들어와 있는지"
  echo ""
  read -r -p "   엔터를 누르면 창이 닫힙니다. "
  exit 1
fi
echo "   연결 정상"

echo ""
echo "  ----------------------------------------------"
echo "   2/3  프로그램 파일 보내기"
echo "  ----------------------------------------------"
rsync -a --delete-after \
  --exclude '.git' \
  --exclude '_backups' \
  --exclude 'uploads' \
  --exclude 'building_manager*.db' \
  --exclude '__pycache__' \
  --exclude '.claude' \
  --exclude 'drive_backup_path.txt' \
  "$SRC" "$PI:rental-v2-online/"
RC=$?

if [ $RC -ne 0 ]; then
  echo ""
  echo "   [실패] 파일을 보내지 못했습니다. (오류번호 $RC)"
  echo "   서버의 프로그램은 바뀌지 않았으니 그대로 쓰셔도 됩니다."
  echo ""
  read -r -p "   엔터를 누르면 창이 닫힙니다. "
  exit 1
fi
echo "   보내기 완료"

echo ""
echo "  ----------------------------------------------"
echo "   3/3  프로그램 다시 시작"
echo "  ----------------------------------------------"
ssh "$PI" "sudo systemctl restart rental" 2>/dev/null || ssh root@100.114.91.81 "systemctl restart rental"
sleep 3

if ssh "$PI" "systemctl is-active rental" 2>/dev/null | grep -q active; then
  echo "   정상 작동 중"
else
  echo "   [주의] 프로그램이 안 켜졌을 수 있습니다. 아래 자료 확인을 보세요."
fi

echo ""
echo "  ----------------------------------------------"
echo "   현장 자료가 그대로 있는지 확인"
echo "  ----------------------------------------------"
ssh "$PI" "cd ~/rental-v2-online && python3 -c \"
import sqlite3,os
if not os.path.exists('building_manager.db'):
    print('   [주의] 자료 파일이 없습니다')
else:
    c=sqlite3.connect('building_manager.db')
    q=lambda t: c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]
    print('   호실 %d개 / 계약 %d건 / 계약자 %d명' % (q('rooms'),q('contracts'),q('contacts')))
\"" 2>/dev/null || echo "   확인하지 못했습니다"

echo ""
echo "  =============================================="
echo "   끝났습니다."
echo ""
echo "   프로그램 열기 :  http://100.114.91.81:8899"
echo "  =============================================="
echo ""
read -r -p "   엔터를 누르면 창이 닫힙니다. "
