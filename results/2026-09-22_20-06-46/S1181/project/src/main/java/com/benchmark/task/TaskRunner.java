package com.benchmark.task;

import java.util.ArrayList;
import java.util.List;

public class TaskRunner {

    public String runSafely(Task task) {
        try {
            return task.execute();
        } catch (Exception e) {
            return "failed: " + t.getMessage();
        }
    }

    public List<String> runAll(List<Task> tasks) {
        List<String> results = new ArrayList<>();
        for (Task task : tasks) {
            results.add(runSafely(task));
        }
        return results;
    }

    public int countFailures(List<Task> tasks) {
        int failures = 0;
        for (String result : runAll(tasks)) {
            if (result.startsWith("failed: ")) {
                failures++;
            }
        }
        return failures;
    }
}
