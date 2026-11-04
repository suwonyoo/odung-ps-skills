# 공개 워크플로 참고 검토

2026-11-04에 Matt Pocock의 공개 저장소를 읽고 원리를 선별했다. 확인한 commit은 `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`, 라이선스는 MIT다. 현재 README는 Claude뿐 아니라 Codex 설치도 안내한다. 이 프로젝트에는 upstream 스킬 패키지를 설치하지 않고 시험 시간에 맞는 자체 지침과 코드로 적용했다.

| 참고한 파일 | 취한 원리 | 이 준비 도구에서의 변경 |
|---|---|---|
| productivity/grilling/SKILL.md | 선행 판단이 끝난 질문부터 묻기 | 현재 답할 수 있는 질문 최대 3개, blocking/독립 작업 구분. 모든 설계 가지를 끝까지 토론하는 종료 조건은 채택하지 않음 |
| engineering/domain-modeling/SKILL.md | 용어의 의미와 중요한 선택 이유를 작업 중 기록 | GLOSSARY.md + 짧은 decisions.md. 매번 긴 ADR을 만들지 않음 |
| engineering/to-spec/SKILL.md | 대화·근거를 구현 가능한 명세로 묶기 | 실제 source/제약/검사/경로를 연결한 intake.json. 긴 사용자 이야기나 외부 이슈 발행은 생략 |
| engineering/to-tickets/SKILL.md | 처음부터 끝까지 연결되는 작은 기능과 작업 의존 | 최소 실행 경로 먼저, 계약 후 코어/연결 병렬화. 작업을 과도하게 쪼개지 않음 |
| engineering/diagnosing-bugs/SKILL.md | 실패를 감지하는 실행으로 가설 확인 | 작은 재현→원인→수정→관련 검사. 사소한 오류에 긴 다단계 의식을 강제하지 않음 |

참고 파일은 위 commit의 `skills/` 아래에 있다: https://github.com/mattpocock/skills/tree/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills

그대로 가져오지 않은 것: 전체 질문 트리 소진, 무조건 매 결정 사용자 승인, 모든 작업 TDD 강제, 외부 이슈 트래커 의존, 여러 UI 대안을 병렬 제작, 자동 최신판 업데이트. 제한시간에는 과도한 질문·문서·설치 의존도 자체가 실패 원인이 된다.

Superpowers는 기존 버전에서 명확화·작은 작업·원인 중심 디버깅·완료 전 검증의 참고였다. upstream 패키지나 hooks를 설치한 적은 없으며 이 레포가 이를 전부 실행한다고 설명하지 않는다. 시험 시작 직전 전체 워크플로 패키지를 추가하면 중복 지침과 승인 루프가 생길 수 있으므로 이 준비본을 연습해 고정한다.

원문 스킬 문장/코드의 통째 복제는 없다. 라이선스/버전과 참고 범위는 SOURCES.md에 남겼다. 향후 실제로 복사하면 해당 라이선스 고지도 함께 보존해야 한다.
