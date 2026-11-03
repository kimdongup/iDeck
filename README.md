# iDeck — Gemini Lightweight Analysis Snapshot

Branch: analysis/build125-gemini-lite-20261103

이 브랜치의 최신 커밋 트리에는 Build 124/125 분석 문서만 담았습니다. iDeck/FEX/Wine/DXMT의 전체 소스와 실행 파일, 실제 디바이스 로그는 포함하지 않습니다.

## 읽는 순서
1. GEMINI_ANALYSIS_TASK.md
2. evidence/BUILD124_OBSERVATIONS.json
3. docs/handoffs/BUILD125_GLYPH_CLUSTER_FAILURE_TRIAGE.md
4. docs/handoffs/BUILD124_GLYPH_CLUSTER_EXECUTION.md

## 별도 작은 복제

기존 Mac 저장소로 pull하지 마십시오.

~~~bash
git clone --depth 1 --single-branch --branch analysis/build125-gemini-lite-20261103 https://github.com/kimdongup/iDeck.git iDeck-gemini-analysis
cd iDeck-gemini-analysis
du -sh .
~~~

이 브랜치 최신 스냅샷만 작습니다. 원본 GitHub 저장소의 전체 Git 히스토리가 작아지는 것은 아닙니다. Gemini가 전체 저장소를 인덱싱하는 방식이면 100MB 제한이 다시 나타날 수 있습니다. 그 경우 이 브랜치의 문서만 직접 주십시오.

실제 로컬 코드 리뷰가 필요하면 사용자가 별도로 소유한 0.9MB 파일 build124-critical-source-20261103-055816.zip을 업로드하게 하십시오. 이 ZIP은 공개 GitHub에 올리지 않았으며 미커밋 작업 코드를 포함할 수 있습니다.

실행 관련 지시는 Glyph Cluster에게, 분석·검증 가설은 Gemini에게 배정합니다. 이 브랜치를 iDeck 실제 로컬 작업 브랜치에 merge/pull하지 마십시오.
