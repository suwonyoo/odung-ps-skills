# 흐름과 상태판

설치 후 Codex에 “제공 자료로 시작해 줘. 전체 진행과 판단 기록을 계속 관리해 줘.”라고 요청한다. `hackathon-start`가 시작·재개를 담당한다. 자동 선택이 없는 CLI에서는 첫 요청에 `.agents/skills/hackathon-start/SKILL.md`를 읽으라고 한 번 덧붙인다.

이 도구가 Codex 세션을 자동 생성하거나 모델을 호출하지는 않는다. 지침을 읽은 에이전트가 사건에 맞춰 다음 지침을 읽고 CLI를 호출한다. 상태·로그·명령 시간은 코드가 기록한다. 사용자는 매 단계마다 스킬 이름을 입력할 필요가 없다.

## 실행

```bash
python3 .harness/flow.py start --minutes 180
python3 .harness/flow.py status --watch
```

다른 터미널의 상태판은 5초마다 갱신한다. `Ctrl+C`로 상태판만 종료한다. 수동 세션은 마지막 갱신이 120초를 넘으면 stale로 표시한다. 에이전트의 실제 사고 과정을 감시하지 않으며 갱신되지 않은 세션이 죽었다고 단정하지 않는다.

```bash
python3 .harness/flow.py event inputs-reviewed --note '실제 자료와 미확인 조건을 분리함'
python3 .harness/flow.py select ortools-cp-sat --reason '실제 선택 이유' --alternative 'Timefold의 비용과 이번 환경의 차이' --evidence '실제로 실행한 명령·결과 또는 미확인'
python3 .harness/flow.py worker core --status running --task '제약 모델' --files src/core --next '작은 반례 검증'
python3 .harness/flow.py worker integration --status running --task '저장·조회' --files src/api src/ui --next '공유 계약으로 연결'
```

`contract.json`의 필수 필드와 실제 requirement ID를 채운 후 `event contract-ready`로 넘어간다. 구조 검사 통과가 명세의 의미까지 검증하지는 않는다. 합의된 계약 revision을 각 세션에 전달한다.

## 자연스럽게 남기는 파일

| 사건 | 기록 |
|---|---|
| 중요한 선택 | decisions.md: 문제, 용어의 쉬운 뜻, 대안, 선택, 이유, 감수한 비용, 다음 검증 |
| 사용자의 판단 | 원문 답변과 판단 주체를 함께 기록; 응답 전에는 proposed |
| 수동 DM 답변 | questions.md: 전달된 원문과 AI 해석을 구분; 요구 ID와 연결 |
| 모델 구현 | model-spec.md: 변수·규칙·목표·제한·보장 범위 |
| 모듈·상태 변경 | architecture.md: 실제 경로·책임·상태·실패 동작 |
| AI 제안과 검증 | AI_collaboration.md: 수용·수정·폐기와 실제 명령·근거 |
| 확인하지 못한 가정 | limits.md: 영향·반례·다음 검증 |

중요한 질문은 이 순서로 짧게 묻는다: **결정할 것 → 전문 용어와 쉬운 뜻 → 선택지 2개·비용 → 추천 근거 → 결과 확인 방법**. 되돌리기 쉬운 내부 구현은 합리적인 기본값으로 진행하고 기록한다. 목표 우선순위, hard 규칙 완화, 외부 전달·비용 등 사용자 판단이 필요한 사항은 답을 기다린다.

## 시간과 실행

```bash
python3 .harness/flow.py run --session solver --engine ortools-cp-sat --label '작은 배정 모델' --limit 30 --input input.json -- python3 solve.py input.json
python3 .harness/flow.py history
```

명령마다 실제 argv·시작·종료·경과·외부 제한·원래 종료 코드·로그 해시를 저장한다. 2초마다 실행 세션을 갱신한다. 출력은 로그 파일에 있고 상태판에 그 경로가 표시된다. 외부 제한은 솔버 제한보다 여유 있게 둔다. Linux/macOS에서는 제한 도달 시 프로세스 그룹을 종료한다. Windows에서는 자식 프로세스 전체 종료를 보장하지 않으므로 시험 전에 별도 확인한다.

솔버 자체는 입력 읽기, 모델 구성, 첫 feasible 해, 마지막 개선, solve, 독립 검증 시간을 가능한 범위에서 결과에 남긴다. 미관측 값은 null이다. 시간 제한은 해를 찾는다는 보장이 아니며, 프로세스의 exit 0은 계획의 유효성 증거가 아니다.

history는 명령·입력·소스·제한·환경 fingerprint가 같은 성공 실행의 실측 최소·중앙·최대를 보여준다. 실패·timeout·입력 변경을 성공 표본에 섞지 않는다. 표본은 미래 ETA나 통계적 신뢰구간이 아니다. 실제 데이터 규모가 바뀌면 다시 측정한다.

## 병렬 작업

코어 A와 연결 B로 시작한다. A는 모델과 검증, B는 API·저장·최소 화면을 맡는다. 공유 타입·의존성·계약은 한 명만 수정한다. 폴더를 나중에 덮어쓰지 않고 작은 단위로 통합한다. worker 명령은 겹치는 소유 경로를 거부하지만 파일 쓰기 자체를 막는 샌드박스는 아니다. Git worktree 사용 시 상태판은 지정한 통합 작업 공간 하나에서 관리한다.

여러 Codex 세션과 솔버 내부 병렬성은 별개다. CPU가 4개인데 솔버 2개가 각각 8 workers로 실행되지 않게 예산을 잡는다. Timefold CE에서 사용할 수 있는 병렬 기능은 선택한 버전의 기능 범위를 확인한다.

`event candidate-ready` → 통합, `event integrated` → 검증, `event claim-complete` → 근거 확인이다. `event verified`는 현재 설정된 필수 검사와 산출물이 충족되지 않으면 거부한다. 공식 제출은 사용자와 실제 안내에 따른다. 작업 종료 후 `runner.py close`는 추가 작업 명령을 막는다.

Superpowers의 문제 명확화·작은 작업·원인 기반 디버깅·완료 전 검증 흐름을 참고했다. upstream 패키지를 설치하거나 자동 hook을 보장하는 구성은 아니다. 모든 이벤트의 순서를 강제하는 완전한 워크플로 엔진도 아니며, 중요한 전환의 검사와 진행 표시를 제공한다.
