# Gemini 2차 분석 지시 — 동일 UI 증상과 기존 분석 교정

사용자 보고: 최신 설치 실행 후에도 connecting steam controls… 상태가 이전과 같다. **새 설치의 실제 빌드 번호/새 로그는 아직 전달되지 않았다.** 따라서 Build125가 실제로 적용됐는지 단정하지 말 것.

## 변경된 분석 조건
- Build124 로그는 19,270줄이며 NOTREACHED 두 건이 있었다. 최초 guest-log tid=0080 / 시각 1103/182116.243, 두 번째 tid=01e4 / 시각 1103/182222.581. 둘 다 Invalid logging destination: file이 수십 밀리초 뒤 이어진다.
- 이전에 전달된 cef debug.log는 누적 이전 실행 기록이고 이 18:21/18:22 구간과 일치하지 않았다. 새 동일 세션 파일이 필요.
- Build124 mprotect 161회 대 [build124-guard] 0회. **소스 스냅샷에서 두 신규/구형 로그는 동일한 VirtualProtect 실패 if 분기에 같은 EFmt 채널로 연속 출력된다.** 소스-오브젝트-정적 archive-Mach-O-런타임 간 최신 코드 출처를 증명할 것. 단순 IPA 파일 버전=124나 marker 존재는 증거 부족.
- 기존 signal_arm64_ios.c의 CEF fatal tracer는 특정 INT3 guest RIP=0x6df3def4 및 session=1에 제한됨. check.cc(376)라는 로그 출력에는 일반적으로 SIGTRAP이 필요하지 않으므로 예외 handler만 계측할 경우 호출 스택을 확보하지 못할 수 있음.
- Gemini 1차 분석의 “상대방 PEB 종료→CROSS! 100% stale ledger” 판정은 과도하다. FD generation과 kernel FD lifecycle로 검증할 것.
- clean worktree이면 git diff=0이 정상. staged/untracked 백업과 git diff --binary는 별개.

## 이번 답변 요청
1. 최초 CEF NOTREACHED에 직접 대응하는 Guest log bridge/CEF log path 계측의 구현 위치 후보를, **실제 소스 확인 여부**를 분리하여 제시.
2. [build124-guard]가 기존 경고보다 앞서 실행되도록 작성돼 있음에도 0회인 가능한 원인을 evidence-first decision tree로 제시.
3. 새 장치 로그가 제출되면 build marker, event first timestamp, crash/BrowserReady를 비교하는 명확한 판정 기준.
4. 추가 변경 없이 수행할 수 있는 한 번의 Mac source + binary audit 명령과 한 번의 device log capture 명령 작성.
5. “새 패치 반영 확인 전 추가 Build 버전 증가/반복 설치 금지” 원칙 준수.

## 자료 범위
이 브랜치에는 경량 문서와 요약만 있다. 실제 소스를 읽고자 하면 사용자에게 build124-critical-source-20261103-055816.zip(0.9MB)을 별도로 요청할 것. 이 ZIP은 과거 소스 스냅샷이므로 최신 로컬 변경 여부는 확인할 수 없다. 사용자 개인 개발 자료는 공개 GitHub로 push 금지.

결과는 한국어. 관측/가설/미확인을 분리하고 추정 신뢰도를 실제 증거에 맞출 것.
