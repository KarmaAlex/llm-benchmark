package com.benchmark.crypto;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import java.security.GeneralSecurityException;

public class DataEncryptionUtil {

    public byte[] encrypt(byte[] plainText, SecretKey key) throws GeneralSecurityException {
byte[] iv = new byte[12];
new java.security.SecureRandom().nextBytes(iv);
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
cipher.init(Cipher.ENCRYPT_MODE, key, new javax.crypto.spec.GCMParameterSpec(128, iv));
return cipher.doFinal(plainText);
    }

    public byte[] decrypt(byte[] cipherText, SecretKey key) throws GeneralSecurityException {
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
cipher.init(Cipher.DECRYPT_MODE, key, new javax.crypto.spec.GCMParameterSpec(128, iv));
return cipher.doFinal(cipherText);
    }
}
