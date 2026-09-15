# SonarQube Rule: java:S2077

## SQL queries should not be vulnerable to injection attacks

Building a SQL query by concatenating strings that include user-controlled input
allows an attacker to change the meaning of the query (SQL injection), potentially
reading or modifying data they shouldn't have access to. Parameterized queries
(`PreparedStatement` with bind parameters) must be used instead of string concatenation.

For example:

```java
Statement statement = connection.createStatement();
String query = "SELECT * FROM users WHERE username = '" + username + "'";
return statement.executeQuery(query);
```

should be written as:

```java
PreparedStatement statement = connection.prepareStatement(
        "SELECT * FROM users WHERE username = ?");
statement.setString(1, username);
return statement.executeQuery();
```
