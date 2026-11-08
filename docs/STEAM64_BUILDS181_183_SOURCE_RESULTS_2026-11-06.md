# Builds181–183: CEF 정렬·실제 backing 및 FEX 소스 재빌드

2026-11-06 HST. [Build180](STEAM64_BUILD180_SOURCE_MEMORY_2026-11-06.md)의 후속 검증.
모든 빌드는 기존 앱 ID로 업데이트하고 설정·prefix를 보존하며 두 선택적 메모리
entitlement를 실제 서명에서 제외한다. 커밋·푸시는 하지 않는다.

## Build181: 정렬 실패 다음의 실제 commit 실패를 분리

`virtual_ios.c`의 soft 후보 계산을 수정했다. 일반 power-of-two pool은 자기 크기에,
BRP의 power-of-two +64 KiB 예약은 guard 뒤의 pool이 자기 크기에 정렬되도록 한다.
정렬한 실제 범위를 네 후보 경로의 중첩·band 끝·overflow 검사와 view 검색에 사용한다.
기존 정확한 base 해제 정책과 assertion은 유지한다.

실제 helper를 추출한 ASAN/UBSAN 검사에서 기존 중첩 회귀, guard 정렬,
인접 범위·overflow·정확한 base 해제가 통과했다. native object, 증분 Xcode 빌드,
서명 검증이 통과했다. native archive는 `virtual.o`와 index만 변경됐으며 PE는 Build180과 같다.

PID5311, 캡처 `build181-artifacts/private/capture-20261106-134027/madeira-log.txt`:

- regular `0x7100000000 +0x40000000`, BRP guard `0x603fff0000 +0x40010000`을 반환했다.
  guard 뒤 주소는1 GiB/2 MiB 정렬을 만족한다.
- Build180의 `address_pool_manager.cc:58` 대신 `page_allocator_internals_win.h:174`에서
  실패했다. regular pool의 `0x7100200000 +0x4000` commit이 Wine view가 없는 native
  PROT_NONE 매핑과 충돌했다. 보호 모드는0, 최대 보호는RW였다.
- 정렬 문제는 이 실행에서 해소됐으나 실제 backing/commit은 아직 해결되지 않았다.
  기존 로그의 “Foreign mapping”은 진단 분류이며, 실제 소유자는 별도 API와 대조해야 한다.

## Build182: FEX IR 예약을 실제로 축소

FEX `IREmitter.h`에 Windows의 `MADEIRA_FEX_IR_HALF_MIB=2/4/8` 선택을 구현했다.
미설정·잘못된 값은 기존8 MiB를 유지한다.2를 명시한 시험에서는 data/list 각2 MiB로
총4 MiB를 예약한다. decoder의4,096개/576 KiB 설정과 IR 사용량 기록은 유지한다.

실제 `DualIntrusiveAllocator`의 data/list 경계 검사를 subtraction 방식으로 바꿔
offset+size 정수 overflow도 거부한다. 실제 class를 추출한 ASAN/UBSAN 검사는
2/4/8 MiB의 마지막 유효 allocation,1바이트 초과, SIZE_MAX, reset을 통과했다.
고정 버퍼가 자동 확장된다는 의미는 아니며 모든 guest의 최대 IR 수요를 보장하지 않는다.

FEX DLL을 재컴파일·링크하고 비디버그 virtual section 바이트 보존을 확인한 뒤 배치했다.
native는 Build181과 같다. 최초 패키징은 서명 전/후 native SHA를 직접 비교하는
검증 오류로 중단됐다. 서명된 Build181 앱을 기준으로 FEX만 교체하도록 고쳤고,
수정 전 시도에서는 새 IPA를 설치하지 않았다. 실패 staging과 로그를 별도 보존했다.

PID5334, 캡처 `build182-artifacts/private/capture-20261106-135037/madeira-log.txt`:

- decoder36건 모두4,096개, IR36건 모두 `half=2097152 total=4194304`를 기록했다.
- 명명된 OpDispatcher 예약도 기존16 MiB에서4 MiB로 바뀌었다.
- 이 구간에서 IR 용량 초과는 관측되지 않았다. 전체 세션·큰 guest workload의 보장은 아니다.
- CEF는 같은 native commit 조건/줄174에서 실패했다.
- FEX16 MiB 요청 실패도 남았다. 버퍼 축소가 실제 적용됐지만 아레나 부족 전체의
  해결은 아니다. 큰 예약 이벤트와 첫 live view 대조는 두 빌드 모두 일치했다.

| 측정 | Build181 | Build182 |
|---|---:|---:|
| FEX 실제 아레나 | 1,408 MiB | 1,456 MiB |
| view 예약합 | 1,388.965 MiB | 1,443.988 MiB |
| 장부상 커밋 | 852.395 MiB | 798.098 MiB |
| 전체 빈 공간 | 19.035 MiB | 12.012 MiB |
| 실패 요청 | 16 MiB | 16 MiB |
| 실패 요청 정렬 | 64 KiB | 16 MiB |
| 정렬 후 최대 gap | 10 MiB | 0.938 MiB |
| RW16 MiB view | 59개 /944 MiB | 70개 /1,120 MiB |
| 샘플링된 physical peak | 2,168 MiB | 2,226 MiB |

아레나 배치·thread 진행량·요청 정렬이 다르므로 이 두 peak를 성능 개선 비율로
해석하지 않는다. per-buffer 예약 감소와 실제 물리 RAM 절약은 구분한다.
두 캡처의 설정은 각 설치 전과 바이트가 같다.

## Build183: 앱이 소유한 사전 예약만 Wine에 전달

소스 조사에서 `JITAllocator.c`는 source ELF slot0의1 GiB를 사전 예약하고
`madeira_cef64_hold_get/claim/unclaim` API를 제공하지만, 현재 Wine native allocator에는
그 API를 사용하는 경로가 없었다. 해당 slot의 주소는 commit 충돌 주소와 일치한다.
이것만으로 현재 native 매핑의 소유권을 확정하지 않고, 실제 provider 확인 후에만 채택한다.

`MADEIRA_CEF_OWNED_REGULAR=1`인 Steam64 실험에 한해 다음을 검사하는 경로를 추가했다.

- 선택된 `wine-steam64` prefix, session/source layout,64비트 helper와 정확한 reserve 형태.
- 실제 native provider의 slot0 보유 여부·base·size, 요청 bounds·정렬·고정 hint 보존.
- Wine view 중첩 없음, 전체 native 범위가 실제 존재하며 PROT_NONE/max RW인지 확인.
- native single-use claim 후 기존 매핑을 해제·재매핑하지 않고 Wine view만 등록.
  view 생성 실패 때 claim을 rollback한다. PROT_NONE이라는 이유만으로 타 매핑을 인수하지 않는다.

실제 함수의 ASAN/UBSAN 검사는 provider 미보유, 잘못된 prefix/helper/고정 주소·bounds,
native hole/protection 불일치, view 충돌, 중복 claim, 생성 실패 rollback을 통과했다.
native 컴파일이 통과했다. 이 경로는 native 앱 수명당 single-use이며 helper 재시작 시
재사용·반납 broker 전체를 구현한 것은 아니다.

최초 Xcode 링크 시도는 LLVM-MinGW 환경 경로가 없어 Bundle Wine Mono 단계에서
중단됐다. 그 결과를 사용할 수 있는 빌드로 처리하지 않고 패키징을 중지·격리했다.
명시적 `LLVM_MINGW`와 PATH로 재빌드한 결과는 `BUILD SUCCEEDED`였고, 새 native marker를
확인한 뒤 서명·패키징했다. PE 1,302개는 Build182와 같다.

PID5438, 캡처 `build183-artifacts/private/capture-20261106-173711/madeira-log.txt`:

- `[cef-owned-regular] ADOPT slot=0 base=0x7100000000 size=0x40000000 status=0x0
  native-hold-verified=1`을 확인했다. 실제 앱 소유의 예약을 Wine이 인수했다.
- 이 캡처에서는 `chrome_elf.dll` loader 초기화 실패와 CEF fatal-site가 관측되지 않았다.
  Build181/182의 regular pool 초기 commit 장애를 넘어선 증거이며, 전체 CEF 초기화나
  Steam 로그인 화면 성공을 확정하는 증거는 아니다.
- FEX의 다음 실패 요청은 `0x802000`(8 MiB +8 KiB, CallRetStack 예약)이었다.
  1,536 MiB 아레나에서 전체 빈 공간은 `0xb4d000`, 최대 gap은 `0x4e0000`(4.875 MiB)이었다.
  예약합은 `0x5f4b3000`, 장부상 커밋은 `0x344ab000`이었다. IR 용량 초과는 관측되지 않았다.
- 샘플링된 physical peak는2,184 MiB였다. 두 메모리 entitlement는 계속 제외했다.

이 결과에 따라 다음 시험은 FEX의 Call/Return 예측 스택 예약과 생성된 JIT 경계 검사를
함께 축소하는 [Build184](STEAM64_BUILD184_COMPACT_CALLRET_2026-11-06.md)로 진행한다.
CoreDevice의 수동적 tunnel 상태가 disconnected여도 직접 앱 조회가 성공하는 경우가 있어,
기존의 paired/wired 기기 식별 뒤 직접 reachability probe로 연결을 검증하도록 시험 도구를 고쳤다.
Build184 설치 전 소유 PID5438을 다시 조회했을 때 이미 존재하지 않아 종료 신호는 보내지 않았다.
종료 원인은 확인되지 않았으며 이를 jetsam이나 정상 종료로 분류하지 않는다.

## 보존 자료

`build181-artifacts/`, `build182-artifacts/`, `build183-artifacts/`에 변경 전 소스·native archive,
컴파일 결과, source/object/DLL hash, package manifest, 캡처·분석 결과를 구분해 보존한다.
서명 자산·Valve 바이너리·원본 로그는 Git에 추가하지 않는다.
