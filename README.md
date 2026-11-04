# odung-ps-skills

문제 자료에서 목표와 필수 결과물을 찾아 분석 → 모델링 → 구현 → 통합 → 검증 → 인계로 진행하는 Codex 도구. 일곱 지침, 상태·시간·질문·실행 근거를 관리하는 Python 하네스, 선택형 OR-Tools/Timefold 예제를 포함한다.

## 시작

별도 과제 폴더에 설치한다. Python 3.10+와 Codex CLI가 필요하며 기존 파일은 덮어쓰지 않는다. 새 과제 폴더가 필요하면 다음처럼 만든다. 이미 제공된 작업 폴더가 있으면 그 경로를 사용한다.

```bash
mkdir -p ../task-workspace
python3 scripts/install.py --target ../task-workspace --apply
cd ../task-workspace
codex
```

이미 설치된 과제 폴더는 다시 설치하지 않고 그 폴더에서 `codex`를 연다.

Codex가 읽을 수 있는 곳에 실제 문제 자료를 두고 위치만 알려준다.

> 문제 자료는 inputs/에 있어.

목표·필수 결과물·입력 역할·제약·시간은 파일에서 먼저 찾는다. 별도 시작 프롬프트나 설정값은 필요 없다. 자료에 시간 정보가 없으면 임시 180분 예산을 알리고 시작하며, HR 유무는 중요한 질문이 필요할 때만 확인한다. 원하는 결과나 시간·DM 유무를 이미 알고 있으면 선택적으로 덧붙여도 된다. 단순 참고자료 첨부나 저장소 열기만으로 작업을 시작하지는 않는다.

자동 진입이 안 되면 `.agents/skills/task-start/SKILL.md를 읽고 시작해 줘`를 한 번 덧붙인다. 기존 AGENTS.md와 실제 과제 규칙이 우선이다. 저장소 연결 자체가 코드를 실행하지는 않는다.

- 재개: “기존 상태와 시계를 유지하고 계속하자.”
- DM 없음: “담당자에게 물어볼 수 없어. 이번 작업은 DM 없이 진행해.” 한 번 설정하면 유지된다. 필수 조건이나 검증까지 생략되지는 않는다.
- 상태 보기: 과제 폴더의 별도 터미널에서 `python3 .harness/flow.py status --watch`. Ctrl+C는 이 상태 보기만 종료한다.
- 시간 계획: 자료를 훑은 뒤 남은 작업의 추정 범위·의존관계·예비 시간을 기록하고, 실측·새 조건·지연에 따라 재산정한다. 원래 마감은 유지한다.
- 수동 DM: 질문은 `.harness/work/hr-outbox.md`, 받은 원문은 `hr-inbox.md`에 쌓는다. 사용자가 터미널 밖에서 전달하며, 답변 대기 중 독립 작업은 계속한다. 새 원문을 기록해도 명세·검사 반영 전에는 관련 작업을 재개하지 않는다.

## 실행에 필요한 참고

- [단계·질문·시간·병렬 작업 명령](docs/WORKFLOW_KO.md)
- [요구사항과 검사 설정 형식](docs/START_HERE_KO.md)
- [솔버 선택 기준](.agents/skills/solver-modeling/references/solver-selection.md)
- [작은 직원 배정 예제 실행](examples/shift-assignment/README.md)
- [출처·버전·라이선스](SOURCES.md)

실제 앱과 문제별 모델은 과제에 맞춰 구현한다. 하네스는 새 AI 세션이나 외부 DM을 자동 실행하지 않는다. 실제 자료·작업 기록은 이 공개 저장소에 올리지 않는다. 평가에 쓰면 실제 AI 허용 규칙과 공개 유지 기간을 따른다.

개발 검사: `python3 -m unittest discover -s tests -v`. 설치 파일 변경 후 `python3 scripts/build_manifest.py`. 진행 중인 과제는 업그레이드하지 않고 새 과제 폴더에 설치한다.
