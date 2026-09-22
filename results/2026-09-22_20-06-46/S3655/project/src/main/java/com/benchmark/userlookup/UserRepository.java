package com.benchmark.userlookup;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public class UserRepository {

    private final Map<Long, User> usersById = new HashMap<>();

    public void save(User user) {
        usersById.put(user.getId(), user);
    }

    public Optional<User> findById(long id) {
        return Optional.ofNullable(usersById.get(id));
    }
}
