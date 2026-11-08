# 추가 메모리 권한 없는 Steam64 실행의 가능성과 FEX 예약 공간 조사

2026-11-06 HST. [Build177–178 실기기 검증](STEAM64_BUILDS177_178_VERIFICATION_2026-11-06.md)의 후속 검토.
이번 단계는 논리 검토, 기존 실측의 재계산, 소스 조사 및 계측 준비다.
새 IPA 설치나 FEX 소스 수정은 하지 않았다.

## 판단

**추가 권한 없이 기존 예산 안의 낭비·파편화를 줄여 할당 여유를 확보할 가능성은 있다.
현재 증거만으로 Steam 전체 실행이 가능하다고 확정할 수는 없다.**

현재 서명과 런타임에서 두 메모리 entitlement는 모두 비활성이다. 이 조건에서 이미
CEF 이미지 배치와 상당한 Wine/FEX 실행이 확인됐다. 따라서 현재의 모든 실패를
“추가 권한이 없기 때문에 해결 불가능”으로 묶을 근거는 없다. 반대로 앱 코드만으로
커널이 부여한 메모리 예산이나 사용 가능한 주소 범위를 늘린다고 보장할 수도 없다.
계정 가입 유형 자체를 새로 검증한 것은 아니며, 기존 개발용 JIT/debugger 설정은 유지된다.

Apple의 [Increased Memory Limit 설명](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit)은
지원 기기의 기본 앱 메모리 한도보다 높은 사용을 요청하는 기능을 설명한다.
[Extended Virtual Addressing 설명](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.extended-virtual-addressing)은
더 큰 주소 공간을 대상으로 한다. 두 기능의 의미를 구분해야 한다.
[os_proc_available_memory](https://developer.apple.com/documentation/os/os_proc_available_memory)는
현재 앱 한도까지 남은 메모리의 순간적인 참고값이며, 기기의 전체 남은 RAM이나
특정 크기의 연속 가상주소 확보 가능성을 나타내지 않는다. 고정된 무료 계정 RAM 상한을 추정하지 않는다.

| 제약 | 추가 권한 없이 가능한 접근 | 현재 판정 |
|---|---|---|
| 앱 물리 메모리 예산 | 작업 집합·캐시·복사·불필요한 커밋 감소 | 확보량은 실제 footprint로 재측정해야 함 |
| 커널 가상주소 배치 | 기존 허용 범위 안에서 더 적게 예약하고 배치 개선 | 주소 상한 숫자만으로 큰 구멍의 존재를 보장할 수 없음 |
| FEX 내부 아레나 | allocator 예약 단위·동시 수요·안전한 재사용 개선 | 이번 직접 실패 지점, 우선 조사 대상 |
| JIT 실행 영역 | 이미 준비된 영역 내 이미지 배치 개선 | C 영역의 초기 CEF 이미지 배치는 이전에 성공, 전체 세션 용량은 별개 |

soft pool의 논리적 성공 응답은 커널의 실제 예약·향후 커밋 가능성을 대신하지 않는다.
Build178의 겹침 제거는 장부 오류를 고친 결과이며, 낮은 soft 주소에 대한 실제 커밋 성공은
별도 검증이 필요하다. 파일 매핑이나 캐시 정리로 RAM 사용을 줄여도 FEX 내부의 연속 주소
부족이 자동으로 해결되지는 않는다.

## 기존 스냅샷을 검증하여 다시 계산한 결과

`[fex-view]`의 개수·크기·커밋 합계가 failure census와 일치하는지 검사했다.
주소 범위의 겹침, 총 빈 공간과 정렬된 최대 구멍도 독립적으로 재계산했다.
아래 커밋 값은 Wine의 페이지 보호 장부 기준이며 물리 상주량이나 살아 있는 객체 크기가 아니다.

| 항목 | Build177 | Build178 |
|---|---:|---:|
| 아레나 | 1,536 MiB | 1,456 MiB |
| 살아 있는 view가 차지하는 예약 | 1,515.19 MiB | 1,439.08 MiB |
| 그 안의 커밋 합계 | 978.74 MiB | 904.67 MiB |
| 아레나의 빈 구멍 합계 | 20.81 MiB | 16.92 MiB |
| 요청 정렬을 만족하는 최대 구멍 | 12.5625 MiB | 6.875 MiB |
| 실패한 요청 | 16 MiB | 9 MiB |
| 16 MiB·flags0x3 view 개수 | 59 | 57 |
| 해당 view들의 예약 합계 | 944 MiB | 912 MiB |
| 해당 view들의 커밋 합계 | 407.70 MiB | 377.73 MiB |
| 해당 view 안의 미커밋 예약 | 536.30 MiB | 534.27 MiB |

Build178에서는 `6.875 < 9 < 16.92`이다. 전체 빈 공간은 한 요청보다 크지만,
적합한 연속 공간이 없다. 메모리를 덜 예약하거나 배치를 바꿔 해결할 여지가 있다는
근거이며, 살아 있는 객체를 즉시 옮길 수 있다는 뜻은 아니다.

완전히 비어 정상 반납 가능한 16 MiB 범위 하나가 확인된다면 이 9 MiB 요청 한 건의
공간은 만들 수 있다. 그러나 **그런 범위가 존재하는지는 아직 확인되지 않았다.**
반납 가능 객체·cross-thread 참조·allocator 소유권을 확인해야 한다.
미커밋 534.27 MiB를 곧바로 회수 가능량으로 계산하거나 물리 RAM 절약량으로 발표하면 안 된다.

## 16 MiB 단위 조사 결과

현재 [rpmalloc.c](../FEX/External/rpmalloc/rpmalloc/rpmalloc.c)는 iOS에서
`SPAN_SIZE=16 MiB`, large page16 MiB, medium page4 MiB, small page64 KiB를 사용한다.
`heap_get_span()`은 부족한 page type마다 span을 요청하고, 마스크 연산으로
객체 주소에서 span 헤더를 찾는다. 로그의 대상 view는 모두16 MiB 정렬이므로
allocator span과 형태가 일치한다. 다만 **모든 대상 view의 실제 span 정체와 소유권이
검증된 것은 아니다.** 큰 FEX 작업 버퍼와 heap span도 구분해야 한다.

Build178 대상57개를 커밋량으로 나누면 다음과 같다.

| view당 커밋 | 개수 |
|---|---:|
| 4 MiB 이하 | 28 |
| 4 MiB 초과~8 MiB | 8 |
| 8 MiB 초과~12 MiB | 4 |
| 12 MiB 초과~16 MiB | 17 |

21개는 이미8 MiB보다 많이 커밋돼 있다. 나머지36개도 커밋량만으로 객체 크기나
생존 여부를 알 수 없다. 단순히 “57개를 반으로 줄여456 MiB 확보”라고 예측할 수 없다.

8 MiB span 변경은 상수 한 개의 수정으로 성립하지 않는다.

- 기존 large page16 MiB를 유지하면 `page_count = 8 MiB / 16 MiB = 0`이다.
- large page도8 MiB로 바꾸더라도 현재 최대 large block8 MiB와128바이트 헤더를
  함께 넣을 수 없어 `(8 MiB - 128) / 8 MiB = 0`개가 된다.
- size class·huge 경로·정렬·span 마스크·cross-thread free를 함께 검증해야 한다.

[CMake 설정](../FEX/External/rpmalloc/CMakeLists.txt)은 `ENABLE_STATISTICS=0`이다.
현재 통계 API를 호출하는 것만으로 필요한 활성 객체·page-type별 정보를 얻는다는
가정도 성립하지 않는다. 또한 `rpmalloc_thread_collect()`는 현재 구현에서 빈 함수다.

## 수명 추적의 실제 결함과 계측 수정

다음 결함을 native `virtual_ios.c`에서 확인했다.

1. `ios_span_census()`는 옛 고정 주소 `[0x7c00000000,0x8000000000)`만 받는다.
   현재 `[0x7040920000,0x709b920000)` 아레나는 전부 제외된다.
2. 해제 호출 지점에도 옛 주소 하한이 남아 있고, 실제 해제 성공 전 기록한다.
3. allocation 호출은 reserve와 commit을 구분하지 않아 중복 집계가 가능하다.
4. 기존 `[valloc]`와 `[vfree]`는 실패 시점 전에 각각3,000건 제한에 도달했다.
   이 기록만으로 전체 수명을 복원할 수 없다. `[span-census]`0건도 누수의 증거가 아니다.

이번 native 계측 수정은 실제 공개된 아레나 범위를 사용하고, 성공한 reserve만
ALLOC으로 센다. FREE는 정상적으로 전체 view를 해제한 뒤에만 기록한다.
실패한 해제·decommit·placeholder 분할은 전체 span 반환으로 세지 않는다.

`MADEIRA_FEX_SPAN_TRACE=1`은 최대4,096건의 이벤트와 명시적 절단 표식을 남긴다.
순번·TID·PEB로 원래 큰 범위의 생성·해제와 pseudo-process를 구분할 수 있다.
이는 **FEX 아레나의 큰 예약 수명** 계측이며 allocator 내부 활성 객체 census를 대신하지 않는다.
기본 추적은 기존처럼 샘플링하며, 할당 배치·보호·재사용 정책은 바꾸지 않는다.

호스트 검사 `tests/host/check-fex-span-census.py`는 실제 함수와 실제 release 분기를
컴파일하여 동적/옛 주소 범위, 경계·overflow, 실패/부분/정상 전체 해제, null TEB,
추적 상한을 AddressSanitizer/UndefinedBehaviorSanitizer로 검증했다. 통과했다.
네이티브 iOS 컴파일도 통과했다. 라이브러리 교체·IPA 패키징·실기기 재설치는 하지 않았으므로
**새 계측의 실기기 결과는 아직 없다.** 설치된 Build178의 결과와 혼동하지 않는다.

## 다음 한 번의 계측에서 판단할 항목

- 실제 실패 시점의 live view와 완전한 큰 예약 이벤트를 대조하여 생성 주체와 소멸을 확인한다.
- 완전히 해제됐는데 남은 범위인지, 아직 살아 있는 객체/allocator cache인지 구분한다.
- heap span으로 검증된 범위에 대해서만 page type·page initialized·block used·pending
  cross-thread free를 allocator가 보호하는 시점에 수집한다. 비어 보인다는 이유로 해제하지 않는다.
- 그 결과에 따라 소유권 있는 전체 span 반환, 더 작은 예약 단위, 작업 버퍼의 초기 크기 축소 중
  하나를 선택한다. CPU count1·L1-only cache·V8 jitless는 이미 적용돼 있어 반복 처방하지 않는다.
- 최종 수용 조건은 실제 pool commit 성공, FEX 연속 할당 성공, 물리 예산 내 진행,
  로그인 화면과 반복 시작이다. 첫9 MiB 요청 성공만으로 전체 세션을 보장하지 않는다.

증거와 재현: `diagnostics/free-memory-review-20261106/analyze-arena-footprint.py`,
`arena-footprint-review.json`, `diagnostic-validation.json` 및 독립 컴파일 객체를 보존했다.
FEX 소스와 기기 설정은 이번 단계에서 변경하지 않았다.

## 후속 실기기 검증

위의 미배포 상태는 이 문서를 작성한 단계의 기록이다. 이후 검증 object로
[Build179](STEAM64_BUILD179_SPAN_LIFETIME_2026-11-06.md)를 빌드·설치했다.
선택적 메모리 권한 없이 큰 예약의 종료 회수176 MiB와 명시적 해제64 MiB를 확인했으나,
FEX 연속 할당 실패는 남았다. 또한 CEF의 `chrome_elf.dll` 초기화 종료가 FEX 실패보다
앞선다는 사실을 확인하여, 다음 조사를 DLL 초기화와 예약·반납 처리로 좁혔다.

[Build180](STEAM64_BUILD180_SOURCE_MEMORY_2026-11-06.md)에서 실제 CEF fatal 위치를
계측했고, [Build181–183](STEAM64_BUILDS181_183_SOURCE_RESULTS_2026-11-06.md)에서는 정렬 수정,
FEX IR 예약 축소, 실제 native hold의 Wine 인수를 각각 빌드·검증했다. Build183 캡처에서는
이전 CEF fatal/loader 실패가 사라졌지만 FEX8 MiB CallRetStack 연속 예약 실패가 남았다.
이를 [Build184](STEAM64_BUILD184_COMPACT_CALLRET_2026-11-06.md)에서 소스 수정으로 검증한다.
