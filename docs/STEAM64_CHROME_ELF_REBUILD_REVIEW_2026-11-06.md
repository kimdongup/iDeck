# 메모리 제약에 맞춘 chrome_elf 재빌드와 FEX 수정 검토

2026-11-06 HST. Build179 계측을 마친 뒤 사용자의 DLL 재구현 조사 및 FEX 메모리 수정
허용 요청을 반영한 검토다. 새 DLL의 컴파일·설치 성공을 보고하는 문서는 아니다.

## 판단

**가능한 접근이며, 현재 DLL도 이미 그 방식으로 만들어졌다.** 공개 Chromium/CEF 소스를
수정해 재빌드하는 경로가 존재한다. 디컴파일은 실제 바이너리와 소스의 대응·실패 분기를
확인하는 데 사용하고, 구현은 버전이 고정된 원본 소스에서 이어가는 것이 타당하다.
Chromium은 `chrome_elf`를 독립 shared-library target으로 정의한다.
[Chromium126 빌드 정의](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/chrome/chrome_elf/BUILD.gn)

다만 `chrome_elf`는 CEF 전체의 메모리를 제공하는 allocator 서비스 DLL이 아니다.
현재 export에는 일반 malloc/free API가 없고, 초기화·Crashpad·설치 정보·DLL hook 관련
기능이 포함된다. 공개 초기화 코드도 이 여러 역할을 수행한다.
[초기화 소스](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/chrome/chrome_elf/chrome_elf_main.cc)

## 현재 기기에서 실제 사용한 파일

Build179의 앱 데이터에서 세 파일을 직접 읽어 분석했다. 설치 파일을 교체하지 않았다.

| 파일 | SHA-256 | 관측 |
|---|---|---|
| chrome_elf.dll | `673584661cd0044b186e40286b3d57a099b45002d3fc50f334ae1d3d14bc7621` | 1,666,560바이트, resource version126.0.6478.183 |
| libcef.dll | `c85bf94462b3c79baeac63823db52d15e116eead71ea414e5d3a112c59e434d3` | chrome_elf의15개 함수를 정적 import |
| steamwebhelper.exe | `abbd293bd42564944700b46b9245209a4fef15247e21b968dd622d874961f4ce` | 정적/지연 chrome_elf import 없음 |

현재 DLL의 named export26개 중 실제 libcef의15개 요구 이름은 모두 충족한다.
이는 함수의 동작·C++ 객체 layout·설치 payload·thread/TLS 수명까지 호환된다는 증명은
아니다. GetProcAddress 같은 동적 사용의 전체 범위도 아직 확정하지 않았다.
`GetHandleVerifier`는 포인터를 반환하는 인터페이스여서 이름만 같은 함수를 만들거나
항상 NULL을 반환하는 것으로 계약을 충족했다고 볼 수 없다.

## 소스 빌드 이력을 복원했다

앱의 `Steam64Compatibility/PROVENANCE.json`과 실제 DLL hash가 일치한다.
기록된 소스는 다음과 같다.

- Chromium: `2e81dea53f5ecdc1c057e4c70ecd66151987296a` /126.0.6478.183.
- CEF crash integration: `a5d51ba9db7ee74a523dc247bd09ec91ba4d7446`.
- regular pool1 GiB + BRP pool1 GiB. 변경 범위는 chrome_elf에 정적으로 연결된 allocator다.
- libcef·Valve helper를 재빌드한 것은 아니다.

현재 checkout에는 출처 문서가 가리키는 `experiments/cef64`가 없다.
Git 이력 `9b9344501b5909ec90e74706d695808e71490e74`에서 준비·빌드·CEF 통합·load probe
레시피와 관련 문서·라이선스10개를 진단 폴더로 복원했다. 브랜치나 현재 작업 파일을
되돌리지 않았다. 당시 Windows 및 기기 component probe 결과는 역사 기록이며,
이번 무료 권한 조건의 전체 Steam 성공으로 소급 적용하지 않는다.

정확한 Chromium 커밋의 allocator header를 새로 받아 원본 SHA를 확인하고, 복원한
`patch_header()`를 적용했다. 결과 SHA
`968dcf754170b273e5f2c78597394b7f48095ba9d8d4307820758807457e7cee`가 현재 DLL의
출처 기록과 일치했다. 전체 DLL을 이번에 다시 컴파일해 재현한 결과는 아니다.

## 디컴파일에서 확인한 범위

REA/Ghidra로 현재 DLL의 실패 경로를 조사했다.

- `ev_a606a310dde7d41d06c3f8baae5c753f37da6669369b993d5ff9a7ef82b2bed3`:
  실제 breakpoint인 RVA `0x96e12`를 포함한 fatal logging 함수의 명령어.
- `ev_a5fe728d0131daf8ed6285b101ddd7b13835e8ae540a840858529f203c4b62e0`:
  RVA `0xb1810` page-free 함수의 pseudocode. 주소·길이 정렬 검사,
  `VirtualFree(address, 0, MEM_RELEASE)` 결과 검사, mapped-address-space 장부 검사가 있다.

따라서 breakpoint를 지우거나 모든 free를 성공으로 반환하는 재작성은 원인을 고치지 않는다.
현재 실행에서 **이 검사 중 어느 것이 fatal을 일으켰는지는 아직 미확정**이다.
syscall 경계의 `jumbo nrip/grip`는 저장 context가 stale일 수 있어, 함수 실행을 확정하는
call stack으로 사용하지 않는다. 별도 탐색에서 나온 iterator destructor pseudocode도
allocator 원인 증거로 채택하지 않았다. pseudocode는 원본 C++와 동일하지 않다.

## 더 작은 DLL 후보

기존1 GiB 소스에 적용할512 MiB·256 MiB 후보 patch를 별도로 만들었다.
둘 다 regular/BRP 크기 두 선언만 변경하며 mask·BRP guard·실패 검사를 유지한다.
소스의 pool 크기는2의 거듭제곱이어야 하며 주소 정렬과 membership mask가 함께 맞아야 한다.
[pool 크기와 mask 정의](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/base/allocator/partition_allocator/src/partition_alloc/partition_address_space.h)

| 각 pool 크기 | 두 pool 합계 | 현재2 GiB 대비 예약 VA 감소 후보 | 상태 |
|---|---:|---:|---|
| 512 MiB | 1 GiB | 1 GiB | 패치 생성·원본 대조, 미컴파일 |
| 256 MiB | 512 MiB | 1.5 GiB | 패치 생성·원본 대조, 미컴파일 |

우선512 MiB를 비교 후보로 둔다.256 MiB는 더 빨리 allocator 용량에 도달할 수 있다.
upstream iOS test용256 MiB 경로가 있더라도 Windows guest에 그 설정을 그대로 켤 수는 없다.
이 버전의 동적 pool 선택은 iOS 조건으로 제한돼 있다.
[초기화와 플랫폼 조건](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/base/allocator/partition_allocator/src/partition_alloc/partition_address_space.cc)

이 수치는 **가상 예약 감소 후보**다. 현재 soft pool은 승인 후 native backing/실제 commit이
검증되지 않았으므로 그만큼 물리 RAM이 절약된다는 뜻이 아니다. 약212 MiB CEF 실행 이미지의
JIT 배치, libcef 자체 allocator/V8의 예약, FEX 아레나는 이 DLL 교체만으로 바뀌지 않는다.

새 빌드에는 추가 작업이 필요하다. Windows 빌드 레시피의 source/patch hash와 pool manifest,
load probe의 고정1 GiB 기대값, native hold·주소 정렬·guest pool 선택을 함께 맞춰야 한다.
현재 native soft fallback의1 GiB 이상 조건 때문에 작은 요청이 같은 경로를 탄다고 가정할 수
없다. probe를 통과한 뒤 실제 helper 초기화·commit·로그인·재시작까지 시험해야 한다.
소스 hash 검사나 patch 생성은 컴파일/실기기 검증을 대신하지 않는다.

## FEX 자체도 별도 수정 대상으로 확인했다

사용자가 허용한 FEX 메모리 수정 범위를 다음 조사에 포함한다. 이번에는 FEX 파일을
변경하거나 기존 수정사항을 덮어쓰지 않고, 실제 사용량과 소스의 축소 지점을 대조했다.

1. `FEXCore/Source/Interface/IR/IREmitter.h`는 한쪽8 MiB를 넘긴다.
   `IntrusiveIRList.h`의 dual allocator가 이를 두 배 예약하므로 IR 작업 버퍼 하나가16 MiB다.
   현재 allocator는 자동 확장하지 않으며 가득 차면 실패한다. 단순히2 MiB로 낮추기 전에
   data/list 각각의 사용 최대치와 긴 instruction block을 측정해야 한다.
2. `Frontend.h`는65,536개의 decode slot을 고정한다. 현재 명명된9 MiB view와 대응한다.
   slot 수를 줄이려면 allocation 크기와 decode 종료 조건을 같이 바꿔야 한다.
3. 현재 FEX 소스에서 `MADEIRA_FEX_IR_HALF_MIB`, `MADEIRA_FEX_DECODER_COMPACT`를 읽는 코드를
   찾지 못했다. Build179의 packaged `xtajit64.dll`에도 두 이름의 문자열이 없다.
   설정에 존재한다는 이유로 버퍼 축소가 적용됐다고 판단하지 않는다.
4. 최초 snapshot에서 큰 ALLOC/FREE 때 과거 이름을 지운 뒤 정확한 이름·주소·크기를
   대조하면 OpDispatcher13개/208 MiB가 연결된다. Frontend는13개/117 MiB가 이름과 맞는다.
   작은 view의 완전한 수명 기록은 없어 전체 allocator 소유권 census로 간주하지 않는다.

따라서 FEX 쪽은 IR 사용 최대치 계측과 decoder 용량/종료 조건 검토가 구체적인 다음 대상이다.
이는 rpmalloc의16 MiB span 자체를8 MiB로 바꾸는 문제와 다르다. 또한 Build179의57개
RW span에 남은 미커밋 예약을 객체 확인 없이 해제하는 방법은 채택하지 않는다.

## 결과물과 다음 실험

Build179의 [수명 검증 문서](STEAM64_BUILD179_SPAN_LIFETIME_2026-11-06.md)를 마무리했다.
테스트 PID5209는 정상 종료에 응답하지 않아 같은 앱/실행 경로를 재확인한 뒤 해당 PID만
종료했고, 이후 사라진 것을 확인했다. 다른 앱·설정·prefix를 교체하거나 삭제하지 않았다.

`diagnostics/chrome-elf-rebuild-20261106/`에 ABI 분석기·결과, 역사 소스와 blob/hash manifest,
확인한 upstream 소스, source 재구성 검사와512/256 MiB 후보 patch를 보존했다.
새 DLL·IPA는 만들거나 설치하지 않았다. 현재 설치 버전은 계측용 Build179다.

다음에는 현재 fatal CHECK의 실제 조건을 확보하면서,512 MiB source ELF와 FEX 작업 버퍼
축소를 각각 독립 비교한다. 무료 메모리 entitlement 조건을 유지하며 각 단계의 결과를 기록한다.

## 후속 결과: Build184까지

위의 Build179 설치 상태와 미빌드 표기는 이 문서 최초 작성 시점의 기록이다.
[Build180–183](STEAM64_BUILDS181_183_SOURCE_RESULTS_2026-11-06.md)에서 fatal의 실제 소스 위치,
pool 정렬과 native hold 소유권을 검증했고, 기존 source ELF를 그대로 둔 채 초기 commit 장애를 넘었다.
[Build184](STEAM64_BUILD184_COMPACT_CALLRET_2026-11-06.md)는 FEX CallRetStack 축소를 적용해
약200초 캡처 동안 기존 연속 예약 실패가 나타나지 않았다. 전체 UI 성공은 아니다.

다음 종료 지점은 libcef RVA `0x6923404`의 주소 공간 예약 실패 경로에 부합한다.
libcef 쪽16 GiB급 pool과32 GiB 정렬 fallback은 chrome_elf의1 GiB 수정과 별개로 남았다.
그러므로 다음 소스 재빌드는 chrome_elf만 교체하는 범위에서 **libcef에 포함된 allocator까지**
확장해야 한다. 정확한 Chromium/CEF 버전에서 regular/BRP 크기·mask·정렬의 inline 사용을
모두 함께 컴파일하고, Valve helper와의 ABI를 확인해야 한다. Windows 대상을 iOS 대상으로
위장하거나 feature flag만으로 compile-time pool 크기가 바뀐다고 가정하지 않는다.
기존512/256 MiB header 후보를 전체 CEF에 적용하는 빌드와 호환성 검증은 아직 미수행이다.
