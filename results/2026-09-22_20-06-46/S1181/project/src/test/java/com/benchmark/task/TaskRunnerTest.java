package com.benchmark.task;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Test;

class TaskRunnerTest {

    private final TaskRunner runner = new TaskRunner();

    @Test
    void successfulTaskReturnsItsResult() {
        assertEquals("ok", runner.runSafely(() -> "ok"));
    }

    @Test
    void checkedExceptionIsReportedAsAFailure() {
        assertEquals(
                "failed: disk offline",
                runner.runSafely(() -> {
                    throw new TaskFailedException("disk offline");
                }));
    }

    @Test
    void runtimeExceptionIsReportedAsAFailure() {
        assertEquals(
                "failed: bad state",
                runner.runSafely(() -> {
                    throw new IllegalStateException("bad state");
                }));
    }

    @Test
    void errorsMustNotBeSwallowed() {
        assertThrows(
                StackOverflowError.class,
                () -> runner.runSafely(() -> {
                    throw new StackOverflowError("stack exhausted");
                }),
                "JVM Errors are not recoverable and must propagate to the caller");
    }

    @Test
    void failuresAcrossTasksAreCounted() {
        List<Task> tasks = List.of(
                () -> "ok",
                () -> {
                    throw new TaskFailedException("nope");
                },
                () -> "fine");

        assertEquals(1, runner.countFailures(tasks));
    }
}
