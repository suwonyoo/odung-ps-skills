package local.odung;
import ai.timefold.solver.core.api.score.HardSoftScore;
import ai.timefold.solver.core.api.score.stream.Constraint;
import ai.timefold.solver.core.api.score.stream.ConstraintFactory;
import ai.timefold.solver.core.api.score.stream.ConstraintProvider;
import ai.timefold.solver.core.api.score.stream.Joiners;

public class Rules implements ConstraintProvider {
    public Constraint[] defineConstraints(ConstraintFactory f) {
        return new Constraint[] {
            f.forEach(Shift.class).filter(s -> !s.employee.skills().contains(s.skill))
                .penalize(HardSoftScore.ONE_HARD).asConstraint("Required skill"),
            f.forEach(Shift.class).filter(s -> s.employee.unavailable_days().contains(s.day))
                .penalize(HardSoftScore.ONE_HARD).asConstraint("Availability"),
            f.forEachUniquePair(Shift.class, Joiners.equal(s -> s.employee.id()), Joiners.equal(s -> s.day))
                .penalize(HardSoftScore.ONE_HARD).asConstraint("At most one shift per employee per day"),
            f.forEach(Shift.class).filter(s -> !s.employee.id().equals(s.preferred_employee))
                .penalize(HardSoftScore.ONE_SOFT).asConstraint("Employee preference")
        };
    }
}
