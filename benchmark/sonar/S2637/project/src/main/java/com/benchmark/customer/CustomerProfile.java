package com.benchmark.customer;

public class CustomerProfile {

    @NonNull
    private String email;

    private String phoneNumber;

    public void reset() {
        this.email = null;
        this.phoneNumber = null;
    }

    public String getEmail() {
        return email;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }
}
