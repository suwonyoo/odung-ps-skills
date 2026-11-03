# 두 솔버로 같은 작은 문제 실행

합성 데이터만 사용한 준비 예제다. 실제 과제의 완성형 근무표 서비스가 아니다. 각 근무에 직원 한 명, 하루 한 근무, 자격·근무 가능일 준수, 선호 직원 불일치 최소화만 구현한다. 휴게·노동법·시간 중첩·장기 공정성·경로는 포함하지 않는다.

`problem.json`은 선호 위반 0인 해가 존재하고, `impossible.json`은 사용 가능한 직원이 없어 불가능하다. 후자에서 CP-SAT는 증명 상태를, Timefold는 제한 시간 내 feasible 해 미발견을 반환한다. 두 의미를 같게 표현하지 않는다.

## OR-Tools

Python 3.12 가상 환경에서 고정 버전을 설치한다. 제공 환경의 버전 호환성은 별도로 확인한다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r ortools/requirements.txt
.venv/bin/python ortools/solve.py problem.json --seconds 3 --output result.json
python3 validate.py problem.json result.json
```

## Timefold Community Edition

JDK 21+와 Maven이 필요하다. Python판이나 상용 모델 API를 사용하지 않는다. 준비 시 다운로드·컴파일을 완료하고 실제 시험 환경에서 다시 작은 실행으로 확인한다. 기본 예제는 Java 라이브러리를 프로세스로 호출하므로 서버 프레임워크를 강제하지 않는다.

```bash
mvn -f timefold/pom.xml -q compile dependency:build-classpath -Dmdep.outputFile=classpath.txt
java -cp "timefold/target/classes:$(cat timefold/classpath.txt)" local.odung.Main problem.json 3 result.json
python3 validate.py problem.json result.json
```

위 classpath 구분자 `:`는 Linux/macOS용이다. Windows는 `;`와 해당 셸의 파일 읽기 문법을 쓴다. 최초 Maven 빌드와 warm solve 시간은 분리한다. 두 솔버 결과의 공통 필드: input_version, input_sha256, engine, raw_status, has_solution, feasible, optimality_proven, infeasibility_proven, assignments, validation, timing. has_solution은 완성된 후보 존재이며 feasible은 규칙 통과를 뜻한다.

Timefold의 `TERMINATED`는 이 어댑터가 solve 반환을 나타내는 상태다. CP-SAT의 native status와 같은 enum이 아니다. Timefold의 해가 hard 위반을 포함하면 exit 3이며 publication 대상이 아니다. CP-SAT도 feasible 결과가 없으면 exit 3이다. 입출력·런타임 오류는 별도 비영 종료다.

각 실행을 `flow.py run --limit ... -- ...`으로 감싸면 전체 프로세스 시간·외부 제한·로그를 상태판에 기록한다. 입력·모델·품질이 다른 실행을 속도 비교로 단정하지 않는다. 이 작은 예제는 설치 확인과 계약 학습용이다.
