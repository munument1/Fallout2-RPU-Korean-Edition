# Fallout 2 RPU 한국어판 정밀 검수 인계

## 목표
이 채팅에서는 Fallout 2 Restoration Project Updated **v2.4.34 기준** 한국어 번역을 화자별·상황별로 정밀 검수한다. 기존의 간단한 어미 분류 결과는 참고 자료일 뿐 확정 오류 목록이 아니다.

## 소스
- 저장소: https://github.com/munument1/Fallout2-RPU-Korean-Edition
- 작업 브랜치: `ko/v2.4.34`
- 한국어 대사: `data/text/korean/dialog/`
- 영어 원문: `data/text/english/dialog/`
- NPC 스크립트: `scripts_src/main/` 및 `scripts_src/`의 각 하위 폴더
- 말투 1차 보고서: https://github.com/munument1/Fallout2-RPU-Korean-Edition/actions/runs/39009955472
- 주요 후보: hcmarcus(마커스), kcsulik(슐릭), vclynett(리네트), qhprzrch(리처드슨), ahmonk 등.

## 특별 주의
현재 원본 저장소 `master`는 기존 번역 기준 릴리스 v2.4.34와 **변경 파일 3,765개**가 있다. 정밀 검수 중 원본 `master`를 번역 브랜치에 자동 병합하지 않는다. 해당 버전의 영어 원문과 스크립트를 우선 비교한다. 개발 브랜치 변경분은 별도 이슈 #1에 기록한다.

## 검수 원칙
1. 대사 파일에 NPC·플레이어·내레이션이 혼재하므로 MSG ID와 스크립트 `Reply()`, `NOption()`, `GOption()`를 추적한다.
2. NPC마다 기본 말투를 명시한다. 분기·상대방·위협·친밀도 변화에 따른 자연스러운 예외는 함부로 통일하지 않는다.
3. 같은 화자의 존댓말·반말, 하오체·해요체 혼재를 문장 맥락까지 살펴보고 결정한다. 단순 분류기는 문장 끝의 `요`, `다` 등에 오탐이 있다.
4. 원문 의미, 인칭·호칭·성별, 조사, 고유명사, 선택지 연결, 줄바꿈 및 게임 토큰을 검수한다.
5. 수정은 CP949와 원본 MSG의 ID·스크립트 참조를 보존하고 파일 단위 소규모로 진행한다.
6. 검수 수정된 파일만 `python korean/update_manifest.py --apply <정확한 상대경로>`로 목록 갱신한 뒤 ZIP 재빌드 및 테스트.
7. 변경 전후 근거·화자별 말투 규칙·허용 예외를 `korean/register-decisions.csv`와 검수 기록에 남긴다.
8. 기존 RPU-KR 번역 저장소, 원본 `master`, 실제 게임 설치본, 공개 Nexus 릴리스는 사용자 승인 없이 변경하지 않는다.

## 시작 순서
마커스, 슐릭, 리네트 등 말투 혼용이 두드러지는 화자를 우선 검수하고, 검수 진행표를 유지하면서 전체 대사로 확대한다. 첫 75개 스크립트 검사 결과로 '완료' 선언하지 않는다.