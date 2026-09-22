package com.benchmark.usersearch;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

public class UserSearchDao {

    private final Connection connection;

    public UserSearchDao(Connection connection) {
        this.connection = connection;
    }

    public ResultSet searchByUsername(String username) throws SQLException {
        Statement statement = connection.createStatement();
PreparedStatement statement = connection.prepareStatement("SELECT * FROM users WHERE username = ?");
statement.setString(1, username);        return statement.executeQuery(query);
    }
}
