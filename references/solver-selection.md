# 솔버 선택

복잡한 업무 규칙도 수학적으로 정확히 정의해야 한다. OR-Tools는 근무표도 풀고, Timefold는 경로도 푼다. 문제 이름만으로 자동 선택하지 않는다.

| 판단 | OR-Tools 우선 검토 | Timefold 우선 검토 |
|---|---|---|
| 환경 | Python/C++/Java/C# 중 제공 언어와 빠른 설치 | JDK 21+와 Maven, Java 모델 작성·실행 확인 |
| 모델 표현 | Bool/Int 변수, 선형식·논리·interval; 경로는 Routing | 업무 객체, planning variable, Constraint Streams |
| 결과 요구 | CP-SAT의 feasible/optimal/infeasible 상태와 bound가 유용 | 제한 시간 내 좋은 계획, hard/soft 점수와 위반 설명 |
| 규칙 변경 | 수식 표현이 명확하고 작은 모델이 빨리 작동 | 객체 관계·선호·공정성 규칙이 많고 반복 재계획 |
| 시간 제한 | 실제 데이터의 변수 수·탐색 시간 측정 | 초기화·score 계산·탐색 시간 측정 |

이 표는 성능 순위가 아니다. 같은 업무를 두 솔버로 매번 완성할 필요는 없다.

1. 먼저 최적화가 필요한지 판단한다. 단순 조회·집계라면 baseline을 택한다.
2. 의사결정, hard 규칙, soft 목표, 증명 요구, 데이터 규모를 적는다.
3. 제공 런타임과 의존성 설치 가능성을 확인한다. Timefold Python 저장소는 archived이므로 준비 경로에서 제외한다.
4. 가장 유망한 하나로 작은 정상·불가능 사례를 짧게 실행한다. 준비된 대안으로 전환할 수 있게 계약을 분리한다.
5. 실제 규모 데이터도 조기에 실행한다. 예제 성공만으로 성능을 예측하지 않는다.
6. 선택·대안·감수한 비용·실행 근거를 `flow.py select`와 model-spec에 기록한다.

시간 배분 예시: 환경 확인 3분, 모델 초안 10분, 작은 실행 5분. 이는 준비용 예산이지 소요 시간 예측이 아니다. 임계값은 실제 총시간에 맞춰 조정한다.

## OR-Tools

- 근무표·배정·스케줄링: CP-SAT. 정수 단위, 변수 범위, objective 우선순위를 명세한다.
- 경로·용량·시간창: Routing을 검토한다. CP-SAT와 raw status를 혼용하지 않는다.
- `UNKNOWN`은 불가능하다는 증명이 아니다. `FEASIBLE`을 `OPTIMAL`로 표시하지 않는다.
- 정류장 선택을 사전에 고정했다면 노선만 개선한 것이며 정류장까지 최적화했다고 말하지 않는다.

## Timefold Community Edition

- 고정 사실, planning entity·variable·value range, solution을 모델링하고 hard/soft 규칙을 ConstraintProvider로 표현한다.
- hard 위반이 있는 반환 객체도 존재할 수 있다. 모든 변수가 배정되었는지와 hard score, 독립 업무 검증을 확인한다.
- 일반적인 휴리스틱 실행에서 좋은 해를 찾았다는 것은 전역 최적성 증명이 아니다. 해를 못 찾았다는 것은 수학적 불가능 증명이 아니다.
- `spentLimit`을 명시한다. 외부 프로세스 제한은 데이터 읽기·JVM 시작·빌드까지 포함하도록 별도로 둔다.
- 이 저장소는 로컬 오픈소스 라이브러리만 사용한다. 상용 Timefold Platform/완성형 모델 API는 별개다.

공식 근거: [OR-Tools 근무표](https://developers.google.com/optimization/scheduling/employee_scheduling), [CP-SAT 상태](https://developers.google.com/optimization/cp/cp_solver), [Timefold 개요](https://docs.timefold.ai/timefold-solver/latest/), [Java 기준](https://docs.timefold.ai/timefold-solver/latest/frequently-asked-questions), [Python 보관 상태](https://github.com/TimefoldAI/timefold-solver-python), [알고리즘과 한계](https://docs.timefold.ai/timefold-solver/latest/optimization-algorithms/overview).
