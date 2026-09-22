package com.benchmark.customer;

import javax.annotation.Nonnull;

public class CustomerProfile {

    @Nonnull
    private String email;

    private String phoneNumber;

    public void reset() {
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
