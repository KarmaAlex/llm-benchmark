package com.benchmark.crypto;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class DataEncryptionUtilTest {

    private final DataEncryptionUtil util = new DataEncryptionUtil();
    private SecretKey key;

    @BeforeEach
    void setUp() throws GeneralSecurityException {
        KeyGenerator keyGenerator = KeyGenerator.getInstance("AES");
        keyGenerator.init(128);
        key = keyGenerator.generateKey();
    }

    @Test
    void decryptingEncryptedDataReturnsOriginalPlainText() throws GeneralSecurityException {
        byte[] plainText = "Hello, World!".getBytes(StandardCharsets.UTF_8);

        byte[] cipherText = util.encrypt(plainText, key);
        byte[] roundTripped = util.decrypt(cipherText, key);

        assertArrayEquals(plainText, roundTripped);
    }

    @Test
    void encryptingProducesDifferentBytesThanThePlainText() throws GeneralSecurityException {
        byte[] plainText = "Sensitive payload data".getBytes(StandardCharsets.UTF_8);

        byte[] cipherText = util.encrypt(plainText, key);

        assertNotEquals(new String(plainText, StandardCharsets.UTF_8), new String(cipherText, StandardCharsets.UTF_8));
    }

    @Test
    void roundTripWorksForLongerPayloads() throws GeneralSecurityException {
        byte[] plainText = "A".repeat(500).getBytes(StandardCharsets.UTF_8);

        byte[] roundTripped = util.decrypt(util.encrypt(plainText, key), key);

        assertArrayEquals(plainText, roundTripped);
    }
}
