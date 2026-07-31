# 오렌지파이 서버 구축 — 작업 지시서 (통합판)

새 세션에서 이 작업을 논의할 때 **이 문서부터** 읽으세요.
프로그램 전반의 배경은 `CLAUDE.md` 에 있습니다.

> 2026-07-31 통합: 데스크탑앱에서 만든 지시서 + 기존 인수인계 문서를 하나로 합치고,
> 실제 코드(`db.py`, `server.py`, `.gitignore`)와 대조해 사실관계를 바로잡았습니다.

---

## ✅ 구축 완료 상태 (2026-07-31 밤, 집에서 세팅 완료)

**1~7단계 끝났습니다. 남은 것은 8단계(건물 반출·실데이터 이관)뿐입니다.**

| 항목 | 값 |
|---|---|
| 호스트명 | `rental` (Orange Pi Zero 2W, Armbian Debian 13 Trixie, 커널 6.18.40-current-sunxi64) |
| 집 LAN 주소 | `192.168.0.233` (건물로 가면 바뀜 — 신경쓰지 말 것) |
| **Tailscale 주소** | **`100.114.91.81`** ← 어디서든 이 주소. 건물로 가도 그대로 |
| 접속 주소 | **http://100.114.91.81:8899** |
| 계정 | `uglywolf` (sudo), root SSH는 맥의 공개키로 무암호 접속 |
| 저장소 | microSD 64GB, 첫 부팅에 58G로 자동 확장됨 (1.3G 사용) |
| RAM | 3.8Gi |
| 프로그램 위치 | `/home/uglywolf/rental-v2-online` (코드만. **DB·uploads는 아직 비어 있음**) |
| 자동시작 | `systemd` 서비스 `rental.service` — 부팅 자동실행 + 죽으면 5초 후 재시작 |
| 로그 보기 | `journalctl -u rental -f` |

### Tailscale 노드

| 이름 | 주소 |
|---|---|
| `rental` (오렌지파이) | 100.114.91.81 |
| `lee-macstudio` (맥) | 100.121.228.34 |
| `raspberrypi` (집 백업서버) | 100.104.174.40 |

**MagicDNS는 끄고(`--accept-dns=false`) IP로 씁니다.** 라즈베리파이의 DNS 설정을 건드리지 않기 위한
선택이라, 이름(`rental`)으로는 안 풀립니다. **IP를 쓰세요.**

### 백업 (7단계 — 동작 확인됨)

- 집 라즈베리파이가 **매일 03:30** 에 오렌지파이에서 당겨옵니다(pull).
- 스크립트: 라즈베리파이의 `/home/uglywolf/부동산백업_가져오기.sh`
- 목적지: **`/mnt/USB32G/data/부동산백업/`** (32GB exFAT, `db/` 와 `uploads/` 로 나뉨)
- 기록: 같은 폴더의 `백업기록.txt` — **날짜가 오늘이 아니면 백업이 멈춘 것**
- 접속 순서: Tailscale IP(`100.114.91.81`) → 실패하면 집 LAN(`192.168.0.233`)
- exFAT은 권한 개념이 없어 `rsync -rt --no-perms --no-owner --no-group` 를 씁니다 (`-a` 쓰면 에러)
- ⚠️ **라즈베리파이의 sshd/SFTP 설정은 절대 건드리지 말 것** — 과거에 `uglywolf` SSH가 끊긴 사고가
  있었습니다. 이 설계는 라즈베리파이에서 SSH 클라이언트만 쓰므로 sshd를 만질 필요가 없습니다.
- 참고: 라즈베리파이에는 2.8TB 디스크(`/mnt/samba`)도 있습니다. 계약서가 많이 쌓이면 목적지를
  그쪽으로 바꾸는 편이 낫습니다 (스크립트의 `DEST` 한 줄).

### 이번에 겪은 함정 (다음에 또 만날 것)

- Armbian Imager에 **First-Boot 프로필 화면이 없었다** → SD의 ext4에 직접 써넣어 해결.
  `brew install e2fsprogs` 후 `debugfs -w` 사용. 맥에서 SD 접근은 **sudo 필수**(사용자가 실행해야 함).
- 이 이미지는 **NetworkManager가 없다**. `nmcli`/`nmtui` 없음.
  네트워크는 **netplan + systemd-networkd + wpa_supplicant**. WiFi는 `/etc/netplan/30-wifis-dhcp.yaml`.
- 무선 인터페이스 이름을 확정하려고 `/etc/systemd/network/98-wlan0.link` 로 `wlan0` 고정.
- **WiFi 절전 끄기는 이미지에 이미 포함**되어 있다 (`10-wifi-disable-powermanagement.rules`).
- `armbian-firstlogin` 마법사는 `/root/.not_logged_in_yet` 을 읽지만 **tty가 있어야만** 돌고,
  SSH로 실행하니 응답 없이 멈췄다 → **마법사를 버리고 `useradd`·`timedatectl` 로 직접 설정**했다.
- 권한 없는 `nmap -sn` 은 열린 포트가 거의 없는 기기를 "꺼짐"으로 판정한다 →
  기기 찾기는 **공유기 관리화면**이 가장 정확했다. (`nmap -p 22 --open` 은 쓸 수 있음)
- 집 네트워크가 **두 대역/두 대역폭으로 갈려 있다**. Chrome에서 `ERR_ADDRESS_UNREACHABLE` 이
  났지만 사파리에서는 접속됐다. Tailscale 주소를 쓰면 이 문제가 사라진다.

---

## 왜 하려는가

임대인(이은석)이 대림빌딩까지 **30~40km를 오가며** 프로그램을 확인하고 있습니다.
지금은 맥에서 터미널로 수동 실행 중이라 **창을 닫으면 서버가 꺼지고, 맥이 켜져 있어야만** 동작합니다.
현장에 항상 켜져 있는 작은 서버를 두고 **집에서 접속**하는 것이 목표입니다.

## ⭐ 작업 장소 — 집에서 다 만들고, 건물에는 완성품을 가져간다

사용자가 오렌지파이를 **집에서 세팅한 뒤 대림빌딩으로 가져갑니다.** 그래서 순서가 이렇습니다.

| 집에서 (1~7단계 대부분) | 건물에서 |
|---|---|
| 굽기, 첫 부팅, SSH 진입, WiFi 절전 끄기, 업데이트 | **전원 꽂기. 끝.** |
| 프로그램 복사 + 8899 확인 (집 LAN이 빨라 유리) | (Tailscale 덕분에 IP 탐색 불필요) |
| systemd 자동시작 등록 | 필요시 공유기 고정IP 예약 (MAC은 집에서 미리 확보) |
| **Tailscale 설치·로그인** ← 가장 중요 | |
| 현장 WiFi를 `nmtui` 로 추가 등록 | |

- 굽기 프로필의 WiFi는 **집 WiFi**입니다. 현장 WiFi를 넣으면 집에서 진입할 수 없습니다.
- NetworkManager는 WiFi를 여러 개 저장해두고 잡히는 쪽에 자동 연결합니다.
  집 WiFi를 지우지 않으므로 나중에 집으로 다시 가져와도 그대로 동작합니다.
- **Tailscale을 집에서 미리 깔아두면 건물의 IP를 몰라도 접속됩니다.**
  원래 3단계 최대 관문이던 "헤드리스로 IP 찾기"가 사라집니다.

## 사용자 상황 (먼저 읽을 것)

- 사용자는 터미널 명령어에 익숙하지 않습니다. **실행 전에 무엇을 왜 하는지 한 줄로 설명**하고 진행하세요.
- 직접 타이핑하게 하지 말고, 가능한 작업은 Claude Code가 직접 실행하세요.
- 모니터·키보드를 오렌지파이에 연결할 수 없습니다. **처음부터 끝까지 헤드리스**로 진행합니다.
- 현장에 유선랜을 쓸 수 없습니다. **WiFi 전용**입니다.
- 각 단계마다 사용자가 눈으로 확인할 수 있는 결과를 만들고 다음으로 넘어가세요.

---

## 하드웨어 / 환경

| 항목 | 내용 |
|---|---|
| 보드 | Orange Pi Zero 2W (Allwinner H618, RAM 4GB) — 실물 보유 |
| 저장소 | microSD 64GB (Armbian Debian 13 Trixie Minimal / CLI) |
| 네트워크 | **WiFi 전용** (보드에 유선 포트 없음). 무선칩 AW859A = Unisoc UWE5622 |
| 용도 | 대림빌딩 74개 호실 임대 관리, 직원 2명 동시 사용 |
| 집 서버 | 라즈베리파이 별도 운영 (Debian 13 arm64, 유선 `192.168.75.125`, 계정 `uglywolf`, SSH 키 `id_ed25519_remote`), **USB 32GB 저장소** |
| 설치 도구 | Armbian Imager (맥 다운로드 폴더에 `Armbian.Imager_2.0.2_aarch64.dmg` 있음) |

### 확인이 필요한 준비물

- [ ] microSD 카드 리더기 (맥에 꽂을 것)
- [ ] USB-C 전원 어댑터
- [ ] 방열판 (부착 후 세워서 배치 — 자연대류)

---

## 먼저 결정할 것 ⭐

**현장 윈도우 PC를 어떻게 할 것인가.**
오렌지파이와 윈도우 PC에서 프로그램을 둘 다 돌리면 SQLite 파일이 각각 갈라져
**어느 쪽이 진짜 데이터인지 알 수 없게 됩니다.**

→ 권장: **오렌지파이를 원본으로 삼고, 윈도우 PC의 자동시작(`install_service.bat`)은 해제.**
윈도우 PC는 브라우저로 오렌지파이에 접속하는 단말로만 씁니다.
이 결정을 사용자에게 먼저 확인한 뒤 4단계로 넘어가세요.

## 목표 상태

1. 건물에 두고 **24시간 무정지** — 잠자기 없음, 정전 후 자동 복구
2. 부팅하면 프로그램이 **자동 실행** (systemd 서비스)
3. **고정 IP** — 공유기에서 MAC 기준 DHCP 예약 (직원 북마크가 깨지지 않도록)
4. 집에서 접속 — **Tailscale** (포트포워딩·공인IP 불필요, 무료)
5. 백업이 **집 라즈베리파이 USB 32GB로** 자동 전송

---

## 기술 메모 (코드 확인 결과, 2026-07-31)

- 프로그램은 **파이썬 표준 라이브러리만** 씁니다. ARM 리눅스에서 그대로 돕니다.
  외부 패키지를 쓰는 건 `ocr_engine.py`의 `pytesseract` 하나뿐이고, `/api/v1/ocr` 호출 시에만
  import되며 계약서 화면에서 OCR은 이미 제거됐습니다. → **tesseract 설치 불필요.**
- 서버는 `0.0.0.0:8899` 로 바인딩합니다 (`server.py:221`). 포트는 그대로 **8899**.
- **DB는 SQLite 단일 파일** `building_manager.db` — 실물 **약 77KB**, 프로젝트 전체 9.5MB.
- 윈도우용 EXE(PyInstaller)는 오렌지파이엔 필요 없습니다. `python3 server.py` 로 직접 돌립니다.
- 포트 충돌 시 `input()` 대기 코드가 있지만 예외 처리되어 있어 systemd 아래에서도 문제 없습니다.

### 백업 코드가 이미 하는 일 (새로 만들지 말 것)

- `db.py:100-103` — **이미 SQLite 백업 API(`s.backup(d)`)를 사용**합니다. 쓰기 도중에도 일관된
  스냅샷이 나옵니다. `shutil.copy2` 는 실패 시 폴백일 뿐입니다.
  → `sqlite3` CLI로 `.backup` 을 다시 짜지 마세요. 의존성만 늘고 이득이 없습니다.
- `db.py:132-144` — 자동 백업은 **DB 파일이 변경됐을 때만** 5분 주기로 동작합니다. 조용한 날엔 안 씁니다.
  77KB × 롤링 30개이므로 **SD카드 마모는 사실상 무시 가능**. 주기 그대로 둡니다.
  백업을 tmpfs(RAM)로 옮기면 **정전 시 백업이 사라지므로 절대 금지** (`CLAUDE.md` 2번 원칙 위반).
- `db.py:31-50` — `drive_backup_path.txt` 에 적힌 경로를 우선 읽어 일자별 백업 1개를 그리로 복사합니다.
  자동탐지 후보는 `~/My Drive`, `G:\My Drive` 등 맥·윈도우 경로뿐이라 **리눅스에선 이 설정파일이 필수**입니다.
- `db.py:22` — `PC_BACKUP_DIR = ~/부동산백업`. 오렌지파이에선 같은 SD카드 안이라 의미가 없습니다.
  → 집 라즈베리파이 마운트 지점으로 바꿔야 진짜 이중화가 됩니다.

---

## 1~2단계 — Armbian Imager로 굽기 + WiFi 사전 설정

**사용자가 직접 GUI로 진행하는 단계.** Claude Code는 안내하고 결과만 확인할 것.

도구: **Armbian Imager** (https://imager.armbian.com) — macOS .dmg, Apple Silicon 지원

1. Armbian Imager 설치 후 실행
2. 제조사 `Orange Pi` → 보드 `Orange Pi Zero2W` 선택
3. 이미지: **Debian 13 Trixie / Minimal (CLI)** (약 291MB, 커널 current 6.18.40)
   - Ubuntu Resolute Xfce는 데스크톱판이므로 **선택하지 말 것**
4. **First-Boot Setup 프로필**에 입력 — 이게 이 단계의 핵심
   - 네트워크: **집 WiFi** SSID / 비밀번호 (2.4GHz 권장)
     ⚠️ **현장 WiFi를 넣으면 안 됩니다.** 세팅을 집에서 하기 때문에, 집 WiFi가 아니면
     부팅 후 네트워크에 붙지 못해 SSH 진입로가 없습니다. 현장 WiFi는 6단계에서 추가합니다.
   - 사용자 계정 및 비밀번호
   - 시간대 `Asia/Seoul`, 로케일
5. SD카드 선택 후 굽기 (자동으로 SHA 검증까지 수행)

이 방식이면 ext4 접근, debugfs, 라즈베리파이 경유, 모니터·키보드가 **전부 불필요**합니다.
부팅하면 보드가 스스로 WiFi에 붙고 SSH 접속 대기 상태가 됩니다.

### ⚠️ 2026-07-31 실제 결과 — First-Boot 프로필이 없었다

사용자가 구운 Armbian Imager 버전에는 **First-Boot Setup 화면이 없었습니다.** 그냥 굽고 끝.
→ SD에 WiFi 정보가 들어가지 않았으므로 **부팅해도 집 WiFi에 붙지 못합니다.** 아래 대체 경로로 진행하세요.

현재 상태: SD는 맥 본체 카드슬롯에 삽입됨 = `/dev/disk5` (63.9GB, `disk5s1` = Linux 1.5GB, 첫 부팅 전).
`e2fsprogs` 는 **아직 미설치**. brew 는 `/opt/homebrew/bin/brew` 에 있음.

**다음 세션에 할 일 (5분)**

1. `brew install e2fsprogs`
2. `/tmp/armbian_first_run.txt` 를 만들되 **비밀번호 칸은 비워두고**, 사용자가 텍스트 편집기로
   직접 채우게 한다 (대화에 비밀번호가 남지 않게)
3. `debugfs -w /dev/disk5s1` 로 `/boot/armbian_first_run.txt` 에 써넣는다
4. 오렌지파이에 꽂고 전원 → 집 네트워크에서 IP 탐색 → SSH 진입 (3단계로 이어짐)

넣을 내용(집 WiFi 기준):
```
FR_general_delete_this_file_after_completion=1
FR_net_change_defaults=1
FR_net_wifi_enabled=1
FR_net_wifi_ssid='집WiFi이름'
FR_net_wifi_key='여기에_비밀번호'
FR_net_wifi_countrycode='KR'
```

안 되면 **SD를 집 라즈베리파이(`192.168.75.125`)에 카드리더로 물려** 네이티브 마운트 후 같은 파일을 쓰면 확실합니다.

> **대체 경로 (참고)** — 원래 이 항목은 First-Boot 프로필이 동작하지 않을 때의 예비안이었습니다.
> Allwinner 계열 Armbian은 단일 ext4 파티션이라 macOS에서 볼륨이 보이지 않습니다.
> (a) SD카드를 카드리더로 집 라즈베리파이(`192.168.75.125`)에 물려 네이티브 마운트 후
> `/boot/armbian_first_run.txt` 작성, 또는 (b) 맥에서 `brew install e2fsprogs` 후 `debugfs -w`.
> macOS가 "읽을 수 없는 디스크" 경고를 띄우면 반드시 **"무시"** — 초기화를 누르면 이미지가 날아갑니다.

## 3단계 — 첫 부팅과 WiFi 확인

**여기가 최대 관문.** WiFi가 안 잡히면 헤드리스로는 진입로가 없습니다.

- 공유기 관리 화면이나 `arp -a` / `nmap` 으로 오렌지파이 IP 확인 → SSH 접속
- `wlan0` 이 안 잡히는 경우: **이 보드용 Armbian vendor 커널 이미지가 없습니다**(current 2종이 전부).
  대안은 둘뿐입니다.
  1. **USB 무선 동글** — 가장 확실하고 저렴. 리눅스 지원 확인된 칩셋으로 고를 것
  2. 오렌지파이 공식 BSP 이미지 — AW859A(UWE5622) 드라이버가 벤더 커널에 포함. 다만 관리가 부실함

접속 성공 후 즉시:

- ~~WiFi 절전 끄기~~ → **이미지에 이미 들어 있습니다.**
  `/etc/udev/rules.d/10-wifi-disable-powermanagement.rules` 가 이미지에 포함되어 있어
  별도 설정이 필요 없습니다. (확인만 하면 됨: `iw wlan0 get power_save`)
- 공유기에서 MAC 기준 **고정 IP** 할당
- 시스템 업데이트, 타임존은 preseed로 `Asia/Seoul` 설정됨 — `timedatectl` 로 확인

## 4단계 — 프로그램 이관

> ⚠️ **진짜 데이터는 맥이 아니라 USB 메모리 스틱에 있습니다.**
> 현장 운영 방식: 스틱을 현장 윈도우 PC에 꽂고 EXE 실행 → `building_manager.db`, `uploads/`,
> `_backups/` 가 **전부 스틱 안**에 있습니다. 맥의 `~/rental-v2-online` 은 **개발·테스트용**이고
> `uploads/` 에 테스트 파일(`test contract.png`)이 들어 있습니다.
> → **코드는 맥(git)에서, 데이터(DB·uploads)는 스틱에서** 가져와야 합니다. 섞으면 테스트
> 데이터가 실서버에 올라갑니다.

- **`git clone` 만으로는 안 됩니다.** `.gitignore` 가 `uploads/`(계약서·신분증 스캔)와 `_backups/` 를
  제외하고, `building_manager.db` 는 추적 중이라 **마지막 커밋 시점의 옛 DB**가 들어옵니다.
- 코드: 맥의 `~/rental-v2-online` 을 `rsync -av` 로 복사 (또는 clone)
- 데이터: **스틱의 `building_manager.db` 와 `uploads/` 로 덮어쓰기** — 이게 진본입니다
- 복사 후 **호실 수(74)와 계약 건수를 화면에서 눈으로 대조** — 여기서 확인 안 하면 나중에 못 찾습니다
- `python3 server.py` 수동 실행 → 포트 8899 응답 확인
- 같은 네트워크의 다른 PC에서 `http://<오렌지파이IP>:8899` 접속 확인

## 5단계 — systemd 서비스 등록

- `server.py` 를 systemd 서비스로 등록 (부팅 시 자동 실행, 비정상 종료 시 자동 재시작)
- 유닛에 `Environment=LANG=C.UTF-8`, `Environment=PYTHONUNBUFFERED=1` 를 넣을 것
  — 백업 폴더명·업로드 파일명이 한글이라 로케일이 C면 로그가 깨집니다
- 정전 후 복구 확인
- 이걸로 "터미널 창 닫으면 꺼지는" 기존 문제가 해결됩니다

## 6단계 — Tailscale + 현장 WiFi 등록 (아직 집에서)

**현장 WiFi 추가** — 건물에 가져갔을 때 스스로 붙게 만드는 단계.

> ⚠️ **이 이미지에는 NetworkManager가 없습니다.** `nmcli`·`nmtui` 둘 다 없고
> 네트워크 스택은 **systemd-networkd + wpa_supplicant + netplan** 입니다.
> (`/etc/NetworkManager/conf.d` 는 armbian-config가 남긴 설정 잔재일 뿐입니다)

- `/etc/netplan/30-wifis-dhcp.yaml` 의 `access-points:` 아래에 현장 SSID를 **한 벌 더** 추가합니다.
  netplan은 여러 AP를 나열하면 잡히는 쪽에 붙습니다.
  ```yaml
        access-points:
          "집SSID":
            password: "..."
          "현장SSID":
            password: "..."
  ```
- 파일 권한은 **600** 유지 (netplan이 경고합니다)
- `sudo netplan apply` 후 `networkctl status wlan0` 으로 확인
- 숨김 SSID면 해당 AP 아래에 `hidden: true`
- `ip link show wlan0` 으로 **MAC 주소를 받아 적어둘 것** (현장 공유기 고정IP 예약용)

**Tailscale** — 건물 IP를 몰라도 접속되게 만드는 단계.

- 오렌지파이와 집 맥(그리고 필요하면 집 라즈베리파이)에 Tailscale 설치
- 각 기기가 `100.x.x.x` 주소를 받으면 집에서 `http://100.x.x.x:8899` 로 바로 접속
- **8899 포트포워딩은 하지 마세요.** 과거 공유기 DMZ 노출로 SSH에 3일간 960회 공격을 받은 이력이 있습니다.
  외부 공개가 꼭 필요해지면 그때 사용자와 따로 상의할 것

## 7단계 — 백업을 집 라즈베리파이 USB 32GB로

용량은 전혀 문제가 안 됩니다. 일자별 백업 77KB × 30일 = **약 2.3MB**.
계약서 스캔이 74개 호실 전부 쌓여도 수백 MB 수준이라 32GB면 수년치가 들어갑니다.

**권장 방식 — 집 라즈베리파이가 가져가는 "당겨오기(pull)"**

집 라즈베리파이의 cron이 하루 1회 오렌지파이에서 백업을 당겨옵니다.

```
rsync -av -e ssh <오렌지파이Tailscale주소>:~/rental-v2-online/_backups/daily/  /mnt/usb32/부동산백업/
rsync -av -e ssh <오렌지파이Tailscale주소>:~/rental-v2-online/uploads/         /mnt/usb32/부동산백업/uploads/
```

왜 pull이 나은가:
- 현장 서버가 **집 네트워크 접속 정보를 갖고 있지 않습니다.** 현장 장비가 털려도 집 백업은 안전하고,
  집에 쌓인 백업을 지울 수도 없습니다.
- 집 라즈베리파이는 항상 켜져 있으니 스케줄러를 맡기기에 적합합니다.
- **SSH 키 인증만** 사용 (기존 `id_ed25519_remote` 활용). 비밀번호는 쓰지 않습니다.

**대안 — 오렌지파이가 보내는 방식**: 오렌지파이에서 sshfs로 집 라즈베리파이를 마운트하고
`drive_backup_path.txt` 에 그 경로를 한 줄 적으면 일자별 백업이 자동으로 넘어갑니다.
다만 마운트가 끊기면 `backup_to_drive()` 가 **조용히 통과**하므로(예외를 먹습니다)
백업이 안 되고 있어도 아무 표시가 없습니다. 쓰려면 마운트 감시를 따로 붙여야 합니다.

**정리**: 주 백업 = 집 라즈베리파이 USB 32GB(pull). 구글드라이브는 나중에 여유 있을 때
`rclone` 마운트 경로를 `drive_backup_path.txt` 에 적는 것으로 추가 (필수는 아님).

또 `db.py:22` 의 `PC_BACKUP_DIR` 는 오렌지파이에선 같은 SD카드라 무의미하니,
불필요한 중복 쓰기를 없애려면 이 경로를 조정하세요.

업로드 성공/실패를 사용자가 **어디서 눈으로 확인하는지** 알려주고 끝내세요.

## 8단계 — 건물로 가져가서 실전 전환

집에서 복사한 데이터는 **복사한 시점의 것**입니다. 그동안 현장 윈도우 PC에서 입력이 계속되면
두 벌이 갈라집니다. 전환 순서를 반드시 지키세요.

1. 오렌지파이를 건물에 두고 전원 연결 → WiFi 자동 접속, 프로그램 자동 실행 확인
2. **스틱의 EXE를 종료** (더 이상 입력이 들어오지 않게)
3. **스틱의 최신 `building_manager.db` 와 `uploads/`** 를 오렌지파이로 **한 번 더 덮어쓰기**
4. 호실 수(74)·계약 건수·최근 입력 내용을 화면에서 눈으로 대조
5. 확인된 뒤에 윈도우 PC의 자동시작(`install_service.bat`)을 해제 — 이때부터 오렌지파이가 원본
6. 직원에게 새 주소를 안내하고 북마크 교체
7. **스틱은 뽑아서 "비상용 / 전환일 2026-__-__" 라고 적어 보관.** 꽂아두면 누군가 실행해
   데이터가 갈라집니다. 오렌지파이가 죽었을 때만 꺼내 쓰는 예비품입니다.

### EXE 재빌드는 필요한가

**아니오 — 오렌지파이로 이관하면 건너뛸 수 있습니다.** 오렌지파이는 EXE 없이 `python3 server.py`
로 돌기 때문에 최신 코드가 그대로 적용됩니다.
단, **이관 전까지는 계약서 원본 백업 수정(2026-07-31)이 현장에 적용되지 않습니다.**
그동안의 보호책은 **스틱의 `uploads/` 폴더를 손으로 복사해 두는 것** 하나뿐입니다.
현장 운영을 오래 유지해야 한다면 윈도우에서 PyInstaller(**Python 3.13**)로 재빌드 후
`UPDATE_apply.bat` 으로 적용하세요.

## 9단계 — 검증

- 오렌지파이 전원을 뽑았다 다시 꽂아 자동 복구 확인
- 직원 PC 2대에서 동시 접속 확인
- 집에서 Tailscale로 접속 확인
- 집 라즈베리파이 USB에 백업 파일이 **실제로 올라갔는지** 확인
- 온도: `cat /sys/class/thermal/thermal_zone0/temp` (1000으로 나눈 값이 ℃).
  며칠 관찰해 70℃ 미만이면 정상

---

## 주의사항

- **비밀번호를 파일이나 노션에 평문으로 기록하지 말 것.** 기존 노션 문서에 SFTP·계정 비밀번호가
  평문으로 남아 있고, 과거 DMZ 노출로 SSH에 3일간 960회 공격을 받은 이력이 있습니다. **SSH 키 인증만.**
- microSD는 수명이 있습니다. **백업은 반드시 집 라즈베리파이/외부로** 내보내세요.
- 정전 대비: 공유기와 함께 소형 UPS를 두는 것을 권할 수 있습니다.
- USB SSD는 불필요 — SQLite 단일 파일 워크로드이고 보드가 USB 2.0이라 이득이 없습니다.
- 오렌지파이는 방열판 부착 상태로 세워서 배치.
