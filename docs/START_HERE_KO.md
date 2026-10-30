# Codex에서 시작하기

이 도구는 범용 준비용이다. 실제 문제나 완성된 제출 서비스는 포함하지 않는다. Python 3.10 이상만 필요하며 외부 패키지, API 키, 유료 서비스가 필요 없다.

## 준비 환경에서 설치

공개 준비 저장소와 실제 과제 작업 폴더를 분리한다. 대상 폴더는 이미 존재해야 한다.

```bash
python3 /path/to/codex-hackathon-kit/scripts/install.py --target /path/to/task
python3 /path/to/codex-hackathon-kit/scripts/install.py --target /path/to/task --apply
cd /path/to/task
python3 .harness/runner.py doctor
python3 .harness/runner.py init
```

첫 명령은 설치 계획만 출력한다. `--apply`는 새 파일만 만든다. 같은 내용이면 유지하고, 다른 내용이 있으면 전체 설치를 중단한다. 기존 README, AGENTS.md, 소스코드, 패키지, 인증 파일은 수정하지 않는다. 해시 검사는 배포 파일의 변경을 감지하는 기능이며 서명 검증은 아니다.

이후 **대상 과제 폴더에서** Codex를 실행한다. 제공 환경에서는 `/status`, `/model`, 스킬 목록을 확인한다. 다음 요청으로 시작한다.

> $hackathon-intake 를 사용해 README와 실제 과제 안내를 읽고 필수 결과물·성공 기준·미확인 사항을 정리해줘. .harness/GUIDE.md도 읽어줘. 기존 프로젝트를 보존하고 .harness/work/task.json을 실제 조건으로 채워줘.

설치 버전에서 스킬이 나타나지 않으면 해당 SKILL.md의 경로를 명시해 읽게 한다. 플랫폼 설정이나 인증을 바꾸지 않는다. 명시적 파일 읽기는 네이티브 스킬 로딩과 다르므로 이를 자동 인식 성공으로 기록하지 않는다.

## task.json의 정확한 형식

다음 예시는 **합성 연습 과제용**이다. 실제 과제의 파일과 조건으로 교체한다. 빈 초기 양식은 통과하지 않는다.

```json
{
  "schema_version": 1,
  "title": "재고 부족 확인 연습",
  "requirements": [
    {"id": "R1", "description": "현재 재고가 기준보다 작은 품목을 표시", "acceptance": "기준 5, 재고 4·5·6에서 4인 품목만 포함", "required": true},
    {"id": "R2", "description": "잘못된 숫자 입력을 차단", "acceptance": "빈 값과 음수를 오류로 처리", "required": true}
  ],
  "deliverables": [
    {"path": "app.py", "purpose": "실행 코드", "required": true},
    {"path": "README.md", "purpose": "실행 방법과 한계", "required": true}
  ],
  "checks": [
    {"id": "logic", "description": "정상·경계·오류 입력 검사", "argv": ["python3", "-m", "unittest", "discover", "-s", "tests"], "cwd": ".", "timeout_seconds": 60, "requirements": ["R1", "R2"], "expected": "명세에서 계산한 기대값에 대한 assertion이 모두 통과"}
  ],
  "manual_checks": [
    {"id": "ui", "description": "내장 Browser에서 직접 확인", "requirements": ["R1"], "expected": "재고 4인 품목 하나와 건수 1이 화면에 표시"}
  ]
}
```

키 이름을 정확히 사용한다. 체크 ID는 영문자로 시작하고 영문·숫자·하이픈·밑줄만 쓴다. `argv`는 셸 문자열이 아니라 인자 배열이다. `cwd`와 제출 경로는 대상 작업 폴더의 상대 경로로 쓰며 상위 경로와 심볼릭 링크는 지원하지 않는다. 검사는 1~600초로 제한한다.

각 필수 요구사항에는 검사가 있어야 한다. 해당 요구에 연결한 모든 검사가 현재 통과해야 충족으로 표시한다. 선택 요구만 있는 과제도 구성할 수 있지만, 필수 결과물을 임의로 선택 항목으로 낮추면 안 된다. 검사는 실제 동작을 assert해야 한다. `true`나 성공 문구 출력은 기능 검증이 아니다.

## 구현·검증·마무리

```bash
python3 .harness/runner.py check
python3 .harness/runner.py check logic
python3 .harness/runner.py audit
python3 .harness/runner.py audit --json
python3 .harness/runner.py report
```

코딩은 `$hackathon-build`, 검증은 `$hackathon-verify`, 제출 전 확인은 `$hackathon-finish`로 요청한다. 도구가 모델을 따로 호출하거나 새 Codex 세션을 자동 실행하지는 않는다.

`check`는 명령을 실제 실행하고 `.harness/work/evidence/`에 원본 로그와 메타데이터를 저장한다. 실패 코드를 유지한다. 시간 초과는 124, 로그 용량 제한은 125, 실행 실패는 127을 반환한다. 제한이나 중단 시 해당 검사에서 만든 프로세스 그룹만 종료한다. 일반 플랫폼 프로세스는 조회하거나 종료하지 않는다.

`audit`는 검증 결과와 필수 파일 존재를 확인한다. 0은 설정한 로컬 검사 충족, 1은 미검증·실패·누락, 2는 잘못된 설정이다. 공식 제출 성공이나 모든 기능의 정확성을 의미하지 않는다. 필수 문서의 내용 검토도 별도로 필요하다.

코드나 task.json을 바꾸면 기존 결과를 `stale`로 표시한다. 검사 중 소스가 바뀐 경우도 통과 근거로 사용하지 않는다. `.harness`, 의존성·캐시·빌드 산출물은 해시 범위에서 제외한다. 핵심 소스는 제외 폴더에 넣지 않는다. 저장소 전체를 자주 바꾸면 검사도 다시 필요하므로, 최종 검증 전에 문서와 코드를 정리한다.

## 직접 확인 기록

UI는 본인이 제공 Browser에서 조작한다. 사용자가 실제로 확인했다고 말한 다음에만 아래처럼 기록한다.

```bash
python3 .harness/runner.py manual --id ui --status pass --observed '재고 4인 품목 하나와 건수 1을 화면에서 확인함' --user-confirmed
```

이는 `user-reported` 기록이다. 본인 인증이나 독립적인 증명 기능이 아니다. 사용자 확인이 없으면 미검증으로 둔다. AI가 추측해 이 명령을 실행하지 않도록 스킬에 명시했다.

## 제출과 AI 사용 종료

내부 기록을 실제 요구된 파일에 반영한다. 제출 폴더 밖의 worktree에만 변경이 남아 있지 않은지 확인한다. 제출 버튼과 최종 완료 확인은 사용자가 직접 한다.

```bash
python3 .harness/runner.py close
```

`close`는 이후 검사·수동 기록·보고서 작성을 막는 로컬 상태 변경이다. 공식 제출이나 타이머 제어가 아니며 다른 Codex 세션을 종료하지 않는다. AI 금지 단계에서는 모든 AI 도움을 중단한다. 다음 사전 연습은 새 폴더에서 시작한다.

## 병렬 작업

주 Codex는 코드를 작성하고, 서버는 별도 터미널에서 유지한다. 두 번째 AI가 허용되고 지원되면 읽기 전용 검토를 맡긴다. 잠금 파일·공통 타입·루트 설정은 하나의 세션만 수정한다. 작업 디렉터리를 나누는 git worktree는 CPU·포트·외부 서비스를 분리하지 않는다. 기능 지원이 확인되지 않으면 단일 세션으로 진행한다.

## 공개 사용 전

공개 레포에는 이 준비 도구만 넣는다. 실제 시험 문제·파일·작업 기록은 넣지 않는다. 시험에서 쓰려면 시험 전 공개한 URL에서 가져오고, 요구된 기간 동안 공개를 유지한다. 개인 스킬 등록, 로컬 Git bundle, 비공개 저장소는 공개 저장소 요건을 대신하지 않는다. 차단을 다른 경로로 우회하지 않는다.
