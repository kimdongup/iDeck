# Build180: 소스 재컴파일과 CEF 실패 조건 검증

2026-11-06 HST. 사용자의 FEX 수정 및 소스 재컴파일·실기기 검증 요청을 반영한다.
[Build179](STEAM64_BUILD179_SPAN_LIFETIME_2026-11-06.md)를 비교 기준으로 사용한다.
기존 수정사항·설정·prefix를 보존하고 추가 메모리 entitlement를 사용하지 않는다.

## 이번 변경

- FEX decoder: Windows에서 `MADEIRA_FEX_DECODER_COMPACT=1`이면65,536개 대신4,096개
  instruction slot을 예약한다. allocation과 decode 종료 조건이 동일한 instance capacity를
  사용한다. 슬롯 쓰기 직전에도 범위를 검사한다. 현재 slot 크기144바이트 기준9 MiB에서
  576 KiB로 줄어든다. 다음 guest PC에서 번역을 계속하며 guest 전체 실행 길이를 제한하지 않는다.
- FEX IR: 기존8 MiB +8 MiB 용량을 유지한다. `MADEIRA_FEX_IR_USAGE_TRACE=1`일 때 reset
  직전에 data/list 최대 사용량을 계산하고64 KiB 구간을 넘을 때만 기록한다.
  실제 사용량 없이 고정 용량을 줄여 overflow를 유발하지 않는다.
- native CEF 진단: pin된 CEF126 fatal logging layout을 읽어 알려진 allocator 소스 파일명과
  줄 번호만 기록한다. guest 문자열을 그대로 출력하거나 exception을 우회하지 않는다.
  Mach의 안전한 읽기로 opcode·severity·주소 overflow·파일명 whitelist를 검증한다.

FEX의 기존 파일·MIT 고지는 유지했다. 변경 전 네 파일과 native source·archive·DLL을
`build180-artifacts/`에 보존했다. 기존 rpmalloc gitlink 및 InvalidationTracker 수정은 유지한다.
현재 요청에 따른 로컬 실험이며 upstream 기여나 commit/push를 수행하지 않는다.

## 빌드 및 호스트 검증

- 실제 decoder의 capacity 선택·쓰기 전 guard·종료 식을 추출한 ASAN/UBSAN 검사가 통과했다.
  두 용량의 마지막 유효 slot, 작은 instruction 제한, 경계 초과 쓰기 거부를 확인했다.
  완전한 x86 decode/IR 의미 검사를 대신하는 테스트는 아니다.
- 실제 CEF fatal-site reader의 정상 경로·읽기 실패·overflow·잘못된 opcode/severity/파일명
  검사가 ASAN/UBSAN에서 통과했다.
- LLVM-MinGW로 `arm64ecfex` target을 재컴파일·링크했다. native signal object도 컴파일했다.
  FEX의 기존 volatile 증가 경고 두 건은 남으며 컴파일 오류는 없다.
- native archive는 `signal_arm64.o`만 변경됐다. 디버그 정보를 제거한 FEX DLL은 비디버그
  section의 virtual bytes와 RVA/크기가 원본 컴파일 결과와 동일함을 대조했다.
- 증분 Xcode 빌드 및 app/helper deep/strict 서명 검증이 통과했다. 두 선택적 메모리
  entitlement는 실제 서명에서 제외됐다.
- PE1,302개 중 `arm64ec-windows/xtajit64.dll`만 재컴파일한 FEX로 바꾸었다.
  나머지는 Build179와 바이트가 같다. chrome_elf는 기존1 GiB source build를 유지한다.

## 실기기 판정 항목

실행 환경에 decoder compact·IR usage trace·CEF fatal trace를 명시적으로 전달한다.
먼저 실제 `[fex-memory]` 출력과 native view의576 KiB를 확인한다. 이후 FEX 연속 할당 실패,
IR 최대 사용량, CEF fatal 파일/줄, helper 종료·진행을 비교한다. 소프트 예약 승인이나
컴파일 성공만으로 초기화·로그인 성공을 선언하지 않는다.

## 실기기 결과

동일 앱 ID로 업데이트 설치하고 PID5290으로 실행했다. 첫 캡처는
`private/capture-20261106-133239/madeira-log.txt`다. 설정은 설치 전과 바이트가 같다.

- decoder 출력30건이 모두 `slots=4096 bytes=589824 default_slots=65536`이었다.
  소스 수정과 재컴파일한 DLL이 실제로 실행됐음을 확인했다.
- CEF fatal은 `address_pool_manager.cc:58`, severity3이었다. 정확한 pin 소스의 해당 줄은
  pool 시작 주소가 super-page(2 MiB) 경계에 맞는지 검사한다.
- 기존 soft fallback은 BRP의1 GiB+64 KiB 요청에도 일반 정렬 주소를 반환한다.
  CEF가 여기에64 KiB guard를 더하면 pool base가 어긋나는 경우를 재현할 수 있다.
  다음 native 수정은 실제 pool 쪽을 정렬한 guard base를 반환하고, 그 실제 범위로
  중첩·band 끝·overflow를 검사하도록 한다. assertion을 제거하지 않는다.
- 기록된 IR data/list peak는250,636/421,100바이트였다.64 KiB 구간을 넘을 때의
  checkpoint 최대값이며, 전체 workload의 절대 최대치나 작은 고정 용량의 안전 보장은 아니다.
- FEX 아레나는1,408 MiB였고16 MiB 요청이 실패했다. 전체 빈 공간19.309 MiB,
  최대 연속/정렬 빈 공간7.688 MiB였다. RW16 MiB span은59개/944 MiB였다.
- 샘플링된 physical peak는2,377 MiB로, Build179의2,269 MiB보다 높았다.
  아레나 배치와 진행 상태도 달라서 decoder 예약 감소를 물리 사용량 개선으로 보고하지 않는다.
  CEF 초기화·전체 Steam 로그인 성공은 아직 확인되지 않았다.

기록된 큰 예약의 수명과 최초 live view를 대조한 불일치는 없었다.
실험 종료 후 정확한 앱/실행 경로를 확인한 PID만 종료했다. 정상 종료에 응답하지 않아
해당 PID에 한해 SIGKILL을 사용했고, 이후 process 목록에서 사라진 것을 확인했다.
다른 앱·설정·prefix는 변경하지 않았다.

재현 자료: `build180-artifacts/baseline-provenance.json`, `native-provenance.json`,
`package-manifest.json`, `fex-build.log`, 두 호스트 검사 및 새 native/DLL snapshot.
