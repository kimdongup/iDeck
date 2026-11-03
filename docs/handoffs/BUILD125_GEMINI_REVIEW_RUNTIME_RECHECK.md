# Build125 — Gemini 분석 검토 및 동일 증상 재검증

작성 2026-11-03 HST. 이 문서는 실행 지시서이며 새 버전의 컴파일·설치 성공을 의미하지 않는다. 한국어로 보고한다.

## 상태

사용자가 Gemini 분석서를 제출하고 설치 실행 결과가 이전과 동일한 connecting steam controls… 상태라고 보고했다. 신규 실행의 build marker 및 신규 로그는 아직 제공되지 않았다. 따라서 Build125 소스가 실제 반영되었는지, 첫 CEF 오류도 동일하게 재현됐는지 판단할 수 없다.

## Gemini 분석: 타당점과 정정

1. check.cc(376) NOTREACHED 자체는 원래 CEF 실패 호출자를 알려주지 않는다. PID/TID/CLI, libcef.dll 모듈 RVA, 상위 스택, 직전 NTSTATUS/LastError와 해당 세션 debug.log를 확보하라.
2. Build123 약 38510줄과 Build124 19270줄은 시간 길이가 다르다. 단순 경고 수 감소를 개선으로 볼 수 없다.
3. Gemini의 “상대방 PEB가 종료됐으면 CROSS는 100% stale ledger”는 잘못된 단정이다. FD 재사용 세대, open/dup/close, fstat/dev/inode, PEB 생존 시점과 포인터 재사용까지 확인하라. 동일 inode도 교차 닫기를 단독 입증하지 않는다.
4. git diff 파일의 크기가 0이면 실패한다는 조건은 잘못됐다. clean worktree면 diff=0은 정상이다. staged/untracked와 하위 submodule dirty 상태는 별도 백업하라.
5. 단순 git diff --binary는 staged/untracked 파일을 모두 담지 못한다. 일괄 git apply -R을 안전한 복구로 가정하지 말라. 원본 스냅샷을 변경하지 않는 형태로 기록.
6. Build124 패키징 gate는 앱 번들을 재귀 grep해서 marker를 찾는다. 소스 또는 리소스에 문자열이 있어도 FEX 실행 경로에 최신 코드가 링크됐다는 증명은 아니다. Object/archive/Mach-O/runtime을 따로 검증.
7. check.cc(376) 메시지는 로그 출력을 의미하고 반드시 SIGTRAP 예외라는 증거는 없다. signal_arm64_ios.c에 예외 probe만 추가해도 일반 로그의 상위 호출자를 포착하지 못할 수 있다. 실제 guest logging bridge를 찾고, 해당 로그 이벤트의 원래 프로세스 및 호출자를 계측하라.
8. 기존에 제공된 debug.log는 여러 실행이 누적된 이전 파일이며 Build124의 1103/182116 및 1103/182222 타임스탬프 항목이 없다. 반드시 같은 기기 실행 세션의 CEF debug.log를 별도 수집해야 한다.

## 소스 스냅샷에서 확인한 사실

이 검토에는 이전에 제공된 build124-critical-source-20261103-055816.zip (약 0.9MB)을 직접 읽었다. 이는 이후 Mac 코드 수정 전의 스냅샷일 수 있으며 현재 로컬 HEAD나 현재 패치 상태의 증거가 아니다. 비공개/미커밋 소스는 공개 GitHub에 게시하지 말 것.

- FEX/FEXCore/Source/Interface/Core/CPUBackend.cpp 약 539~541행:
  VirtualProtect 실패 분기에서 LogMan::Msg::EFmt로 [build124-guard]를 출력한 다음 Failed to mprotect last page of code buffer.를 출력한다.
- FEX/FEXCore/include/FEXCore/Utils/ThreadPoolAllocator.h 약 423~425행:
  동일하게 두 출력을 같은 분기에 같은 LogMan::Msg::EFmt로 연속 실행한다.
- Build124 실기 로그에서는 기존 경고 161회, [build124-guard] 0회였다. 소스대로 해당 분기가 실행됐다면 신규 마커가 먼저 나와야 한다. 따라서 stale native archive, 별도 옛 바이너리 실행 경로, log sink/조건 차이를 우선 조사한다. 이는 미링크 확정 증거는 아니다.
- build/ntdll-unix/signal_arm64_ios.c 약 2445~2485행:
  기존 [steam-ui-cef32-fatal] probe는 특정 i386 INT3 guest RIP 0x6df3def4 및 MADEIRA_STEAM_UI_SESSION=1에 한정되어 있다. 일반 check.cc(376) 로그를 이 코드가 자동 포착하지 않는다.
- 동일 스냅샷의 server_ios.c에는 FD_CACHE_CROSS_GUARD가 없지만 이후 로컬에서 opt-in guard를 적용했다는 사용자 결과가 있으므로 과거 스냅샷으로 현재 파일 결손을 판정하면 안 된다.

## 즉시 실행 1 — 최신 기기 세션의 실제 build와 CEF 로그 확인

기존 앱을 다시 설치하거나 삭제하지 않고 로그만 읽는다. 사용자의 실제 기기 ID는 devicectl 목록에서 가져오고 공개 리포트에서는 가린다.

    WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
    BUNDLE=com.kimdongup.ideck.build100
    OUT="$WORK/build125-artifacts/postinstall-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$OUT"
    xcrun devicectl list devices
    DEV="<USER_DEVICE_ID>"
    xcrun devicectl device copy from --device "$DEV" --domain-type appDataContainer --domain-identifier "$BUNDLE" --source Documents/madeira-log.txt --destination "$OUT/madeira-log.txt"
    xcrun devicectl device copy from --device "$DEV" --domain-type appDataContainer --domain-identifier "$BUNDLE" --source Documents/wine/drive_c/Steam32BundleLab/bin/cef/cef.win7/debug.log --destination "$OUT/cef-debug.log" || true
    grep -n -m 5 -E '\[build\]|[[:space:]]v0[.]1[.]' "$OUT/madeira-log.txt" > "$OUT/build-marker.txt" || true
    grep -n -E 'NOTREACHED|Invalid logging destination|BrowserReady|\[build124-guard\]|\[fd-guard\]|Failed to mprotect|store-noalias|CROSS!' "$OUT/madeira-log.txt" > "$OUT/key-events.txt" || true
    wc -l "$OUT/madeira-log.txt" "$OUT/key-events.txt"
    echo "Evidence: $OUT"

실행 실패 로그가 최신으로 생성됐는지 타임스탬프 확인. CEF debug.log가 없어도 원인 자체를 단정할 수 없다.

## 즉시 실행 2 — 정적 FEX marker 및 빌드 출처 확인

기존 Build124 DerivedData가 있는 Mac에서:

    WORK=/Volumes/Repository/cokacremote/iDeckRuntimeLab
    APP="$WORK/build124-artifacts/DerivedData/iDeckBuild124/Build/Products/Debug-iphoneos/Madeira.app"
    EXEC=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP/Info.plist")
    shasum -a 256 "$APP/$EXEC"
    strings -a "$APP/$EXEC" | grep -E 'build124-guard|MADEIRA_FD_CACHE_CROSS_GUARD|Failed to mprotect' | sort -u || true

이 검사는 문자열 포함만 알려준다. 최신 FEX 소스에서 C++ 변경 지점, object 및 .a 정적 라이브러리의 실제 rebuild/link 경로를 추적하고 런타임에서 같은 경고의 두 출력이 왜 일치하지 않는지 분류해야 한다.

## Glyph Cluster 실행 우선순위

P0: 새 설치의 build marker/CEF 로그 동기화. Build125가 아니라 Build124/기타 빌드가 실행됐을 가능성을 먼저 배제.
P0: FEX source -> object -> archive -> Mach-O -> runtime provenance 확보. old warning과 new marker 불일치 설명.
P0: 최초 check.cc 발생의 원래 프로세스/스레드, CEF CLI, libcef RVA/stack 수집. 일반 로그를 signal-handler exception이라고 가정하지 말 것.
P1: FD guard OFF baseline 유지. FD/CEF/Crashpad/FEX 변수는 한 번에 하나만 바꿔 A/B.
P1: FEX arena 회수는 동일 실행 시간, 동일 CEF 재시도 횟수, 종료 후 live view로 비교.
STOP: 위 근거 없이 단순 Build 번호 증가/동일 IPA 재설치만 반복하지 말 것.

결과 보고: build marker, 원본 로그 구간과 시각, 첫 실패 callsite 또는 수집 한계, FEX native linkage 판정, 실행한 명령/결과/미해결 항목 및 다음 한 단계. 기존 소스와 Build124 아티팩트 보호.

**상태: 지시서 배포만 완료. 새 기기 검증, Build125 수정 성공과 GUI 복구는 확인되지 않았다.**
