# SonarQube Rule: java:S5542

## Encryption algorithms should be used with secure mode and padding scheme

ECB (Electronic Codebook) mode encrypts each block of plaintext independently, so
identical plaintext blocks always produce identical ciphertext blocks. This leaks
patterns in the data and makes ECB unsuitable for most real-world use. A mode that
uses an initialization vector (IV), such as GCM (preferred, since it's authenticated)
or CBC, should be used instead.

For example:

```java
Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
cipher.init(Cipher.ENCRYPT_MODE, key);
```

should be written using an authenticated mode with a randomly generated IV, e.g.:

```java
byte[] iv = new byte[12];
new SecureRandom().nextBytes(iv);
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
```
