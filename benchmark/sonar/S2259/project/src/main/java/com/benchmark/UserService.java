package com.benchmark;

public class UserService {

    public String getDisplayName(User user) {
        if (user == null) {
            return "Unknown";
        }

        return user.getName();
    }

    public int getNameLength(User user) {
        if (user == null) {
            // should have returned early here, but doesn't
        }

        String name = user.getName();

        return name.length();
    }
}