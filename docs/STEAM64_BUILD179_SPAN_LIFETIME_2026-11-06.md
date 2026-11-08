# Build179: FEX 큰 예약 수명 및 CEF 선행 종료 검증

2026-11-06 HST. [추가 권한 없는 메모리 검토](STEAM64_NO_EXTRA_MEMORY_REVIEW_2026-11-06.md)의 다음 단계.

## 실험 조건

- 목적: 실패 시점의16 MiB 예약을 생성·해제 이벤트와 대조한다.
- Build178의 할당·배치 정책과 PE 자산을 유지하고 native 수명 계측만 변경한다.
- 실제 app/helper 서명에서 increased-memory-limit 및 extended-virtual-addressing을 제외한다.
- `MADEIRA_FEX_SPAN_TRACE=1`, `MADEIRA_FEX_VIEW_LOG=1`로 기록한다.
- 기존 CPU count1, L1-only cache, V8 jitless 조건을 바꾸지 않는다.
- 같은 앱 ID로 업데이트하며 사용자 설정과 Wine prefix를 보존한다.
- validated object와 source SHA를 대조하고, native archive의 변경 object가 virtual.o뿐인지 검사한다.

## 판독 방법과 한계

수명 이벤트의 순번 연속성·절단·중복·주소 재사용·해제 일치를 먼저 검사한다.
첫 failure census의 live view와 크기·주소를 대조해 일치한 범위만 할당 호출자의 PEB/TID에 연결한다.
할당 syscall의 진단 출력이 view 변경보다 늦게 기록될 수 있으므로 snapshot과의 불일치는
곧바로 누수로 해석하지 않는다. 기록 위치 차이나 미완료 이벤트를 먼저 검토한다.

이 계측은16 MiB 이상인 FEX 아레나 예약의 수명을 다룬다. allocator 내부의 살아 있는 객체,
빈 page, cross-thread pending free를 직접 측정하지 않는다. 해제되지 않은 예약이 존재해도
그 전체를 안전하게 반납할 수 있다고 결론 내리지 않는다.

프로세스 종료 회수는 `ios_fex_reclaim_process()`가 `delete_view()`를 직접 호출하므로
NtFreeVirtualMemory의 FREE 이벤트와 별도로 합친다. 종료 회수의 PEB와 당시 남은 예약을
대조하되, 이 PEB를 allocator heap이나 개별 객체의 실제 소유자로 단정하지 않는다.

## 빌드·설치 결과

호스트 ASAN/UBSAN 검사 및 native 컴파일이 통과한 source/object hash를 다시 확인했다.
Build178과 native archive를 비교하면 `virtual.o`와 archive index만 달라졌다.
증분 Xcode 빌드, app/helper 서명 검증, 같은 앱 ID로 업데이트 설치가 통과했다.
PE DLL/EXE 1,302개는 Build178과 바이트가 같다. FEX 소스는 이번 단계에서 수정하지 않았다.

`iDeck-Build179-SpanLifecycle.ipa`를 설치하고 PID5209로 실행했다.
실제 app/helper 서명과 실행 로그 모두 두 선택적 메모리 entitlement가 없음을 확인했다.
이는 현재 서명에서 권한을 사용하지 않았다는 검증이다. Personal Team 발급 절차 전체를
새로 시험하거나 계정의 가입 상태를 검증한 것은 아니다.

## 큰 예약의 회수는 관측됐다

12:20:49와12:25:53 HST의 두 캡처를 대조했다. 큰 예약 이벤트는 모두 첫 view census 전에
기록됐으며, 두 번째 캡처에도 동일한90건만 남았다. 순번1~90 누락·중복·절단이 없었다.

| 최초 실패 snapshot까지의 사건 | 16 MiB 범위 개수 | 예약 크기 |
|---|---:|---:|
| 성공한 ALLOC | 86 | 1,376 MiB |
| 명시적 전체 MEM_RELEASE | 4 | 64 MiB |
| 세 프로세스 종료 시 회수된 추적 대상 | 3 + 3 + 5 = 11 | 176 MiB |
| snapshot에 남은 큰 view | 71 | 1,136 MiB |

`86 - 4 - 11 = 71`이며, 남은71개는 주소·크기가 live view와 모두 일치한다.
FREE만 보면 주소 재사용11건이 중복 할당처럼 보이지만, 별도 종료 회수를 합치면
그 불일치가 사라진다. 캡처된 큰 범위에서 종료 후 남은 예약 불일치는 발견하지 않았다.
이 결과는 작은 범위까지 포함한 모든 누수의 부재나 allocator 객체 생존 여부의 증명은 아니다.

기록된 할당 호출자별로는 첫 PEB가11개/176 MiB, Steam 실행과 연결된 두 번째 PEB가
60개/960 MiB를 생성했다. 이미 종료한 helper의 예약을 무조건 다시 해제하는 방식으로
이1,136 MiB를 확보할 수 있다고 볼 근거는 없다.

## FEX 연속 할당 실패는 계속된다

| 항목 | 측정값 |
|---|---:|
| 실제 FEX 아레나 | 1,456 MiB |
| live view / 예약 | 172개 / 1,439.082 MiB |
| Wine 장부상 커밋 | 903.723 MiB |
| 전체 빈 공간 | 16.918 MiB |
| 최대 연속 빈 공간 | 6.875 MiB |
| 16 MiB 정렬 후 최대 빈 공간 | 5.625 MiB |
| 실패한 요청 | 16 MiB, 16 MiB 정렬 |
| RW 16 MiB view | 57개 / 예약912 MiB / 커밋376.781 MiB |
| 샘플링된 최대 physical footprint | 2,269 MiB |

view 개수·예약합·커밋합·범위·중첩 없음·gap 합을 재계산하여 native census와 대조했다.
커밋되지 않았지만 예약된 RW 영역535.219 MiB도 곧바로 반환 가능한 공간은 아니다.
객체·page·cross-thread pending free를 측정하지 않았고, physical footprint를 OS 상한으로
간주하지 않는다. 이번 계측 변경으로 로그인 화면이나 전체 세션 성공을 확인하지 못했다.

## CEF 종료가 먼저 일어났다

첫 캡처의 다음 로그 순서는 두 번째 캡처에서도 유지된다.

1. line13039: helper TID008c의 guest breakpoint.
2. line13150~13151: `chrome_elf.dll` 초기화 실패, helper loader status `0x80000003`.
3. line13196: 해당 helper PEB의 FEX view18개 회수. 이 중 추적한16 MiB 범위는5개다.
4. line13201: CEF helper 종료 이벤트.
5. line13433 이후: FEX 아레나 할당 실패와 view census. 요약은 line13606에 있다.

따라서 이 실행의 CEF 종료를 뒤의 FEX 연속 공간 부족만으로 설명할 수 없다.
앞서 큰 guest VA 예약 시도들도 실패했으므로 메모리 관련 원인 전체가 배제된 것은 아니다.
soft pool은6번 승인·4번 반납됐고 활성 범위끼리 중첩은 없었다. native backing이나 실제
commit 성공을 증명한 것은 아니다. 누적 `bigres`/`jumbo` 수치를 동시 활성 예약으로 읽지 않는다.

기기에서 현재 `chrome_elf.dll`을 읽어 SHA-256
`673584661cd0044b186e40286b3d57a099b45002d3fc50f334ae1d3d14bc7621`을 확인했다.
이는 앱이 배치하는 소스 빌드 호환 자산과 같다. `PROVENANCE.json`은 Chromium126에서
regular/BRP pool을 각각1 GiB로 줄이고 CEF crash integration을 적용한 빌드임을 기록한다.
공식 배포 원본 DLL이 아니다. 이 단계의 초기 설명에서 공식 DLL이라고 표현한 부분을 정정한다.
로드 base `0x7162c80000`을 적용하면
breakpoint는 RVA `0x96e12`, 이어지는 guest RIP는 `0x96e13`이다.

REA/Ghidra 정적 Evidence
`ev_a606a310dde7d41d06c3f8baae5c753f37da6669369b993d5ff9a7ef82b2bed3`는
`FUN_180096cc0`의 severity 값3 분기와 마지막 INT3를 보여 준다.
LLVM objdump의 원본 바이트 판독은 바로 다음 UD2도 확인한다.
이는 일반적인 fatal logging 경로로 보이지만 **어느 CHECK가 실행됐는지는 아직 미확정**이다.
인접한 page allocator 함수에는 VirtualFree 실패 CHECK와 원본 파일명 문자열이 있으나,
이 사실만으로 그 CHECK를 현재 종료 원인이라고 확정하지 않는다.

REA의 첫 시도는 sandbox 내 Swift module cache 접근 오류로 실패했고, 허용된 실행 환경에서
다시 수행한 정적 분석은 성공했다. 원본 DLL을 실행하거나 패치하지 않았다.
기기 로그·호스트 parser 결과·LLVM 출력은 별도 증거이며 REA runtime 관측으로 표현하지 않는다.

## 다음 조사와 보존 상태

우선 `chrome_elf.dll` 초기화의 fatal CHECK, reserve 정렬과 반환 주소, 실제 VirtualFree 인자와
결과를 좁힌다. 별도로 FEX의 활성 allocator page/객체 계측이 필요하다. 단순 span 축소나
CPU count1·L1-only·jitless 재적용으로 해결됐다고 판단하지 않는다.

두 캡처의 `madeira.cfg`는 설치 전과 바이트가 같다. 동일 ID 업데이트로 prefix를 유지했다.
확인한 테스트 PID에 정상 종료를 요청했으나 이후에도 남아 있었다.
앱 버전과 정확한 실행 경로를 다시 검증한 뒤 PID5209에만 SIGKILL을 사용했고,
후속 process 조회에서 사라진 것을 확인했다.
다른 iDeck 인스턴스는 건드리지 않았다. 커밋·푸시는 하지 않았다.

재현 자료는 workspace의 `build179-artifacts/`에 보존했다.
`native-provenance.json`, `package-manifest.json`, `lifecycle-analysis.json`,
`analyze-lifecycle.py`, REA 정적 Evidence와 원본 disassembly가 포함된다.
서명 자산·실제 Valve DLL·원본 기기 로그는 Git에 추가하지 않는다.
소스 빌드 DLL을 더 작은 메모리 상황에 맞출 수 있는지는
[재빌드 조사](STEAM64_CHROME_ELF_REBUILD_REVIEW_2026-11-06.md)에서 이어서 검토한다.
