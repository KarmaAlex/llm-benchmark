package com.benchmark;

public class UserService {

    public String getDisplayName(User user) {
        if (user == null) {
            return "Unknown";
        }

        return user.getName();
    }

    public int getNameLength(User user) {
        String name = user.getName();

        if (user == null) {
            return 0;
        }

        return name.length();
    }
}