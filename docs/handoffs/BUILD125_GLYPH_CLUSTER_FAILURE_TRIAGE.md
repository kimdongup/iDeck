# Build 125 — Glyph Cluster 실행 지시서: Build 124 CEF 첫 실패 규명

작성일: 2026-11-03 (HST)
저장소: https://github.com/kimdongup/iDeck
성격: 실행 지시서. Build 125의 빌드/설치/실기 성공을 의미하지 않음.
결과 보고 언어: 한국어.

## 0. 실행 목표

현재 Build 124 실기 화면은 connecting steam controls… 에서 정지한다. Build 124 IPA는 Xcode 빌드, 압축 검증, 실행파일 해시 일치와 실제 설치/실행을 통과했지만 Steam Big Picture UI가 시작되었다는 증거는 없다.

Glyph Cluster는 실제 Mac 로컬 소스를 읽고, 기존 변경을 보호하면서 가능한 코드 분석·계측·수정·테스트를 수행하라. 단순 계획만 작성하지 말고 가능한 작업을 실제로 끝내되, 없는 로그/실행/성공은 만들어내지 말 것.

**P0-CEF**: 첫 번째 CEF NOTREACHED의 실제 호출자, 실패 조건과 가능하면 모듈/RVA/stack 확보.
**P0-NATIVE**: FEX guard probe가 실제 컴파일/링크/실행되었는지 증명.
**P1-RESOURCES**: 여러 CEF 재시도에서 FD 및 FEX 예약 공간 회수 검증.
**BUILD125**: 근거 확보 후 최소 수정만으로 별도 IPA를 빌드하고 검증.

## 1. 현재 Build 124 로그 근거

사용자가 전달한 madeira-log(2).txt는 19,270줄, marker v0.1.20 (124). madeira-log.prev(1).txt는 14줄로 별도 초기 실행이며, 둘을 연속 로그로 합치지 말 것.

| 이벤트 | 건수 | 첫 행 |
|---|---:|---:|
| steam.exe launch | 1 | 1708 |
| steamwebhelper.exe launch (Crashpad 포함) | 4 | 3403 |
| CEF NOTREACHED check.cc(376) | 2 | 8177 |
| logging_chrome Invalid logging destination | 2 | 8235 |
| crashpad nonresponse | 1 | 14534 |
| FEX last code-buffer page mprotect warning | 161 | 1957 |
| store-noalias | 4 | 10386 |
| store-undecoded | 1 | 17503 |
| av-detail | 2 | 10387 |
| fdtrace CROSS! | 0 | — |
| fd-guard SKIP | 0 | — |
| build124-guard marker | 0 | — |
| BrowserReady | 0 | — |
| STATUS_NO_MEMORY | 0 | — |

시간 순서:
- L1708: steam.exe launch t+2.611s.
- L3403: 첫 steamwebhelper launch t+3.263s.
- L5521: Crashpad helper launch t+3.852s.
- L8177: 08:21:16.243 최초 CEF check.cc(376) NOTREACHED.
- L8235: 08:21:16.273 Invalid logging destination: file.
- L10386-L10388: 0x7200ae7e18에 write, no alias / fault.
- L14534: 08:22:18.320 crashpad server did not respond; self-terminating.
- L14897 / L15418: CEF helper 재시도 t+67.135s / t+70.575s.
- L16036: 08:22:22.581 두 번째 NOTREACHED.
- L17849-L17851: 후속 write fault.
- 마지막 L19270: phys footprint 3794 MB; guest VA 예약 사용률과 혼동하지 말 것.

FEX high virtual reservation snapshots (16 GiB arena): L1828 0%, L12158 6419 MiB / 39% / 781 views, L14698 6283 MiB / 38% / 765 views. Build123의 더 긴 38,510줄 캡처에서는 최대 94%와 16 MiB 할당 실패 6건이 있었지만 **이번 캡처가 더 짧으므로 문제가 해결됐다고 판단할 수 없다.**

미확인 사실/가설:
- CEF first failure 이전에도 FEX mprotect guard-page 경고가 다수 있다. 단순 경고 자체가 CEF 실패의 원인이라는 입증은 없다.
- CEF NOTREACHED는 공통 check.cc 출력 위치일 수 있다. 반드시 원래 실패 조건/호출 지점을 찾아야 한다.
- Steam launches refused: steamsysinfo, gldriverquery(64), vulkandriverquery(64), steamerrorreporter. 인과관계 미확인; 한 변수씩 격리 실험.
- FEX [build124-guard] 로그 0개이지만 구형 Failed to mprotect... 161개 발생한다. 새 패치가 미링크됐거나 로그 경로가 호출되지 않았을 수 있다. 코드와 바이너리로 판정.
- FD guard는 default OFF이며 CROSS!가 0건인 것은 늦은 재시도 구간 미수집 때문일 수 있다.
- JIT는 활성화 성공했다. 초기 allow-jit:false 출력은 활성화 전에 나온 값이므로 이를 주 장애라고 오판하지 말 것.
- CrBrowserMain 스레드가 select/NtDelayExecution에서 대기한 스냅샷만으로 브라우저 준비 상태를 증명할 수 없다.

## 2. 안전 경계

- Mac ROOT: /Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
- WORK: /Volumes/Repository/cokacremote/iDeckRuntimeLab
- Linux mount: /shared/iDeckRuntimeLab/iDeck
- 이전 로컬 HEAD는 574d24e로 보고됨. 최신은 반드시 git rev-parse로 확인.
- 공개 GitHub handoff branch는 실제 로컬 작업 브랜치와 일치하지 않을 수 있음.
- 루트/FEX/Wine/DXMT의 모든 미커밋 수정 보호. git reset --hard, git clean -fdx, 강제 체크아웃, submodule --force 갱신 금지.
- Build123/Build124 IPA와 DerivedData를 덮어쓰지 말 것. 외장 SSD에서 build125-artifacts 디렉터리 사용.
- 인증 정보, 기기 식별자, 서명 관련 파일, Steam 계정 데이터, 원본 사설 로그는 공개 GitHub에 업로드 금지.
- 코드 remote push, GitHub Actions, iPhone 설치/삭제/데이터 초기화는 각각 사용자 승인 후에만 실행.

## 3. Phase A — 무손실 체크포인트

Mac에서 먼저 다음을 실행하고, 결과를 새 evidence 폴더에 보관한다. Docker에서 작업하면 ROOT는 /shared 경로로 조정한다.

~~~bash
set -euo pipefail
ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
cd "$ROOT"
STAMP=$(date +%Y%m%d-%H%M%S)
EVIDENCE="$WORK/build125-artifacts/evidence/$STAMP"
mkdir -p "$EVIDENCE"
git rev-parse HEAD > "$EVIDENCE/head.txt"
git status --porcelain=v1 -uall > "$EVIDENCE/root-status.txt"
git diff --binary > "$EVIDENCE/root-working.diff"
git -C FEX status --porcelain=v1 -uall > "$EVIDENCE/fex-status.txt"
git -C FEX diff --binary > "$EVIDENCE/fex-working.diff"
git -C wine status --porcelain=v1 -uall > "$EVIDENCE/wine-status.txt"
git -C wine diff --binary > "$EVIDENCE/wine-working.diff"
git diff --check
git -C FEX diff --check
git -C wine diff --check
~~~

## 4. Phase B — CEF 첫 실패 실증 (P0)

1. 기존 CEF guest PC/RVA 및 stack 계측 구현(signal_arm64_ios.c 등)을 검색하고 활성화 조건을 조사. 이미 있는 진단 로직을 중복 개발하지 말 것.
2. 첫 CEF NOTREACHED 당시 pid/tid, libcef.dll guest PC 및 RVA, host translated PC, NTSTATUS/Win32 error, 실행 인수, 호출 스택을 가능한 범위에서 동시 수집.
3. Wine guest CEF debug.log를 같은 실행의 madeira-log.txt와 짝지어 수집. 기존 로그에는 전체 debug.log가 첨부되지 않았다.
4. logging_chrome invalid destination은 별도의 오류일 수 있음. 파일 로그 destination과 관련 CLI 옵션의 인과관계 확인; 원래 로그/조건을 무작정 숨기지 말 것.
5. crashpad failure는 첫 CEF NOTREACHED보다 늦다. 단일 정책 변수 A/B를 하되 최초 CEF 실패 원인을 Crashpad로 단정하지 말 것.
6. 실제 callsite를 심볼화하지 못하면 정확한 blocker와 재수집 명령을 기록할 것.

참고 수집 명령 (Mac, 설치 없음, DEV는 사용자 환경에서 devicectl로 확인):

~~~bash
DEV="<USER_DEVICE_ID>"
BUNDLE=com.kimdongup.ideck.build100
OUT="$HOME/Downloads/build124-cef-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
xcrun devicectl device copy from --device "$DEV" \
  --domain-type appDataContainer --domain-identifier "$BUNDLE" \
  --source Documents/madeira-log.txt --destination "$OUT/madeira-log.txt"
xcrun devicectl device copy from --device "$DEV" \
  --domain-type appDataContainer --domain-identifier "$BUNDLE" \
  --source Documents/wine/drive_c/Steam32BundleLab/bin/cef/cef.win7/debug.log \
  --destination "$OUT/cef-debug.log" || true
~~~

## 5. Phase C — FEX Native Guard 반영 여부 실증 (P0)

기존 FEX 변경 파일은 FEXCore/Source/Interface/Core/CPUBackend.cpp, FEXCore/include/FEXCore/Utils/ThreadPoolAllocator.h, Source/Windows/WOW64/Module.cpp; Wine 변경도 기존대로 유지.

- FEX guard probe 문자열과 실제 logging 조건을 코드를 통해 확인한다.
- 컴파일 명령과 object/static library 출처, 타임스탬프 및 해시를 확인한다.
- 빌드된 Madeira.app의 FEX 정적 링크 포함을 증명한다. 단순 소스 문자열 존재, preflight 13/13 PASS만으로 충분하지 않다.
- 기존 경고 161건에 guard marker 0건인 이유를 구체적으로 규명: stale binary / dead strip / log sink / 조건 불일치 / 다른 오류 경로.
- 경고만 없애기 위해 무조건 RWX 완화하거나 보호 검사 제거하지 말 것.

## 6. Phase D — FD 및 FEX 자원 회수 실험 (P1)

- FEX 16GiB 예약 영역의 PEB별 alloc/free와 16MiB view 회수를 장시간(최소 3–4분) 관측, Crashpad/CEF 재시도마다 live views 추적.
- FD cache의 stored=fd+1 및 real_fd=stored-1, FD_TYPE_INVALID 보정은 기존에 있는 수정. 동일 로직 중복 수정 금지.
- opt-in MADEIRA_FD_CACHE_CROSS_GUARD=1은 기본 OFF. A/B는 실제 기기 런타임 환경에서 토글되어야 하며 Mac 셸 export로는 기기 앱 환경에 들어가지 않을 수 있다.
- CROSS! 기록만으로 무조건 close가 잘못됐거나 ledger가 정확하다고 단정하지 말 것.
- CEF/Crashpad/FD/FEX 옵션을 여러 개 동시에 바꾸지 말 것.

## 7. Phase E — Build125 제작 (근거 확보 후)

- 기존 tools/dev-build101/build124-on-mac.sh를 먼저 읽고 dependency rebuild 경로 확인.
- 전용 DerivedData 및 Output 생성, Build124 IPA 그대로 보존.
- 필요할 경우 버전 125 / 0.1.21을 후보로 하되 실제 프로젝트 규칙 확인.
- 변경 native code를 정말 재컴파일·재링크한 증거를 남기고, xcodebuild PASS, 앱 codesign, IPA ZIP CRC, version, IPA↔app executable SHA-256, i386/ARM64 PE imports 및 라이브러리 export PASS를 검증.
- IPA 생성은 Steam Big Picture 성공과 다르다. iPhone 설치 및 실행은 사용자 별도 승인 없이는 하지 말 것.

## 8. 최종 통과 게이트

- A0: 기존 작업 트리 보존 + 복원 가능한 diff/체크포인트.
- A1: 최초 CEF 실패의 원본 호출 위치/원인 또는 구체적 진단 한계.
- A2: FEX Guard native compile/link/런타임 도달 여부 증명.
- A3: 자식 프로세스 종료 후 FEX/FD 회수 정량 검증.
- A4: 새 IPA를 만든 경우 version/signature/hash/ZIP/import 검증.
- A5: 실기 BrowserReady, Steam Big Picture 표시, 터치/패드 입력 수락.

## 9. 산출물과 중단 시 재개

Mac 외장 SSD build125-artifacts 디렉터리에 다음 파일을 작성하라:
- BUILD125_EXECUTION_REPORT.md
- BUILD125_CEF_FIRST_FAILURE.md
- BUILD125_NATIVE_LINKAGE.md
- BUILD125_VALIDATION.json
- BUILD125_NEXT_ACTION.md
- 명령 및 런타임 로그, 수정 파일 목록, 해시.

각 파일에는 실제 확인된 출력과 추정/가설을 구별하고, 마지막 HEAD, branch, dirty status, 남은 블로커, 다음 실행 명령을 기록한다.

## 10. 로컬 작업을 바꾸지 않고 문서 가져오기

브랜치 병합 또는 git pull 대신 git fetch와 git show를 사용한다.

~~~bash
ROOT=/Volumes/Repository/cokacremote/iDeckRuntimeLab/iDeck
WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
git -C "$ROOT" fetch origin handoff/build124-glyph-cluster-20261103
mkdir -p "$WORK/build125-artifacts/handoff"
git -C "$ROOT" show FETCH_HEAD:docs/handoffs/BUILD125_GLYPH_CLUSTER_FAILURE_TRIAGE.md > "$WORK/build125-artifacts/handoff/BUILD125_GLYPH_CLUSTER_FAILURE_TRIAGE.md"
~~~

**Glyph Cluster, 지금 Phase A → B → C 순서로 실행하라. 실증 자료가 있으면 수정과 테스트까지 진행하고, 없으면 정확한 재현·수집 방법과 blocker를 보고하라.**