package local.odung;
import java.nio.file.*;
import java.time.Duration;
import java.security.MessageDigest;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import ai.timefold.solver.core.api.solver.SolverFactory;
import ai.timefold.solver.core.config.solver.SolverConfig;
import ai.timefold.solver.core.config.solver.termination.TerminationConfig;

public class Main {
    private static double seconds(long start) { return (System.nanoTime()-start)/1_000_000_000.0; }
    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) throw new IllegalArgumentException("INPUT.json SECONDS [OUTPUT.json]");
        double limit = Double.parseDouble(args[1]);
        if (!Double.isFinite(limit) || limit <= 0 || limit > 3600) throw new IllegalArgumentException("SECONDS must be > 0 and <= 3600");
        long started = System.nanoTime();
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        ObjectMapper mapper = new ObjectMapper();
        validateRaw(mapper.readTree(raw));
        Schedule input = mapper.readValue(raw, Schedule.class);
        validateInput(input);
        long modelStart = System.nanoTime();
        var config = new SolverConfig().withSolutionClass(Schedule.class).withEntityClasses(Shift.class)
            .withConstraintProviderClass(Rules.class).withRandomSeed(0L)
            .withTerminationConfig(new TerminationConfig().withSpentLimit(Duration.ofMillis(Math.max(1,(long)(limit*1000)))));
        var solver = SolverFactory.<Schedule>create(config).buildSolver();
        double modelSeconds = seconds(modelStart);
        Double[] first = {null}, last = {null};
        long solving = System.nanoTime();
        solver.addEventListener(e -> {
            var s = e.getNewBestSolution();
            double at = seconds(solving);
            last[0] = at;
            if (first[0] == null && s.score.isFeasible() && s.shifts.stream().allMatch(x -> x.employee != null)) first[0] = at;
        });
        Schedule best = solver.solve(input);
        double solveSeconds = seconds(solving);
        long checking = System.nanoTime();
        List<Map<String,String>> assignments = new ArrayList<>();
        List<String> violations = new ArrayList<>();
        Set<String> occupied = new HashSet<>();
        int penalty = 0;
        for (Shift s : best.shifts) {
            if (s.employee == null) { violations.add("MISSING_SHIFT:"+s.id); continue; }
            Employee emp = s.employee;
            assignments.add(Map.of("shift_id",s.id,"employee_id",emp.id()));
            if (!emp.skills().contains(s.skill)) violations.add("SKILL:"+s.id);
            if (emp.unavailable_days().contains(s.day)) violations.add("UNAVAILABLE:"+s.id);
            // Identity tuple is encoded without concatenation collisions.
            if (!occupied.add(mapper.writeValueAsString(List.of(emp.id(),s.day)))) violations.add("DAILY_CAPACITY:"+emp.id());
            if (!emp.id().equals(s.preferred_employee)) penalty++;
        }
        boolean assigned = assignments.size() == best.shifts.size();
        boolean valid = violations.isEmpty();
        boolean feasible = assigned && valid && best.score != null && best.score.isFeasible();
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("schema_version",1); result.put("engine","timefold"); result.put("engine_version","2.7.1");
        result.put("input_version",input.input_version);
        result.put("input_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw)));
        result.put("raw_status", "TERMINATED"); result.put("score",best.score == null ? null : best.score.toString());
        result.put("has_solution", assigned); result.put("feasible",feasible);
        result.put("optimality_proven",false); result.put("infeasibility_proven",false);
        result.put("outcome",feasible ? "FEASIBLE_FOUND" : "NO_FEASIBLE_FOUND");
        result.put("assignments",assignments); result.put("objective",penalty); result.put("objective_bound",null);
        result.put("limits",Map.of("solver_seconds",limit,"seed",0));
        result.put("validation",Map.of("valid",valid,"violations",violations,"preference_penalty",penalty));
        Map<String,Object> timing = new LinkedHashMap<>();
        timing.put("model_seconds",modelSeconds); timing.put("solve_seconds",solveSeconds);
        timing.put("first_feasible_seconds",first[0]); timing.put("last_improvement_seconds",last[0]);
        timing.put("validation_seconds",seconds(checking)); timing.put("total_seconds",seconds(started));
        result.put("timing",timing);
        String text = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
        if(args.length==3) Files.writeString(Path.of(args[2]),text+"\n");
        System.out.println(text);
        System.exit(feasible ? 0 : 3);
    }

    private static void fields(JsonNode n, String... required) {
        Set<String> actual=new HashSet<>(); n.fieldNames().forEachRemaining(actual::add);
        if(!n.isObject() || !actual.equals(Set.of(required))) throw new IllegalArgumentException("Missing or unsupported input fields");
    }
    private static void text(JsonNode n) {
        if(!n.isTextual() || n.textValue().isEmpty()) throw new IllegalArgumentException("Expected nonempty text");
    }
    private static void day(JsonNode n) {
        if(!n.isIntegralNumber() || !n.canConvertToInt()) throw new IllegalArgumentException("Day must be a 32-bit integer");
    }
    private static void validateRaw(JsonNode p) {
        fields(p,"input_version","employees","shifts"); text(p.get("input_version"));
        if(!p.get("employees").isArray() || !p.get("shifts").isArray()) throw new IllegalArgumentException("Expected arrays");
        for(JsonNode e:p.get("employees")) {
            fields(e,"id","skills","unavailable_days"); text(e.get("id"));
            if(!e.get("skills").isArray() || !e.get("unavailable_days").isArray()) throw new IllegalArgumentException("Expected employee arrays");
            for(JsonNode v:e.get("skills"))text(v);
            for(JsonNode v:e.get("unavailable_days"))day(v);
        }
        for(JsonNode s:p.get("shifts")) {
            fields(s,"id","day","skill","preferred_employee");
            text(s.get("id"));day(s.get("day"));text(s.get("skill"));text(s.get("preferred_employee"));
        }
    }
    private static void validateInput(Schedule p) {
        if(p.input_version==null || p.input_version.isBlank() || p.employees==null || p.employees.isEmpty() || p.shifts==null || p.shifts.isEmpty())
            throw new IllegalArgumentException("Nonempty version, employees and shifts required");
        Set<String> employees=new HashSet<>(), shifts=new HashSet<>();
        for(Employee e:p.employees) {
            if(e.id()==null || e.id().isBlank() || !employees.add(e.id()) || e.skills()==null || e.unavailable_days()==null)
                throw new IllegalArgumentException("Invalid employee or duplicate ID");
        }
        for(Shift s:p.shifts) {
            if(s.id==null || s.id.isBlank() || !shifts.add(s.id) || s.skill==null || !employees.contains(s.preferred_employee) || s.employee!=null)
                throw new IllegalArgumentException("Invalid shift, duplicate ID, or injected assignment");
        }
        if(p.score!=null) throw new IllegalArgumentException("Input must not supply score");
    }
}
