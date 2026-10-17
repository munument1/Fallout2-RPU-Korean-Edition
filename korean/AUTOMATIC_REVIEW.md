# Fallout 2 RPU - 클릭 없는 일괄 검수

이 도구는 한글 대사 파일 1,032개를 로컬 Ollama 모델로 순회하여 **교정 후보를 생성합니다**.
결과는 korean-auto-review 폴더에 저장되며 state.json으로 완료한 묶음을 기억합니다.
재시작하거나 중단해도 동일한 묶음에 불필요하게 재요청하지 않습니다.

## 자동화 범위

- 모든 한글 대사 MSG를 읽고, 대응 영어 MSG와 같은 버전 SSL의 Reply/Option을 제공
- 기존 정적 감사에서 혼용이 의심된 251개 파일을 먼저 처리한 후 나머지도 순회
- 기존에 설치된 qwen3:14b 사용. 별도 유료 외부 AI API 키가 필요 없음
- 결과는 PROGRESS.md / review-proposals.jsonl / state.json / structural_flags.jsonl
- 재실행 시 체크포인트를 읽어서 다음 미검수 묶음부터 이어서 처리

## 품질 한계 (중요)

AI가 생성한 결과는 **확정 교정본이 아니라 후보**입니다.
14B급 모델은 틀린 어휘와 문체를 높은 확신도로 추천할 수도 있습니다.
실제 시험에서 게임의 고유한 정식 명칭인 '미합중국'을 '미국'으로
고치라고 0.95 확신도를 붙이는 잘못된 추천이 확인됐습니다.
때문에 CP949 MSG, 매니페스트, 정식 릴리스는 **자동으로 수정하지 않습니다**.
안전한 변경은 제안을 영어 원문·SSL과 독립적으로 검증한 뒤 적용해야 합니다.

## 실행

저장소 루트 PowerShell에서:

    python korean/auto_review_queue.py --status
    powershell -NoProfile -ExecutionPolicy Bypass -File korean/run_local_batch.ps1

Windows 작업 스케줄러 작업명: Fallout2-RPU-Overnight-Review
기본 매일 오전 3시, 1회 최대 115분, 중복 실행 금지.
PC가 꺼져 있으면 실행되지 않고 Ollama 미설치/미작동 시 진행되지 않습니다.

기존 korean/audit_dialogue_register.py --script-limit 0은
규칙 기반으로 전체 MSG에 대해 말투 후보만 탐지하며
실제 문맥 검수나 자동 오역 수정이 아님을 구별해 두어야 합니다.
