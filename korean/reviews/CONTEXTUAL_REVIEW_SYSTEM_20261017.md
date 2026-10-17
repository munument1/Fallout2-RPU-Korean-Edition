# Fallout 2 RPU — 문맥 기반 번역 검수 시스템 (2026-10-17)

## 구현 범위

- 기존 8개 주요 NPC에 한해 성격·기본 말투·상황별 예외를 따로 기록.
  다른 NPC의 말투를 임의로 적용하지 않음.
- 동일 Git HEAD의 영어 MSG와 SSL로 각 ID의 역할을 확인:
  NPC Reply, 플레이어 Option, Reply(mstr(...)) 복합 대사, 일반 스크립트 출력.
- SSL의 실제 procedure/Node, 해당 호출 원문 위치, 인접 MSG ID의 영어 텍스트를 전달.
  인접 ID는 실제 대화 흐름이라고 가정하지 않음.
- 용어집의 Vertibird와 복수형 vertibirds 모두 버티버드 표기 기준으로 탐지.
  응답의 용어집 위반, CP949 출력 가능 여부, 서식·치환식·마크업 위험을 자동 표기.
- Hy-MT2-7B Q8 1차 번역과 TranslateGemma 12B 2차 번역을 서로 독립적으로 생성.
  상태 저장으로 ID별 재개 가능. 번역 원본은 절대로 수정하지 않음.

## 실제 대사 시범

리처드슨 qhprzrch.msg의 ID 250/266/276을 먼저 실행해 두 모델의 번역 6개를 생성.
SSL에서 250=리처드슨 Reply(Node045), 266/276=플레이어 선택지(Node050/055)를 정확히 구분.
이어서 과거 수동 검수 확정 오역 12건에 대해 NPC/영문/SSL/용어집을 제공하는
**24개 모델 번역**을 생성하고 정답 교정본과 나란히 저장.

- [CONTEXTUAL_MODELS_12_20261017.csv](CONTEXTUAL_MODELS_12_20261017.csv):
  실제 영어, 이전 오역, 최종 수동 검수본, 역할, SSL Node, 두 모델의 번역.
- 리처드슨 ID 250은 두 모델 모두 버티버드 용어를 유지했으나,
  TranslateGemma는 반말을 존댓말로 변환.
- 리처드슨 ID 276은 Hy-MT2가 상대를 직접 처리한다는 위협을 복원.
  TranslateGemma는 '일에서 빼버린다'는 모호함이 남음.
- 술릭 ID 731은 이전의 pasture pies 오역과 달리 두 모델 모두
  소똥에 모이는 파리의 비유를 해석.
- 리처드슨 ID 218의 Red menace는 두 모델 모두 공산주의 관련 표현으로 개선.
- 반면 술릭 711은 독특한 '우리랑 나'라는 화자 표현을 흔하게 생략했고,
  고리스 144(플레이어 선택지)는 Hy-MT2가 상대를 반말로 대하는 등
  상황별 한국어 말투의 정확성은 완전히 해결되지 않음.

이 시험은 특정 과거 오역 12건에 대한 **정성적 회귀 시험**이며
5만 7천여 개 RPU 대사 전체의 정량적 정확도를 나타내지 않음.

## 실행 방법

저장소 루트에서:

    python korean/contextual_review_queue.py --file ocgoris --max-items 12
    python korean/contextual_review_queue.py --file qhprzrch --ids 250,266,276 --max-items 3
    python korean/contextual_review_queue.py --status

결과는 기본적으로 Git에 올라가지 않는 korean-contextual-review 폴더의
comparisons.jsonl과 state.json에만 저장.
원본 MSG, manifest, ZIP, 게임 엔진, 사용자 정식 배포본에 영향 없음.

## 검수 품질·운영 원칙

기계적 형식 검증만으로 의미상 오역이 없다고 주장하지 않음.
특히 이미 수동으로 교정한 대사를 Hy-MT2/TranslateGemma가
동시에 잘못 해석할 수 있으므로 자동 커밋·자동 릴리스 금지.

기존 Windows 새벽 3시 자동 검수 작업은 Disabled를 유지.
이 새 시스템은 **재개 가능한 후보 비교용 도구**이며, 별도로 품질 기준과
컴퓨터 자원 한도를 정하기 전까지 매일 장시간 무인 실행하지 않음.
