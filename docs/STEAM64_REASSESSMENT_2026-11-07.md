# Steam64 시도 재평가와 다음 실험의 우선순위

2026-11-07 HST. 기존 문서와 Build184–204의 보존 자료를 읽은 후속 분석이다.
이 문서 작성 중 새 빌드·기기 실행·DLL 변경·서명 변경은 하지 않았다.
분석 코드와 개인정보를 제외한 capture summary는
`diagnostics/reassessment-20261107/`에 보존했다.

## 판단을 갱신해야 하는 이유

앞선 응답은 Build184와 libcef 소스 재빌드 준비를 중심으로 설명했다. 로컬에 남아 있는
Build185–204의 후속 캡처·package manifest·현재 소스까지 반영하면 **현재 우선 병목을
여전히16 GiB/32 GiB 예약 실패로 단정할 수 없다.** 최근에는 초기화·리소스·로더·동기화·
화면 전달을 나눠 조사하는 것이 전체 CEF 재빌드보다 먼저다.

| 단계 | 직접 확인한 근거 | 아직 증명하지 못한 것 |
|---|---|---|
| Build177–179 | 작은 FEX 아레나의 큰 예약 수명과 실제 연속 gap 부족 | 모든 미커밋 span을 반환할 수 있는지 |
| Build180–184 | decoder/IR/CallRet 예약 축소, CEF 정렬·native hold 인수;184의 libcef 큰 reserve 실패 | 전체 CEF/UI 성공 |
| Build185–188 | 최신 소스의 compact slot 구성,188의4건 ADOPT;188에서는 FEX failure census가 남음 | compact CEF/V8 mask 전체의 의미적 일치 |
| Build189 | memory entitlement true, EVA false; 주소 상한 `0x8000000000`,16 GiB FEX 아레나 | 모든 무료 계정에서의 동일 발급·동작 |
| Build190–197 | manifest에 delay-load 보충, wake stack/exception 관련 수정이 기록됨 | 각 수정의 원인이 독립 실험으로 확정됐는지 |
| Build198–204 | ResourceBundle·vtable·Crashpad·exception dispatcher 관련 추가 패치;204 캡처에는 기존 FEX failure census 없음 | BrowserReady·실제 로그인 UI·반복 시작 |

Build189의 앱 서명 변경은 패키징 코드와 실행 로그가 함께 뒷받침한다. Build204 staging의
실제 app signature에서도 increased-memory-limit=true / EVA=false를 다시 읽었다.
helper extension은 두 권한 모두 false다. 이것은 실행 앱의 상태이며 계정 membership 전체의
증명이 아니다. increased-memory-limit와 EVA가 별도 키라고 해서 이 기기에서 전자가
주소 상한에 영향을 주지 않는다고 단정해서도 안 된다.

## 가장 최근 캡처에서 확인한 상태

`build204-artifacts/private/capture-20261107-213302/madeira-log.txt`:

- 20,531줄. 기록된 physical footprint peak는2,497 MiB.
- FEX는 `[0x7c00000000,0x8000000000)`의16 GiB 아레나를 기록했다.
- 기존 FEX live failure census, chrome_elf loader 초기화 실패, cef-fatal-site,
  int3 guest record와 exc-disp record는 이 캡처에 없다.
- 기록된1 GiB 이상 alloc-fail도 없다. 이는 해당 marker의 부재이며 장시간 안정성,
  모든 allocation 성공이나 모든 예외 부재의 증명은 아니다.
- 4건의 owned native pool ADOPT가 있다. 소스 slot 설명 기준으로 libcef regular256 MiB,
  libcef BRP256 MiB +guard, Oilpan128 MiB, chrome_elf BRP128 MiB +guard 범위를 인수했다.
 현재 소스의 slot 설명과 일치하지만,
 전체 CEF/V8 inline mask·성장·해제 계약까지 검증한 것은 아니다.
- IR half capacity는2 MiB다. Build188 캡처에는8 MiB도 있어 초기/후기 빌드를 동일한
  설정으로 간주한 메모리 사용량 비교는 부적절하다.
- 최종 관측의 대형 창 하나가1068×492, visible=1이고 같은 HWND의 present가4회 기록됐다.
  class와 title은 빈 값이었다. 창 소유자·CEF 콘텐츠 여부·사용자가 본 실제 화면은 미확정이다.
  present와 일부 signature 변화만으로 로그인 화면을 그렸다고 판단하지 않는다.
- `uxtheme.dll`, `actxprxy.dll`, 일부 `steamservice.dll` 요청은 status=c000007b다.
  다른 optional module의 c0000135도 있다. 모두 필수 장애로 취급하지 않고 실제 호출·영향을 구분한다.
- Madeira 로그에는 BrowserReady가 없다. 별도의 CEF/Steam 로그는 이 캡처에 포함되지 않아
  그 부재만으로 CEF가 해당 단계에 도달하지 못했다고 확정하지 않는다.

## 남은 실험 — 적은 비용 순으로

### 1. 같은 Build204에서 CEF 진행과 화면 전달을 동시에 구분

추가 DLL 수정 없이 실제 helper가 기록한 CEF/Steam 원본 로그부터 수집한다.
CEF 초기화 진입/반환, context/browser 생성, 최초 콘텐츠 paint, Wine surface 갱신,
Winios present를 동일 세션의 HWND·TID·시간으로 연결한다. 현 로그만으로는 blank window가
CEF 초기화 전 정지인지, 콘텐츠 생성 후 전달 실패인지 결정할 수 없다.

GDI 테스트 패턴이 같은 Wine surface와 compositor 경로를 통과하는지도 별도 control로 확인한다.
windowed CEF와 OSR의 paint 경로를 섞지 않는다. 창을 강제로 visible로 만드는 변경은 이미
적용됐고 실제 present도 있어, 같은 변경의 반복보다 이 분리 실험이 우선이다.

### 2. 실제 prefix에서 로더 오류를 구분

첫 대상은 UI와 관련된 `uxtheme.dll`의 c000007b다. 실제 선택된 파일의 SHA·PE/ARM64EC metadata,
import closure·선택 경로를 앱의 정상 후보와 대조한다. 잘못된 image format이라는 status만으로
CPU 아키텍처 불일치를 확정하지 않는다. 잘못된 파일 선택·종속성·hybrid metadata를 함께 본다.
실제 호출이 필요한지 확인한 뒤 해당 모듈 하나만 수정해 동일 UI milestone을 비교한다.

`nvapi64`, 오디오·프린터·서비스 DLL처럼 선택적으로 탐색할 수 있는 모듈까지 무조건
stub으로 채우는 실험은 후순위다. 단순 export 존재와 실제 동작을 구분한다.

### 3. ResourceBundle 우회 패치의 의미를 검증

Build198 이후의 recursion 차단, false 반환, vtable 교체는 manifest/검증 코드에 남아 있다.
crash 감소와 올바른 resource 공급은 다른 결과다. 실제 pak·locale·ICU·V8 resource의 버전,
경로·open/read 결과, 요청 resource ID, handler 반환값과 recursion depth를 좁게 계측한다.
공개 CEF는 handler 유무·pack-loading 설정에 따라 pack 파일 사용 여부가 달라짐을 설명한다.
[CEF126 공개 계약](https://github.com/chromiumembedded/cef/blob/a5d51ba9db7ee74a523dc247bd09ec91ba4d7446/include/cef_app.h#L164)

다만 이 공개 소스와 Steam C API hash는 다르므로 실제 바이너리의 callback/this/vtable slot
계약과 대조해야 한다. 모든 패치를 한꺼번에 되돌리지 않고, 원인이 좁혀진 하나만 비교한다.
항상 false를 반환하거나 assertion을 건너뛴 결과를 초기화 성공으로 세지 않는다.

### 4. 대기가 정상인지 교착인지 확인

최근 sample의 `wait_select_reply/read`는 정상 IPC 대기일 수도 있다. CPU가 낮거나
`srv-stuck` 출력이 있다는 이유만으로 deadlock이라고 판정하지 않는다.
UI 관련 thread별 wait 대상, signal/owner, loader lock 소유자, callback 진입/탈출과
진행 counter를 연결한다. 같은 대기가 계속되면서 소유자가 진행할 수 없는 cycle이 나오는지 본다.
sampler를 껐다는 UI marker와 실제 thread-sample 기록이 함께 존재해, 계측 설정의 실제 적용도 확인한다.

### 5. 안정화 후 메모리·수명 재검증

CEF 콘텐츠 단계가 진행하면 native hold의 helper 재시작 후 반납/재사용, pool 용량 도달,
JIT와 rpmalloc의 live demand, footprint를 장시간·반복 시작에서 검증한다.
최근에 부족 근거가 없는 상태에서 FEX 아레나를 더 키우거나 predictor/IR을 계속 줄이는
실험은 우선순위가 낮다. 특히 rpmalloc span 축소는 size class와 cross-thread free까지 바뀌어
새 오류를 만들 수 있다. 현재2 MiB IR,1 MiB CallRet,compact decoder 적용을 먼저 유지한다.

## 재현성을 먼저 고쳐야 하는 부분

Build204 manifest의 libcef SHA와 staging의 실제 SHA는 일치했다. 그러나 현재
`Steam64Compatibility/PROVENANCE.json`의 chrome_elf SHA는 실제 patched staging과 다르다.
이 파일은 원래 source build 출처로 보존하고, 현재 적용한 모든 binary patch의
원본 hash·offset/RVA·변경 전후 bytes·의도·독립 검증을 별도 manifest로 남겨야 한다.
Build203/204의 libcef SHA도 서로 달라, 공통 패치 몇 곳의 assert만으로 동일 payload라고
가정할 수 없다. 실제 prefix 파일까지 같은 기준으로 대조하는 것이 다음 비교 실험의 전제다.

## 전체 libcef 재빌드의 위치

일치하는 CEF C API/구조체 계약과 Windows 빌드 환경이 미확보라는 제약은 그대로다.
소스 재빌드는 장기적으로 binary patch를 대체하고 재현성을 높이는 방향으로 남긴다.
그러나 후속 자료를 반영하면 현재1순위 실험은 아니며, 작은 pool 재빌드만으로 최신
UI 정지를 해결한다고 볼 근거도 없다. CPU1·L1-only·jitless처럼 이미 적용된 옵션의 단순
재시도보다 위의 로더·리소스·진행·전달 분리가 더 많은 정보를 준다.
