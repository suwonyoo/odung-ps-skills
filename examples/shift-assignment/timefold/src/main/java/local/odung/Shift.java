package local.odung;
import ai.timefold.solver.core.api.domain.entity.PlanningEntity;
import ai.timefold.solver.core.api.domain.common.PlanningId;
import ai.timefold.solver.core.api.domain.variable.PlanningVariable;

@PlanningEntity
public class Shift {
    @PlanningId public String id;
    public int day;
    public String skill;
    public String preferred_employee;
    @PlanningVariable public Employee employee;
    public Shift() {}
}
