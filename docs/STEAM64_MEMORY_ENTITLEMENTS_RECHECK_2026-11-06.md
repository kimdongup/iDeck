# 무료 계정과 GetMoreRam: 메모리 entitlement 전제 재검토

2026-11-06 HST. 공개 소스 조사이며 Apple 계정·App ID·서명·설치 상태는 변경하지 않았다.

## 확인한 동작

GetMoreRam commit `52f5e964cf262dd1b8f4a1b93cde22b79a1fdd3f`의
[AppIDViewModel.swift](https://github.com/hugeBlack/GetMoreRam/blob/52f5e964cf262dd1b8f4a1b93cde22b79a1fdd3f/GetMoreRam/AppIDViewModel.swift#L28)는
로그인된 team/session으로 `AppleAPI.shared.updateAppID`를 호출하며
capability로 `INCREASED_MEMORY_LIMIT`를 전달한다. 이 버튼의 코드에는
`extended-virtual-addressing` 활성화나 IPA 서명 위조 처리가 없다.

[AltSign의 관련 커밋](https://github.com/rileytestut/AltSign/commit/b2c8861793)은 GetMoreRam
구현을 바탕으로 App ID의 `bundleIdCapabilities`를 Apple Developer Services에 PATCH한다.
이는 서버가 허용하는 capability를 활성화하는 요청이다. 서버 승인 없이 임의 entitlement를
유효한 권한으로 만드는 기능이라고 해석하지 않는다.

[GetMoreRam 사용 순서](https://github.com/hugeBlack/GetMoreRam)는 capability 변경 후
SideStore/AltStore에서 대상 앱을 다시 설치하도록 요구한다. 실제 적용에는 다음이 필요하다.

1. Apple 서버가 대상 App ID에 capability를 허용한다.
2. 재발급한 provisioning profile이 필요한 권한을 허용한다.
3. 재서명한 실행 파일이 해당 entitlement를 실제로 요청·유지한다.
4. 설치·실행 후 실제 entitlement와 프로세스 메모리 예산을 검증한다.

## 두 권한을 구분

| 키 | 목적 | 이번 조사에서 확인한 범위 |
|---|---|---|
| `com.apple.developer.kernel.increased-memory-limit` | 지원 기기에서 앱 메모리 한도 증가 요청 | GetMoreRam의 명시적 요청 대상 |
| `com.apple.developer.kernel.extended-virtual-addressing` | 확장된 가상 주소 공간 접근 | 위 버튼이 활성화한다는 근거 없음 |

Apple 문서: [Increased Memory Limit](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit),
[Extended Virtual Addressing](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.extended-virtual-addressing),
[Provisioning Profiles](https://developer.apple.com/documentation/technotes/tn3125-inside-code-signing-provisioning-profiles).

무료 계정의 increased-memory-limit 적용 보고와 SideStore의 capability 누락 문제는
[SideStore issue1616](https://github.com/SideStore/SideStore/issues/1616)에 있다.
이는 구체적인 사용자 보고이며 모든 계정·서명 도구 버전·iOS에서의 성공 보장은 아니다.
이 프로젝트의 현재 계정에서 Apple 서버가 허용하는지는 아직 시험하지 않았다.

## iDeck 조사에 반영

“무료 계정이므로 increased-memory-limit는 사용할 수 없다”는 일반화는 철회한다.
무료 계정의 capability/profile 발급을 검증하는 경로를 추가할 수 있다.
이는 유료 가입 여부와 entitlement 사용 여부가 서로 다른 조건임을 뜻한다.

기존 Build179–184가 두 entitlement를 제외해 수행됐다는 실제 서명·실험 기록은 유지한다.
추가 물리 메모리 예산을 받더라도 Build184의 libcef16 GiB급 pool/32 GiB 정렬 fallback이나
FEX 연속 주소 공간 문제가 자동으로 해결된다고 단정하지 않는다. EVA의 실제 허용 여부와
native 주소 공간·연속 예약 성공을 별도로 측정해야 한다.
