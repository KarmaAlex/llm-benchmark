package com.benchmark.userlookup;

public class UserController {

    private final UserRepository userRepository;

    public UserController(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public String getEmailForUser(long id) {
        return userRepository.findById(id).get().getEmail();
    }
}
