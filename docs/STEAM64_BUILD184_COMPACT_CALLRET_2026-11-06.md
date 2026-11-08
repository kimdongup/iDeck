# Build184: FEX Call/Return 예측 스택과 연속 공간 검증

2026-11-06 HST. [Build183](STEAM64_BUILDS181_183_SOURCE_RESULTS_2026-11-06.md)의 후속 시험.
두 선택적 메모리 entitlement 없이 기존 Steam64 prefix를 보존한다. 커밋·푸시는 하지 않는다.

## 변경 이유와 구현

Build183은 native regular hold의 Wine 인수에 성공했고 이전 CEF fatal/loader 실패가
캡처에서 사라졌지만, 최대 연속 gap 4.875 MiB에 대해 FEX CallRetStack이8 MiB +8 KiB를
요구하다 실패했다. 물리 RAM 사용량과 별개로 이 예약은 연속 주소 공간이 필요하다.

FEX의 iOS ARM64EC CallRetStack을8 MiB에서1 MiB로 줄였다. 다른 FEX 대상은8 MiB를 유지한다.
이는 guest Windows 스택이 아니라 CALL/RET 예측용 shadow stack이다. 예측이 초기화되면
기존의 일반 lookup 경로로 진행하므로 예측 기록을 무제한 보관할 필요는 없다.
예약 크기만 바꾸지 않고 다음을 함께 수정했다.

- 공유 MIT C header의 크기로 기본 위치(512 KiB), live 시작(256 KiB), live 폭(512 KiB)을 계산한다.
- BranchOps의 세 guard와 dispatcher callback sentinel guard가 모두 같은 이름 있는 경계를 사용한다.
- allocation/free, GetInfo와 전체 reservation reset은 기존의 TS 상수를 통해 같은 크기를 사용한다.
- native signal 진단도 공유 geometry로 읽고, 사용량의 고정4 MiB 비율 표기를 제거한다.
  native `WINE_IOS` 진단은 이번 ARM64EC 후보와 맞췄으며 다른 cached FEX 조합은 미검증이다.

더 작은 predictor는 reset·일반 lookup 빈도와 성능에 영향을 줄 수 있다. 이 시험은 연속 예약
부담을 낮추는 후보이며 모든 게임이나 callback/SEH workload의 호환성을 보장하지 않는다.

## 빌드 전 검증과 보존

실제 네 guard의 emitted sequence와 GetInfo 코드를 추출해 ASAN/UBSAN 모델에서 검사했다.
1/8 MiB 구성, 낮은/높은 경계,0/UINT64_MAX,100,000회 push/pop 주소 범위를 통과했다.
이는 실제 생성된 ARM64 명령을 CPU로 실행한 통합 시험은 아니다. native C header 크기와
전체 reservation reset 사용도 확인했다. FEX DLL 재컴파일·링크와 native signal object 컴파일이 통과했다.

`build184-artifacts/`에 소스·object·DLL hash, 변경 전 archive, host 결과, 빌드 로그를 보존한다.
변경 전 네 FEX 파일은 최초 snapshot 명령이 실행되지 않아 Git HEAD에서 복구했다.
사전 status에서 이 네 파일은 clean이었고, 기존 rpmalloc/InvalidationTracker 변경은 보존했다.
`baseline-source-recovery.json`에 이 복구 방법을 명시했다.

## 패키징·실기기 결과

Xcode 빌드, app/helper 서명, IPA 무결성 검증이 통과했다.
native archive는 Build183 대비 `signal_arm64.o`만 달라졌고 FEX DLL은 재컴파일했다.
디버그 제거 전후 비디버그 section의 virtual 바이트·RVA·크기가 같음을 확인했다.
PE 1,302개 중 교체한 것은 `arm64ec-windows/xtajit64.dll`뿐이다.

- IPA: `build184-artifacts/iDeck-Build184-CompactCallRet.ipa` /290,450,525바이트.
- IPA SHA-256: `afac36930d8b19d7a00d2abb6bd01200e41e633bc599301f531d1baab5fd93b0`.
- FEX SHA-256: `85343467de5b676b7c4a0cbd13df44aa8223aee1389949446575f0f43525a133`.
- 같은 앱 ID로 업데이트 설치 후 PID5477로 실행했다. app/helper 실제 서명에서
  increased-memory-limit와 extended-virtual-addressing이 모두 없는 것을 확인했다.

| 캡처(HST) | 실행 후 약 | 로그 줄 수 | FEX census/CallRet 예약 실패 | CEF fatal-site/ELF loader 실패 | guest breakpoint | 샘플링 physical peak |
|---|---:|---:|---|---|---:|---:|
| 17:52:25 | 33초 | 13,024 | 없음/없음 | 없음/없음 | 0 | 1,716 MiB |
| 17:53:12 | 80초 | 18,486 | 없음/없음 | 없음/없음 | 2 | 2,375 MiB |
| 17:55:12 | 200초 | 23,589 | 없음/없음 | 없음/없음 | 2 | 2,469 MiB |

실제 `[callret-geom]`은 `size=0x100000 guard-offset=0x40000 guard-size=0x80000`을 기록했다.
regular slot0의 `ADOPT ... status=0x0 native-hold-verified=1`도 다시 확인했다.
이 구간에서는 Build183의8 MiB 연속 예약 실패가 사라졌다. FEX failure snapshot이 없으므로
남은 최대 gap·아레나 잔여량을 측정한 것은 아니며, 모든 실행의 메모리 문제가 해결된 것은 아니다.
초기1,716 MiB 샘플만으로 물리 RAM 절감률을 주장하지 않는다. 세 설정 캡처는 설치 전과 바이트가 같다.

최종 로그 수집 후 기록한 PID의 앱 version과 실제 executable 경로를 대조하고 종료했다.
일반 종료 뒤에도 남아 있어 해당 PID에만 kill을 사용했고, 사라진 것을 확인했다.
다른 앱이나 prefix를 종료·삭제하지 않았다.

## 다음 장애: libcef의 큰 PartitionAlloc 예약

후속 캡처에서16 GiB regular soft grant와16 GiB +64 KiB BRP 예약 재시도가 나타났다.
그 뒤 unhinted `0x800000000`(32 GiB) reserve가 `STATUS_NO_MEMORY`로 실패했고,
`libcef.dll` 내부에 두 번의 breakpoint가 발생했다. 첫 번째의 모듈 base는
`0x70f2c30000`, guest RIP는 `0x70f9553405`였다. trap 명령은 그 한 바이트 앞인
RVA `0x6923404`다. `chrome_elf.dll`의 기존 fatal RVA와는 다른 위치다.

실제 libcef SHA는 Build179에서 채취한
`c85bf94462b3c79baeac63823db52d15e116eead71ea414e5d3a112c59e434d3`와 대조했다.
PE runtime-function table의 해당 함수 범위는 RVA `[0x69233f0,0x6923408)`다.
LLVM disassembly에서47을 stack에 쓰고 no-op `ret` 함수에 주소를 전달한 다음
`int3; int3; ud2`로 끝나는 것을 확인했다. 부모 코드는 error8일 때 이 함수를 호출하고,
별도 commit 오류 경로는52라는 line marker를 사용한다.

정확한 Chromium commit의 [PartitionAddressSpace 소스](https://raw.githubusercontent.com/chromium/chromium/2e81dea53f5ecdc1c057e4c70ecd66151987296a/base/allocator/partition_allocator/src/partition_alloc/partition_address_space.cc)에서
`HandlePoolAllocFailureOutOfVASpace()`의 `PA_NO_CODE_FOLDING` 위치가47이며,
그 macro는 `__LINE__`을 Alias에 전달한다. 따라서 이 trap은 **pool의 주소 공간 예약 실패**
경로라는 추론에 부합한다. 심볼을 복구해 이름을 확정한 것은 아니다.

REA/Ghidra로 원본 PE에서 추출한24바이트 함수 조각도 분석했다. 올바른 주소를 사용한 Evidence는
`ev_5512ba90b4d575030b374d842533d954d8192faa471765dda73baf5cbf26f7a6`이며,
원본 offset·범위·fragment hash는 `libcef-trap-fragment-manifest.json`에 있다.
조각에는 외부 함수·전역·문자열이 없으므로 이것만으로 전체 C++ 의미를 확정하지 않는다.
Kuna의 PE 미지원 응답과 최초 잘못 지정한 origin의 결과도 보존하되, 후자는
`invalid-origin`으로 격리하고 판단 근거에서 제외했다.

기존 `[brp-contain]` 문구는 범용 `CC CC 0F 0B`를 refcount assertion이라고 이름 붙인다.
이번 원인 판정에는 그 이름을 사용하지 않는다. 그 진단이 caller라고 읽은 값도 이번에는
libcef `.data` 영역이어서 return PC로 사용할 수 없다. refcount 오류를 확정하거나 trap을
우회할 근거가 아니다.

32 GiB를 필요한 실제 RAM이나 별도의32 GiB pool로 해석해서도 안 된다.
[동일 commit의 page allocator](https://raw.githubusercontent.com/chromium/chromium/2e81dea53f5ecdc1c057e4c70ecd66151987296a/base/allocator/partition_allocator/src/partition_alloc/page_allocator.cc)는
정렬 hint 재시도 후 `length + alignment - allocation_granularity`를 예약하는 fallback을 쓴다.
16 GiB +64 KiB와16 GiB 정렬을 대입하면 정확히32 GiB다. 로그의 순서·크기는 이 경로와 일치한다.

## 다음 해결책의 범위

다음 수정 대상은 **libcef에 포함된 allocator의 pool 크기와 mask/정렬 계약**이다.
현재 chrome_elf의1 GiB 빌드만 더 줄이는 것으로 libcef의16 GiB 요구까지 바뀐다고 볼 수 없다.
전체 CEF 소스 재빌드 후보에 regular/BRP 크기를 함께 적용하고, libcef·chrome_elf의 각 allocator
복사본과 CEF ABI를 검증해야 한다. 기존512/256 MiB header 후보는 설계 자료이며 이번에 새 DLL로
컴파일·설치한 것은 아니다. Valve helper와 교환하는 export·구조체·동적 함수 사용도 확인해야 한다.

작은 크기를 요청보다 적게 반환하거나 backing 없는 큰 성공값을 만드는 방식은 채택하지 않는다.
무료 권한 아래에서 작은 pool의 실제 예약·commit이 통과하는지부터 검증하고,
이후 BrowserReady·로그인 화면·반복 시작으로 수용 범위를 넓힌다. 이번 세 캡처에서는
BrowserReady와 로그인 화면 성공을 확인하지 못했다. FEX rpmalloc의16 MiB span도 후속 공간
압박 대상으로 남지만, 이번에 관측한 선행 종료 지점은 libcef의 큰 pool 예약 경로다.

후속 [전체 libcef 소스 재빌드 조사](STEAM64_LIBCEF_SOURCE_REBUILD_2026-11-06.md)에서
실제 DLL의 API hash/CEF commit이 기존 공개 source ELF의 CEF 리비전과 다름을 확인했다.
1 GiB source 후보와 Windows metadata probe는 준비했지만, 일치 ABI와 Windows 빌드 환경이
확보되지 않아 libcef DLL 재컴파일·설치는 아직 수행하지 않았다.
