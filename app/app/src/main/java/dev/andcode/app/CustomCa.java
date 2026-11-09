package dev.andcode.app;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.Base64;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** User-confirmed optional CA data only; never downloads or disables verification. */
final class CustomCa {
    static final int MAX_BYTES = 65536;
    private static final Pattern PEM = Pattern.compile(
        "\\A\\s*-----BEGIN CERTIFICATE-----\\s*([A-Za-z0-9+/=\\r\\n]+)\\s*-----END CERTIFICATE-----\\s*\\z");

    static final class Info {
        final String sha256;
        final String subject;
        final String fingerprint;
        final String expires;
        Info(String digest, X509Certificate cert) throws Exception {
            sha256 = digest;
            subject = cert.getSubjectX500Principal().getName();
            fingerprint = hex(MessageDigest.getInstance("SHA-256").digest(cert.getEncoded()));
            expires = cert.getNotAfter().toString();
        }
    }

    private CustomCa() {}

    static byte[] read(InputStream in) throws IOException {
        if (in == null) throw new IOException("无法读取所选证书");
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int n;
        while ((n = in.read(buffer)) != -1) {
            if (out.size() + n > MAX_BYTES) throw new IOException("证书超过 64 KiB");
            out.write(buffer, 0, n);
        }
        return out.toByteArray();
    }

    static Info inspect(byte[] bytes) throws IOException {
        if (bytes.length == 0 || bytes.length > MAX_BYTES) throw new IOException("证书大小无效");
        try {
            Matcher match = PEM.matcher(new String(bytes, StandardCharsets.US_ASCII));
            if (!match.matches()) throw new IOException("仅接受单个 PEM CA 证书，不接受私钥或证书集合");
            byte[] der = Base64.getDecoder().decode(match.group(1).replaceAll("\\s", ""));
            ByteArrayInputStream input = new ByteArrayInputStream(der);
            X509Certificate cert = (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(input);
            if (input.available() != 0 || !java.util.Arrays.equals(der, cert.getEncoded()))
                throw new IOException("证书含额外或非规范 DER 数据");
            cert.checkValidity();
            if (cert.getBasicConstraints() < 0) throw new IOException("所选证书不是 CA");
            boolean[] usage = cert.getKeyUsage();
            if (usage != null && (usage.length <= 5 || !usage[5])) throw new IOException("证书不允许签发证书");
            return new Info(hex(MessageDigest.getInstance("SHA-256").digest(bytes)), cert);
        } catch (IOException error) {
            throw error;
        } catch (Exception error) {
            throw new IOException("CA 解析/有效期检查失败", error);
        }
    }

    static Info install(Path files, byte[] bytes, String expected) throws IOException {
        Info info = inspect(bytes);
        if (!info.sha256.equals(normalize(expected))) throw new IOException("PEM 文件 SHA-256 不匹配；未导入");
        Path dir = files.resolve("custom-ca");
        if (!Files.exists(dir, LinkOption.NOFOLLOW_LINKS)) Files.createDirectory(dir);
        if (Files.isSymbolicLink(dir) || !Files.isDirectory(dir, LinkOption.NOFOLLOW_LINKS))
            throw new IOException("CA 目录不是普通目录");
        Path target = dir.resolve(info.sha256 + ".pem");
        if (!Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            // Content addressed, never overwrite. A failed partial write stays rejected.
            try (java.io.OutputStream out = Files.newOutputStream(target, StandardOpenOption.CREATE_NEW)) {
                out.write(bytes);
            }
        }
        verify(files, info.sha256);
        return info;
    }

    static Path verify(Path files, String digest) throws IOException {
        String normalized = normalize(digest);
        Path dir = files.resolve("custom-ca");
        Path file = dir.resolve(normalized + ".pem");
        if (Files.isSymbolicLink(dir) || !Files.isDirectory(dir, LinkOption.NOFOLLOW_LINKS)
                || !Files.isRegularFile(file, LinkOption.NOFOLLOW_LINKS))
            throw new IOException("已启用的 CA 文件缺失或为链接；拒绝启动");
        try (InputStream in = Files.newInputStream(file, LinkOption.NOFOLLOW_LINKS)) {
            if (!inspect(read(in)).sha256.equals(normalized)) throw new IOException("CA 副本摘要改变；拒绝启动");
        }
        return file.toAbsolutePath();
    }

    static void apply(Map<String, String> env, Path files, boolean enabled, String digest) throws IOException {
        // No inherited trust overrides or disabled verifier, even while this option is off.
        for (String key : new String[]{"NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "SSL_CERT_DIR",
                "NODE_TLS_REJECT_UNAUTHORIZED", "NODE_USE_SYSTEM_CA", "NODE_OPTIONS", "BUN_OPTIONS"}) env.remove(key);
        if (enabled) env.put("NODE_EXTRA_CA_CERTS", verify(files, digest).toString());
    }

    static String normalize(String value) throws IOException {
        String digest = value == null ? "" : value.trim().toLowerCase(java.util.Locale.ROOT);
        if (!digest.matches("[a-f0-9]{64}")) throw new IOException("请输入 64 位 PEM 文件 SHA-256");
        return digest;
    }

    private static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder();
        for (byte b : bytes) text.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return text.toString();
    }
}
