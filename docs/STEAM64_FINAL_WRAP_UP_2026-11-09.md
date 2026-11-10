# iDeck / Steam64 조사 종료 기록

시도 사이의 의존 관계와 검증 경계를 탐색하려면
[Build100–217 상세 분기 지도](build100-to-217-ramification-map-detailed.html)와
[구조화된 분석 데이터](build100-to-217-ramification-map-detailed.json)를 참조한다.
지도는 기존 기록을 세분화한 문서이며 새로운 실행 성공이나 실험 재개를 뜻하지 않는다.

**종료일: 2026-11-09 HST. 최종 판정: 목표 달성 실패.**

사용자가 모든 시도의 실패를 알리고 프로젝트 마무리와 기록 보존을 요청했다.
이 조사 라인의 추가 실험·빌드·기기 설치를 종료한다. 실제 Steam64의 안정적인 초기화,
로그인·라이브러리·Big Picture·게임 실행과 복귀를 연결하는 수용 기준을 충족하지 못했다.
현재 소스를 동작하는 Steam64 제품이나 성공한 릴리스로 소개하지 않는다.

과거 README의 데모와 Steam32/다른 Madeira 실험 기록은 각 당시의 별도 결과다.
그 기록을 삭제하거나 이 Steam64 조사 라인의 성공으로 소급하지 않는다.
GitHub 저장소 자체의 archive 설정이나 과거 release는 이 요청으로 변경하지 않는다.

## 조사 범위와 남기는 결과

| 시도 | 관측·산출물 | 종료 시 한계 |
|---|---|---|
| CEF 실행 이미지/JIT 배치·native 예약·Wine view 인수 | 실제 소유권 확인과 정렬·해제 검사, 계측 | 전체 CEF 초기화·장시간 안전성 불확정 |
| FEX 연속 공간과 작업 버퍼 | decoder/IR/CallRet 축소, arena/bands·high-window 배치, 수명 추적 | 일부 실패를 넘었지만 전체 Steam64 목표 실패 |
| 메모리 entitlement | 권한을 제외한 실험과 increased-memory-limit가 적용된 후속 실험을 구분 | 무료 계정 일반 보장·EVA 허용을 증명하지 않음 |
| CEF 재빌드 | 정확한 공개 소스 pin, 작은 pool 패치, CEF metadata probe | Windows full CEF 빌드 미수행; Steam C API hash와 공개 소스 불일치 |
| CEF 바이너리 실험 | pool/resource/vtable/Crashpad 관련 후보·패치 출처 기록 | 올바른 ABI·resource 공급·callback 의미를 전체 검증하지 못함 |
| Wine ARM64EC·exception·wake 경로 | stack/dispatch/loader/provider 관련 소스·후보와 계측 | 개별 증상 감소는 최종 실행 성공이 아님 |
| UI 표시·surface 전달 | 창 생성·visible·present 관측, 표시/occlusion 실험 | 실제 CEF 콘텐츠·사용자 수용 기준 미확인 |
| 최종 IPC/동기화·주소 배치 | SteamChrome mapping/event, handle 상속, pipe/process, request/reply, CodeRange/bands 조사 | 원인과 수정의 전체 통합 검증 미완료 |

핵심 경과는 [Build152 handoff](STEAM64_BUILD152_HANDOFF_2026-11-04.md),
[무권한 메모리 검토](STEAM64_NO_EXTRA_MEMORY_REVIEW_2026-11-06.md),
[Build180](STEAM64_BUILD180_SOURCE_MEMORY_2026-11-06.md),
[Build181–183](STEAM64_BUILDS181_183_SOURCE_RESULTS_2026-11-06.md),
[Build184](STEAM64_BUILD184_COMPACT_CALLRET_2026-11-06.md),
[libcef 소스 재빌드 조사](STEAM64_LIBCEF_SOURCE_REBUILD_2026-11-06.md),
[Build204까지의 재평가](STEAM64_REASSESSMENT_2026-11-07.md)에 있다.
옛 문서의 “다음 실험”은 당시 계획으로 보존하며 현재 진행 약속이 아니다.

## 마지막으로 남은 작업

로컬 자료는 Build217 및 `build217-bands-artifacts/`까지 존재한다.
최종 미커밋 소스에는 native FEX arena/bands·near-builtins CodeRange 배치,
Steam 직접 실행과 config_guard opt-in, IPC/handle/pipe/request 진단,
Wine host 주소 상한 반영, FEX thread/CallRet 예약 실험이 포함돼 있다.
이는 실패한 조사 종료 시점의 소스 보존이며 검증된 해결책으로 승격하지 않는다.

보존된 마지막 bands 캡처에도 Madeira 로그의 BrowserReady marker는 없다.
일부 로그에 FEX failure나 exception marker가 없더라도 실제 CEF/Steam 내부 로그 전체,
화면·기능·장시간 수용 결과를 대체하지 못한다. 일부 후보는 계측과 여러 패치를 함께 바꿔
단일 수정의 인과 효과가 독립적으로 입증되지 않았다.

코드·패키지·설치된 prefix가 항상 같은 후보였는지도 완전히 입증되지 않았다.
원본 source provenance와 후속 binary patch provenance를 구분해야 한다.
현재 상태만으로 “원인은 하나였고 해결됐다”거나 “iOS에서 원천적으로 불가능하다”고 결론 내리지 않는다.

## 보존·게시 원칙

- GitHub에는 이 프로젝트의 소스, 실험 도구·호스트 검사, 공개 라이선스, 분석 문서와
  서브모듈 commit 참조를 보존한다. 실패/미검증 상태를 명시한다.
- Valve/game 바이너리, IPA·정적 라이브러리·빌드 트리, 서명·provisioning 자산,
  계정·인증 정보와 원본 기기 로그는 Git에 게시하지 않는다. 기존 로컬 파일은 삭제하지 않는다.
- 실행 산출물은 워크스페이스의 `build*-artifacts/`, 원본 로그는 각 `private/`,
  분석 자료는 `diagnostics/`에 남긴다. 이 경로들은 GitHub clone에 자동 포함되지 않는다.
- 실험 진단에는 command-line/IPC 등 민감한 payload가 포함될 수 있어 원본 로그를 공유하지 않는다.
  공개 기록에는 필요한 categorical 결과와 비민감 hash만 남긴다.
- FEX·Wine 수정은 사용자 fork에 보존한다. upstream에 제출하거나 검증 완료 수정으로 소개하지 않는다.
  dxmt·madeira-dock·중첩 rpmalloc 등 변경 없는 서브모듈은 기존 pin을 유지한다.

## 검증 경계와 재현 조건

종료 작업은 문서 링크·게시 대상·소스 차이와 최종 호스트 검사를 확인한다.
새 전체 빌드·기기 실행·성공 릴리스 검증은 수행하지 않는다.
`check-fex-arena-bands.py`는 추출 allocator/주소 배치 검사,
`check-coderange-near-builtins.py`는 소스 구조 검사다. 이들의 통과가 Steam64 성공은 아니다.
실제 결과는 이 문서 아래의 종료 검증 기록으로 남긴다.

종료 시 재실행 결과:

- `check-fex-arena-bands.py`: PASS. 추출 allocator의 band 선택·round-up·fallback·bounds 검사.
- `check-coderange-near-builtins.py`: PASS. 소스 구조·fallback·steering gate 검사.
- 종료 시 변경한 iDeck/FEX/Wine 소스의 `git diff --check`: 통과.
- 전체 native/FEX/Wine 재컴파일·새 IPA 설치·Steam 실행: 수행하지 않음.

향후 별도 연구를 재개한다면 고정한 source/submodule revision, 실제 배치 DLL과 patch manifest,
같은 CEF resource 세트, 서명 entitlement, 실제 prefix hash, 기기·OS·JIT 조건과 capture를
한 세션에 연결해야 한다. Windows full CEF 재빌드에는 별도의 적절한 빌드 호스트와 일치 ABI가 필요하다.
이는 보존 자료의 재현 조건이며 추가 작업 약속이 아니다.

## 종료 시 보존한 서브모듈 revision

| 저장소 | 브랜치 / 보존된 commit |
|---|---|
| kimdongup/FEX | `ios-port-2607` / `5890832f4feaac024f0f48db4f4e5ff5812aa579` |
| kimdongup/wine | `madeira-lgpl` / `feb21585147e341cbf56dedee0ee1a436a63c00d` |
| kimdongup/dxmt | 고정 commit `128b297c6e9a00014408dc68b4c2c2373b5813de` |
| kimdongup/madeira-dock | 고정 commit `72558e416a390f3669457930f09a389e54f49556` |
| kimdongup/rpmalloc (FEX 내부) | `ideck/ios-madeira` / `9c4e5470603964362bff59f7369459150a81946b` |

이 표를 포함한 iDeck 종료 커밋이 parent gitlink를 고정한다. 변경이 없는 서브모듈에는
빈 커밋을 만들지 않는다. 사용자는 이번 마무리 작업에 한해 HST 평일 게시 시간 제한의
예외를 명시적으로 허용했다. 이후 작업의 기본 시간 규칙은 바꾸지 않았다.
