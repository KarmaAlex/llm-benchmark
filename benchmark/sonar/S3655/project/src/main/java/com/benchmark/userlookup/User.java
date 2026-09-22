package com.benchmark.userlookup;

public class User {

    private final long id;
    private final String email;

    public User(long id, String email) {
        this.id = id;
        this.email = email;
    }

    public long getId() {
        return id;
    }

    public String getEmail() {
        return email;
    }
}
