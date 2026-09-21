package com.benchmark.customer;

public class CustomerProfile {

    @NonNull
    private String email;

    private String phoneNumber;

    public void reset() {
        this.email = null;
        this.phoneNumber = null;
    }

    public CustomerProfile() {
    }

    public CustomerProfile(String email, String phoneNumber) {
        this.email = email;
        this.phoneNumber = phoneNumber;
    }

    public String getEmail() {
        return email;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }
}
