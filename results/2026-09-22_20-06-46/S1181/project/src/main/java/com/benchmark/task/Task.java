package com.benchmark.task;

@FunctionalInterface
public interface Task {

    String execute() throws TaskFailedException;
}
