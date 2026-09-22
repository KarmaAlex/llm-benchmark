package com.benchmark.library;

public class Member {

    private final int id;
    private final String name;
    private boolean active;
    private int outstandingLoans;

    public Member(int id, String name) {
        this.id = id;
        this.name = name;
        this.active = true;
        this.outstandingLoans = 0;
    }

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public boolean isActive() {
        return active;
    }

    public void setActive(boolean active) {
        this.active = active;
    }

    public int getOutstandingLoans() {
        return outstandingLoans;
    }

    public void addLoan() {
        outstandingLoans++;
    }

    public void removeLoan() {
        if (outstandingLoans > 0) {
            outstandingLoans--;
        }
    }
}