# 시험 전 공개 저장소로 배포

이 절차는 준비용 프로젝트를 시험 전에 공개할 때만 사용한다. 실제 과제 작업 공간에서 실행하지 않는다.

1. 공개할 파일이 일반 도구와 합성 연습 자료뿐인지 확인한다. 실제 시험 문제, 배포된 안내서 원본, 개인정보, 키, 작업 결과, 실제 평가 기록을 넣지 않는다.
2. `python3 -m unittest discover -s tests -v`로 코드를 검증한다.
3. `python3 scripts/build_manifest.py`로 설치 파일 해시를 갱신한다.
4. GitHub에서 `odung-ps-skills` 같은 이름의 **Public** 저장소를 만든다. 기존 저장소를 덮어쓰지 않는다.
5. 준비 프로젝트만 업로드하고, 검증한 커밋에 `v3.1.0` 같은 태그를 남긴다. 실제 소유자와 저장소 URL을 기록한다.
6. 로그아웃 상태에서 저장소와 태그가 열리는지, 인증 없이 clone할 수 있는지 확인한다.
7. 규정이 요구하는 결과 통지 시점까지 공개 상태를 유지한다. 이 기간이 끝나도 실제 시험 자료의 공개가 자동 허용되는 것은 아니다.

GitHub CLI를 사용한다면, 연결된 계정과 새 저장소 이름을 확인한 뒤 준비 저장소 안에서 다음과 같이 만들 수 있다. GitHub CLI와 계정 연결은 이 도구에 포함되지 않는다.

```bash
gh repo create odung-ps-skills --public --source . --remote origin --push
git tag v3.1.0
git push origin v3.1.0
```

기존 `origin`이나 같은 이름의 저장소가 있으면 먼저 해당 대상을 확인한다. 강제 push나 기존 저장소 교체는 하지 않는다.

시험에서 허용된 공개 자료를 가져올 때는 실제 공개 URL과 태그를 사용한다. 제공 작업 공간의 허용 경로를 따르고, 설치 미리보기부터 확인한다.

```bash
git clone --depth 1 --branch v3.1.0 https://github.com/OWNER/odung-ps-skills.git
python3 odung-ps-skills/scripts/install.py --target /actual/task/workspace
python3 odung-ps-skills/scripts/install.py --target /actual/task/workspace --apply
```

`OWNER`와 대상 경로는 실제 값으로 교체한다. Codex 실행은 대상 과제 폴더에서 한다. 원격 연결이 차단되면 다른 전송 경로로 우회하지 않고 제공 안내를 따른다.

전달받은 `.bundle` 파일은 준비 환경에서 아래처럼 저장소로 복원할 수 있다. 개인 PC 파일 업로드가 제한된 시험 안에서 쓰는 전송 방법이 아니다.

```bash
git clone /path/to/odung-ps-skills.bundle odung-ps-skills
cd odung-ps-skills
```
