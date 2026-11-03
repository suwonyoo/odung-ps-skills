package local.odung;
import java.util.List;
import ai.timefold.solver.core.api.domain.solution.PlanningSolution;
import ai.timefold.solver.core.api.domain.solution.PlanningEntityCollectionProperty;
import ai.timefold.solver.core.api.domain.solution.ProblemFactCollectionProperty;
import ai.timefold.solver.core.api.domain.solution.PlanningScore;
import ai.timefold.solver.core.api.domain.valuerange.ValueRangeProvider;
import ai.timefold.solver.core.api.score.HardSoftScore;

@PlanningSolution
public class Schedule {
    public String input_version;
    @ValueRangeProvider @ProblemFactCollectionProperty public List<Employee> employees;
    @PlanningEntityCollectionProperty public List<Shift> shifts;
    @PlanningScore public HardSoftScore score;
    public Schedule() {}
}
