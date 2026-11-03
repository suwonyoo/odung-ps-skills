package local.odung;
import java.util.List;
public record Employee(String id, List<String> skills, List<Integer> unavailable_days) {}
