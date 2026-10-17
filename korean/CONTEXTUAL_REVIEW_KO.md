# Fallout 2 RPU — NPC / SSL / 용어집 기반 로컬 번역 비교기

## 현재 제공하는 것

1. contextual_review_queue.py는 각 MSG ID의 **동일 HEAD 영문 대사와 실제 SSL 역할**
   (NPC Reply, 플레이어 Option, 대사 연결 문자열 mstr)을 구분합니다.
2. contextual_review_profiles.json은 지금까지 수동 검수한
   **마커스·술릭·리네트·리처드슨·수도원장·아로요 전사·장로·고리스**
   8개 파일의 말투·설정과 반드시 보존할 용어를 담고 있습니다.
3. 첫 번째 모델 **Hy-MT2-7B Q8**이 영어 원문을 직접 번역하고, 기본값에서는
   **TranslateGemma 12B**가 같은 정보로 독립 번역합니다.
4. state.json에 완료 ID를 저장하고 comparisons.jsonl에
   파일·영문·원래 한국어·SSL Node/화자·모델별 번역·용어집 위반·구조 위험을 기록합니다.
5. 분기/원문을 확신할 수 없으면 표시만 하고 **원문 MSG/manifest/ZIP을 전혀 수정하지 않습니다.**

명칭·형식 위반을 자동 검출하는 것과 의미·인물 성격·어조를 제대로 판단하는
것은 별개입니다. 두 모델이 같은 오류를 범할 수 있으므로
**일치한 출력도 자동 정답 처리하지 않습니다.**

## 수동 시범 또는 한 NPC 검수

저장소 루트 PowerShell 기준:

    python korean/contextual_review_queue.py --file qhprzrch --ids 250,266,276 --max-items 3
    python korean/contextual_review_queue.py --status

다른 NPC 시범:

    python korean/contextual_review_queue.py --file ocgoris --max-items 15

이어서 실행할 때도 이전에 검사한 동일 입력은 건너뜁니다.
--model hy를 쓰면 1차 모델만 호출하되 **반드시 다른 --out 디렉터리**를 지정해야
기존 2모델 비교와 결과가 섞이지 않습니다.

예: --model hy --out korean-contextual-review-hy --max-items 20

--file 없이 실행하면 우선순위가 높은 나머지 NPC부터 전 파일에 대해
검수 후보를 순차 생성합니다. 처음부터 **전수 수정이 완료됐다고 간주하면 안 됩니다.**
의도치 않은 컴퓨터 장기 점유를 막으려고 기본 한 실행은 **5개 ID/15분**만 처리합니다.

## 안정성·제약

- 문장별 PC/NPC 역할이 충돌하면 강제로 말투를 지정하지 않습니다.
- *아직 검수 기록이 없는 NPC*에는 다른 NPC의 어투를 일괄 전파하지 않습니다.
- mstr()로 이어 붙인 대사와 주석 처리된 경로는 확정 NPC 발화로 가정하지 않습니다.
- 옆에 있는 MSG ID는 **게임에서 실제 연속되는 선택지라고 보장하지 않습니다.**
  실제 연결 경로는 SSL Node 등에서 추가로 확인해야 합니다.
- CP949, printf 치환식, HTML 태그, 대괄호 지시어, 엄격한 게임 용어집을 검사하고
  문제가 있는 모델 출력에는 검토 플래그를 붙입니다.
- Windows 작업 스케줄러의 옛 Fallout2-RPU-Overnight-Review 예약은
  번역 품질 검증으로 **사용 중지되어 있습니다**.
  새 큐는 명시적으로 실행할 때만 동작합니다.
- 이 도구는 번역 초안 생성·비교 시스템이지
  GPT가 실제 모든 분기를 읽어 판단한 인간 수준의 완전한 전수 검수가 아닙니다.
