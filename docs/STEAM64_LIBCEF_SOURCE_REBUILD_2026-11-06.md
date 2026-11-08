# libcef 전체 소스 재빌드: 1 GiB 후보와 ABI 선행 검사

2026-11-06 HST. [Build184](STEAM64_BUILD184_COMPACT_CALLRET_2026-11-06.md)의
16 GiB급 pool /32 GiB 정렬 fallback 실패 후속 조사다. 실제 libcef DLL을 새로
컴파일·설치했다는 보고가 아니다. 앱·prefix·계정·서명 상태를 변경하지 않았다.

## 소스 선택 전에 발견한 ABI 차이

기존 source chrome_elf의 Chromium126.0.6478.183만 보고 전체 CEF의 원본 리비전을
같다고 가정하지 않았다. 실제 libcef의 `cef_api_hash`와 `cef_version_info` export를 읽었다.
DLL을 호스트에서 실행하지 않고, PE export table과 검증된 leaf 코드·RIP-relative 문자열·
version jump table을 대조했다. 재현 도구는
`experiments/cef64-full/read-baseline.py`이며 고정된 원본 SHA 이외의 DLL을 거부한다.

| 항목 | 현재 Steam용 libcef | 기존 chrome_elf에 사용한 공개 CEF 소스 |
|---|---|---|
| Chromium | 126.0.6478.183 | 126.0.6478.183 |
| CEF commit | `bbb75964a9f4095daf2926163a63cbf11af56565` | `a5d51ba9db7ee74a523dc247bd09ec91ba4d7446` |
| Windows API hash | `97314fe45c14007fca596262a64cad69467df21f` | `0d99d1b9b85b2efab91a39d6fc325bb6d56fd524` |
| Universal API hash | `908f7378d71977393cee4bc349055b7365c3673c` | `ed1dfa5ff8a041241f8fb72eb7454811f358f0d3` |

현재 DLL의 `cef_version_info(0...7)` 값은
`[126,0,0,3171,126,0,6478,183]`이었다. 바이너리 SHA는
`c85bf94462b3c79baeac63823db52d15e116eead71ea414e5d3a112c59e434d3`로 고정했다.
named export222개와 두 함수의 메타데이터를 별도 분석 및 재현 도구로 다시 대조해 일치했다.

공개 CEF의 [API hash header](https://github.com/chromiumembedded/cef/blob/a5d51ba9db7ee74a523dc247bd09ec91ba4d7446/include/cef_api_hash.h)는
C API 타입 정의 변경으로 binary incompatibility가 생길 수 있을 때 hash가 달라짐을 설명한다.
따라서 같은 Chromium 버전만으로 공개 libcef를 Steam의 drop-in replacement로 인정할 수 없다.
hash 반환값만 기존 값으로 위장하는 방법도 채택하지 않는다.

현재 DLL이 반환하는 commit의 upstream GitHub 조회는422, 해당 commit의 raw header 조회는404,
추측한 `ValveSoftware/cef` 저장소 조회는404였다. 일치 소스의 출처는 아직 미확정이다.
이 결과가 소스의 비공개 여부나 Valve 고유 변경 전체를 증명하지는 않는다.

REA/Ghidra로 정확한 `cef_api_hash` 함수41바이트 조각을 분석한 Evidence는
`ev_97080362dbc782602278253cdff39a186adde876f4d314b9e8c3f02150b31fed`다.
각 entry가 반환하는 문자열 주소와 NULL 경로는 disassembly와 일치했다. 외부 문자열은 원본 PE에서
별도로 읽었다. fragment manifest에 원본 offset·RVA·SHA를 보존했으며 조각 분석을 전체 DLL의
의미나 Windows 실행 검증으로 취급하지 않는다.

## 실제로 준비·검증한 결과물

`experiments/cef64-full/`에 다음을 추가했다.

- `baseline-contract.json`: 현재 DLL의 API hash·version·222개 export metadata. 바이너리는 포함하지 않는다.
- `public-control.json`: 공개 Chromium/CEF·depot_tools pin과 원본 source hash. Steam ABI와 불일치를 명시한다.
- `prepare.py`: 일반적인 전체 CEF 소스 트리에 적용하는 pool 패치. 기존의 축소된 chrome_elf 전용
  BUILD.gn 트리를 거부하고, 예상 source hash와 다른 파일·기존 결과 폴더를 덮어쓰지 않는다.
- `contract-probe.c`: 정상 LoadLibrary 초기화 후 CEF hash/version을 읽는 Windows 실행 검사 도구.
  hash나8개 version 값이 다르면 exit4다. 성공해도 Steam UI 검증으로 간주하지 않는다.
- `README.md`: 정확한 소스 pin·전체 빌드 명령·자료 보존 및 수용 조건.

첫 후보는 regular/BRP 각각1 GiB다. 현재 native source ELF의 크기와 같게 하여 큰 libcef 요청을
축소하는 첫 비교 대상으로 삼는다. regular/BRP 두 선언만 변경하고, inline mask의 원래 유도식,
BRP guard·assertion·실패 경로는 그대로 둔다. 최대 용량 bitmap 설정이나 다른 V8 cage 크기는
이 두 선언과 다른 요소일 수 있다. 전체 트리에서 모든 allocator 복사본을 함께 빌드해야 한다.

패치 결과 header SHA:
`fedb32f72d53d255018f5a9ec1fbcc308dc1dfd57c629e84f19137e2ec93edfb`.
원본 hash·patch hash·대조 결과는 `diagnostics/libcef-rebuild-20261106/candidate-1g/`에 있다.
초기 미컴파일 후보의 단위 이름 의존성을 제거한 수정 전 결과도 별도 보존했다.

호스트 검사는256/512/1024 MiB 후보 각각에 대해 두 선언 외의 모든 바이트 보존, 변경된 소스의
재패치 거부, source drift·미검토 크기 거부, 기존 결과와 입력 파일 보존을 통과했다.
이는 full CEF의 실제 컴파일이나 allocator 실행 검사는 아니다.

Windows probe는 기존 LLVM-MinGW로 AMD64 PE EXE를 실제 크로스 컴파일했다.
최초 `UNICODE` macro 중복 오류를 include guard로 수정한 뒤 `-Wall -Wextra -Werror`로 통과했다.
이 EXE는 libcef가 아니며, Windows나 iPhone에서 실행하지 않았다.

## 실제 빌드가 아직 안 된 이유

현재 Mac의 RAM은8 GiB이며 Windows Visual Studio/SDK 환경이 확인되지 않았다.
연결된 두 원격 shell connector는 parameter 수정 뒤에도 internal error를 반환했다.
`kimdongup/iDeck`의 GitHub Actions workflow 조회 결과는0개였으며 기존 Windows job은 없다.
사용자도 사용 가능한 Windows 빌드 PC나 소스 작업 폴더가 없다고 답했다.

이번에는 필요한 고정 리비전의 공개 source 파일만 받았다. 전체 Chromium 의존성 checkout이나
full libcef 컴파일을 시작한 것은 아니다. 새 유료 서비스·계정·workflow를 생성하지 않았다.
현재 receipt의 `compiled=false`, `replacement_eligible=false`는 이 상태를 정확히 표시한다.

공개 CEF 전체 빌드 환경을 확보해도 우선 **메모리 예약 동작을 검증하는 control**이다.
Steam 교체 후보를 만들려면 일치하는 CEF C API 선언·callback/구조체 계약의 출처를 확보하거나
차이를 충분히 검증해야 한다. export 이름222개 충족만으로 그 검증을 대신하지 않는다.

## 이어갈 수용 조건

1. Windows CEF 전체 빌드 환경에서 공통 header 패치를 libcef·chrome_elf에 함께 적용한다.
2. 원본 전체 BUILD.gn과 CEF 공식 hook을 사용해 DLL·pak·ICU·V8 runtime 자산을 같은 빌드에서 만든다.
3. probe의 정상 초기화, API·version 및 실제 helper의 요구 export/동적 인터페이스를 확인한다.
4. native Wine이 각 allocator 복사본의 pool을 구분하고 실제 backing/commit을 제공하는지 검증한다.
5. entitlement 없는 조건에서16 GiB/32 GiB 요청 감소, 실제 연속 예약, BrowserReady·로그인·반복 시작을 확인한다.

소스 수정은 직접적인 해결 후보지만 이번 ABI 검사와 host/probe 컴파일 결과로 실제 libcef
재빌드·CEF 초기화·Steam 성공을 보고하지 않는다. 기존 Build184 앱과 prefix는 그대로 보존한다.
