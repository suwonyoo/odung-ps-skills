# Codex Hackathon Kit

시간이 제한된 코딩 과제에서 요구사항, 구현, 검증, 인수인계를 연결하는 준비 도구다. 실제 시험 문제나 완성된 서비스는 포함하지 않는다.

- 네 가지 Codex 스킬: `hackathon-intake`, `hackathon-build`, `hackathon-verify`, `hackathon-finish`
- 기존 파일을 보존하는 설치 미리보기와 충돌 검사
- 실제 명령·종료 코드·로그, 소스 변경에 따른 검증 만료 표시
- 사용자 직접 확인의 별도 기록
- 실제 제출 경로와 누락 파일 점검
- Python 3.10+ 표준 라이브러리만 사용. 모델 API, 키, 네트워크, 텔레메트리, GUI 자동화 없음

## 시작

```bash
python3 scripts/install.py --target /path/to/task
python3 scripts/install.py --target /path/to/task --apply
cd /path/to/task
python3 .harness/runner.py init
```

대상 폴더의 Codex에서 `$hackathon-intake`로 시작한다. 실제 과제에 맞춰 `.harness/work/task.json`을 작성한 뒤 검사를 실행한다. 전체 사용법과 JSON 예시는 [시작 안내](docs/START_HERE_KO.md)에 있다.

## 공개본과 작업 공간

이 저장소는 일반적인 준비 자료만 담는다. 시험에 사용할 경우 먼저 공개 GitHub 저장소로 배포하고 실제 안내가 정한 기간 동안 공개를 유지해야 한다. 로컬 파일이나 개인 스킬 등록만으로 공개 자료 요건을 충족하지 않는다.

실제 과제는 별도 제공 작업 공간에서 수행한다. 작업 자료를 이 저장소에 복사하거나 원격으로 보내지 않는다. 실제 규정과 과제 안내가 이 도구보다 우선한다. 이 도구는 대회의 공식 도구가 아니다.

## 확인

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_manifest.py
```

구현한 것은 스킬과 로컬 검사 도구다. 제공 시험 환경의 Codex 버전·모델·네이티브 스킬 탐색·동시 실행 한도는 그 환경에서 확인해야 한다. 런타임은 샌드박스나 위변조 방지 장치가 아니다. 실행하도록 설정한 명령 자체의 동작도 검토한다.

연습은 [합성 과제](practice/BRIEF.md), 시작 요청문은 [prompts/start.md](prompts/start.md), 검증 범위는 [docs/VALIDATION.md](docs/VALIDATION.md), 시험 전 공개 배포는 [배포 안내](docs/PUBLISH_KO.md)를 참고한다.
