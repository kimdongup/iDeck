# Gemini 분석 지시서 — Build 124 CEF 실패 / Build 125 설계

**역할:** 실제 코딩·Mac 빌드는 Glyph Cluster, 독립적인 소스 검토·원인 분석·재현 실험 설계는 Gemini.
**보고 언어:** 한국어.
**목표:** iPhone에서 계속 나타나는 connecting steam controls… 의 첫 실패를 정량 근거로 좁힌다.

먼저 evidence/BUILD124_OBSERVATIONS.json 및 docs/handoffs/BUILD125_GLYPH_CLUSTER_FAILURE_TRIAGE.md를 읽으십시오.

## 분석 질문
1. 최초 CEF NOTREACHED check.cc(376)의 진짜 호출자·실패 조건을 특정하려면 어떤 guest PC/RVA, call stack, debug.log, command line, 환경변수가 필요한가? check.cc 출력만으로 원인 단정 금지.
2. FEX last-page mprotect 경고 161건 vs build124-guard marker 0건: stale native link, 조건 미도달, 문자열 제거, 로그 채널 차이를 구분하는 최소 검사법.
3. guest store-noalias 및 write fault가 최초 CEF 실패의 원인인지, 후행 오류인지 구분하는 시간 순서와 instrumentation.
4. FEX 16GiB 가상예약 영역 사용 39% (짧은 Build124 캡처) vs 94% (긴 Build123 캡처). 실행 시간 차이를 통제한 alloc/free 추적법.
5. FD CROSS! Build123 49건, Build124 짧은 캡처 0건. 로그 테이블 stale 여부와 실제 close 실행을 분리하는 검증.
6. Build125에서 증거를 더 많이 얻을 최소 변경 세 가지와 변수 하나씩 A/B 실험 설계.

## 결과
- 확인된 사실 / 증거 위치
- 경쟁 가설, 신뢰도, 반증 조건
- 우선적으로 필요한 로그/소스
- 3개의 최소 실험: 변수, 관찰, 합격·불합격 기준
- Glyph Cluster에게 넘길 구현 지시(구체적인 코드 읽었을 때만 파일·함수 단정)
- 위험과 롤백 경로
- 현재 판단 불가능한 내용

## 범위와 안전
- 이 GitHub 브랜치는 **문서만** 보유합니다. FEX/Wine 현재 로컬 수정 코드는 없습니다.
- 필요 시 사용자가 약 0.9MB 핵심 소스 ZIP을 별도로 제공합니다.
- 기존 iDeck, FEX, Wine 작업을 변경하거나 공개 저장소에 미커밋 코드를 push하지 않습니다.
- 앱 설치/삭제, 데이터 초기화, GitHub Actions, 강제 checkout/reset/clean 금지.
- 원본 로그의 계정/토큰/기기 식별자를 공개하지 않습니다.
- Build124 IPA 빌드 성공과 Steam UI 정상 작동은 다른 검증 단계입니다. BrowserReady + UI 표시 + 입력 수락을 별도로 확인합니다.
