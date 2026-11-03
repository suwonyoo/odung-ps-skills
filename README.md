# odung-ps-skills

시간이 제한된 코딩 과제에서 요구사항, 구현, 검증, 인수인계를 연결하는 준비 도구다. 실제 시험 문제나 완성된 서비스는 포함하지 않는다.

- 시작부터 마무리까지 연결하는 일곱 가지 Codex 스킬
- OR-Tools / Timefold / 단순 baseline 선택, 모델 명세와 공유 계약
- 단계·세션별 작업·파일 소유·갱신 시각을 보여주는 Markdown 상태판
- 명령의 경과·설정 제한·실제 종료·로그를 남기는 실행 타이머
- 수동 DM 답변, 선택 이유, 구조, 검증, 한계를 작업 중 자연스럽게 기록
- 기존 파일을 보존하는 설치 미리보기와 충돌 검사
- 실제 명령·종료 코드·로그, 소스 변경에 따른 검증 만료 표시
- 사용자 직접 확인의 별도 기록
- 실제 제출 경로와 누락 파일 점검
- 하네스는 Python 3.10+ 표준 라이브러리만 사용. 모델 API, 키, 텔레메트리 없음
- 선택형 솔버 예제: Python OR-Tools 9.15.6755 / JDK 21+ Timefold CE 2.7.1

## 시작

```bash
python3 scripts/install.py --target /path/to/task
python3 scripts/install.py --target /path/to/task --apply
cd /path/to/task
python3 .harness/flow.py start --minutes 180
```

대상 폴더의 Codex에 아래처럼 한 번 요청한다.

> .agents/skills/hackathon-start/SKILL.md를 읽고 제공 자료로 시작해 줘. 중요한 판단은 용어의 쉬운 뜻·선택지·비용·추천 근거·확인 방법으로 물어봐 줘. 내 답변과 실제 작업 근거를 파일에 남기고, 현재 단계와 세션별 작업을 계속 관리해 줘. 담당자 DM은 내가 직접 보내고 답변을 전달할게.

이후 에이전트가 사건에 맞춰 지침과 명령을 사용한다. 사용자가 매번 스킬 이름을 부를 필요는 없다. 네이티브 자동 hook이나 세션 자동 생성 기능은 아니다. 다른 터미널에서 `python3 .harness/flow.py status --watch`를 실행하면 상태를 볼 수 있다.

기존 v1 설치와 내용이 충돌하면 설치기는 중단한다. 기존 작업을 덮어쓰지 말고 새 연습 폴더에서 v2를 확인하거나 변경 파일을 검토해 수동 이관한다.

## 솔버 선택과 실행

업무 규칙이 복잡하다고 무조건 Timefold를 선택하지 않는다. 문제 표현, 필요한 증명, 제공 언어, 설치 가능성, 작은 실제 실행 결과로 판단한다. 두 솔버 모두 정확한 조건 정의와 독립 검증이 필요하다.

- [선택 기준](references/solver-selection.md)
- [같은 합성 문제의 OR-Tools·Timefold 예제](examples/shift-assignment/README.md)
- [자동 흐름·판단 기록·시간·병렬 작업](docs/WORKFLOW_KO.md)
- [설치·검증 설정의 정확한 형식](docs/START_HERE_KO.md)

솔버의 시간 제한은 해 탐색 예산이다. 전체 프로세스 제한과 실측 시간은 따로 기록한다. Timefold의 후보와 CP-SAT의 UNKNOWN을 최적해나 불가능 증명으로 바꾸어 말하지 않는다. `feasible`, `optimality_proven`, `infeasibility_proven`, 독립 검증을 구분한다.

## 구성

| 구성 | 역할 |
|---|---|
| hackathon-start | 시작·재개, 사건별 다음 지침, 전체 상태 |
| hackathon-intake | 자료·입출력·요구사항·수용 기준 |
| stakeholder-bridge | 사용자의 수동 DM과 조건 변경 연결 |
| solver-modeling | 솔버 선택·모델 명세·실측 prototype |
| hackathon-build | 계약에 맞춘 구현·통합·집중 디버깅 |
| hackathon-verify | 실제 검사·독립 검증·오래된 근거 식별 |
| hackathon-finish | 실제 산출물·문서·한계·수동 제출 준비 |

`harness.py`는 검증 증거, `workflow.py`는 진행·세션·시간을 관리한다. 설치 후 실제 기록은 별도 과제 폴더의 `.harness/work/`에만 생긴다. 구현 설명과 선택 근거를 작성하는 일반 개발 기록이며, 시험 중 AI 금지 평가의 답안을 생성하는 기능은 아니다.

## 공개본과 작업 공간

이 저장소는 일반적인 준비 자료만 담는다. 시험에 사용할 경우 먼저 공개 GitHub 저장소로 배포하고 실제 안내가 정한 기간 동안 공개를 유지해야 한다. 로컬 파일이나 개인 스킬 등록만으로 공개 자료 요건을 충족하지 않는다.

실제 과제는 별도 제공 작업 공간에서 수행한다. 작업 자료를 이 저장소에 복사하거나 원격으로 보내지 않는다. 실제 규정과 과제 안내가 이 도구보다 우선한다. 이 도구는 대회의 공식 도구가 아니다.

## 확인

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_manifest.py
```

제공 시험 환경의 Codex 버전·모델·네이티브 스킬 탐색·동시 실행 한도는 그 환경에서 확인해야 한다. 런타임은 샌드박스나 위변조 방지 장치가 아니다. 실행하도록 설정한 명령 자체의 동작도 검토한다. Superpowers의 일부 절차를 참고했으며 upstream 패키지를 설치한 것은 아니다.

연습은 [합성 과제](practice/BRIEF.md), 시작 요청문은 [prompts/start.md](prompts/start.md), 검증 범위는 [docs/VALIDATION.md](docs/VALIDATION.md), 시험 전 공개 배포는 [배포 안내](docs/PUBLISH_KO.md)를 참고한다.
