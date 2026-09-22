package com.benchmark.usersearch;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class UserSearchDaoTest {

    private Connection connection;
    private UserSearchDao dao;

    @BeforeEach
    void setUp() throws SQLException {
        connection = DriverManager.getConnection("jdbc:h2:mem:");
        try (Statement statement = connection.createStatement()) {
            statement.execute("CREATE TABLE users (id INT PRIMARY KEY, username VARCHAR(255))");
            statement.execute("INSERT INTO users (id, username) VALUES (1, 'alice')");
            statement.execute("INSERT INTO users (id, username) VALUES (2, 'bob')");
        }
        dao = new UserSearchDao(connection);
    }

    @AfterEach
    void tearDown() throws SQLException {
        connection.close();
    }

    @Test
    void findsExistingUserByUsername() throws SQLException {
        try (ResultSet resultSet = dao.searchByUsername("alice")) {
            assertTrue(resultSet.next());
            assertEquals(1, resultSet.getInt("id"));
            assertFalse(resultSet.next());
        }
    }

    @Test
    void returnsNoRowsForUnknownUsername() throws SQLException {
        try (ResultSet resultSet = dao.searchByUsername("nobody")) {
            assertFalse(resultSet.next());
        }
    }
}
