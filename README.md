# odung-ps-skills

문제 자료와 원하는 결과를 받아 분석 → 모델링 → 구현 → 통합 → 검증 → 인계로 진행하는 Codex 도구. 일곱 지침, 상태·시간·질문·실행 근거를 관리하는 Python 하네스, 선택형 OR-Tools/Timefold 예제를 포함한다.

## 시작

별도 과제 폴더에 설치한다. Python 3.10+가 필요하며 기존 파일은 덮어쓰지 않는다.

```bash
python3 scripts/install.py --target /path/to/task --apply
cd /path/to/task
codex
```

Codex에 말한다. 경로·결과·시간·DM 유무만 실제 상황으로 바꾼다.

> 문제는 inputs/brief.pdf, 데이터는 data/야. 결과는 배정표와 조회 화면이야. 180분이고 담당자 DM은 없어. 시작하자. 중요한 선택은 쉽게 설명하고 현재 단계와 내가 할 일만 짧게 알려줘.

자동 진입이 안 되면 `.agents/skills/task-start/SKILL.md를 읽고 시작해 줘`를 한 번 덧붙인다. 기존 AGENTS.md와 실제 과제 규칙이 우선이다. 저장소 연결 자체가 코드를 실행하지는 않는다.

- 재개: “기존 상태와 시계를 유지하고 계속하자.”
- DM 없음: “담당자에게 물어볼 수 없어. 이번 작업은 DM 없이 진행해.” 한 번 설정하면 유지된다. 필수 조건이나 검증까지 생략되지는 않는다.
- 상태 보기: 과제 폴더의 별도 터미널에서 `python3 .harness/flow.py status --watch`. Ctrl+C는 이 상태 보기만 종료한다.

## 실행에 필요한 참고

- [단계·질문·시간·병렬 작업 명령](docs/WORKFLOW_KO.md)
- [요구사항과 검사 설정 형식](docs/START_HERE_KO.md)
- [솔버 선택 기준](.agents/skills/solver-modeling/references/solver-selection.md)
- [작은 직원 배정 예제 실행](examples/shift-assignment/README.md)
- [출처·버전·라이선스](SOURCES.md)

실제 앱과 문제별 모델은 과제에 맞춰 구현한다. 하네스는 새 AI 세션이나 외부 DM을 자동 실행하지 않는다. 실제 자료·작업 기록은 이 공개 저장소에 올리지 않는다. 평가에 쓰면 실제 AI 허용 규칙과 공개 유지 기간을 따른다.

개발 검사: `python3 -m unittest discover -s tests -v`. 설치 파일 변경 후 `python3 scripts/build_manifest.py`. 진행 중인 과제는 업그레이드하지 않고 새 과제 폴더에 설치한다.
