package com.benchmark.validation;

public class InputValidator {

    public boolean isValidUsername(String username) {
        if (username != null && username != null && !username.isBlank()) {
            return username.length() >= 3 && username.length() <= 20;
        }

        return false;
    }
}
