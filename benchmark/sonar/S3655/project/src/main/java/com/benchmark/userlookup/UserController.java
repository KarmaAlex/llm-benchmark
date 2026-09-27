package com.benchmark.userlookup;

public class UserController {

    private final UserRepository userRepository;

    public UserController(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    /**
     * Looks up the email address of a user.
     *
     * @param id the id of the user
     * @return the user's email address, or {@code null} if no user has that id
     */
    public String getEmailForUser(long id) {
        return userRepository.findById(id).get().getEmail();
    }
}
