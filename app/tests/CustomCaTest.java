package dev.andcode.app;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/** Platform JDK test, ephemeral self-generated certificates/keys only. */
public class CustomCaTest {
    private static int checks;
    interface Checked { void run() throws Exception; }
    static void check(boolean ok) {
        if (!ok) throw new AssertionError("Check failed");
        checks++;
    }
    static void reject(Checked action) throws Exception {
        try { action.run(); } catch (IOException expected) { checks++; return; }
        throw new AssertionError("Expected IOException");
    }
    static byte[] certificate(Path temp, String name, String constraints, String usage, boolean expired) throws Exception {
        String exe = System.getProperty("os.name").startsWith("Windows") ? "keytool.exe" : "keytool";
        String tool = Path.of(System.getProperty("java.home"), "bin", exe).toString();
        Path store = temp.resolve(name + ".p12");
        java.util.List<String> command = new java.util.ArrayList<>(java.util.List.of(tool, "-genkeypair",
            "-alias", name, "-dname", "CN=Ephemeral andcode test " + name, "-keyalg", "EC", "-groupname", "secp256r1",
            "-validity", expired ? "1" : "365", "-ext", constraints, "-ext", usage,
            "-keystore", store.toString(), "-storepass", "test-only-password", "-noprompt"));
        if (expired) command.addAll(java.util.List.of("-startdate", "2020/01/01 00:00:00"));
        Process gen = new ProcessBuilder(command).redirectError(ProcessBuilder.Redirect.INHERIT).start();
        if (gen.waitFor() != 0) throw new AssertionError("keytool generate failed");
        Process export = new ProcessBuilder(tool, "-exportcert", "-rfc", "-alias", name,
            "-keystore", store.toString(), "-storepass", "test-only-password").start();
        byte[] pem = export.getInputStream().readAllBytes();
        if (export.waitFor() != 0) throw new AssertionError("keytool export failed");
        return pem;
    }
    public static void main(String[] args) throws Exception {
        Path temp = Files.createTempDirectory("andcode-ca-test-");
        try {
            byte[] ca = certificate(temp, "ca", "bc=ca:true", "ku=keyCertSign,cRLSign", false);
            byte[] leaf = certificate(temp, "leaf", "bc=ca:false", "ku=digitalSignature", false);
            byte[] wrongUsage = certificate(temp, "wrong-usage", "bc=ca:true", "ku=digitalSignature", false);
            byte[] expired = certificate(temp, "expired", "bc=ca:true", "ku=keyCertSign", true);
            CustomCa.Info info = CustomCa.inspect(ca);
            check(info.sha256.matches("[a-f0-9]{64}"));
            check(info.fingerprint.matches("[a-f0-9]{64}"));
            check(info.subject.contains("Ephemeral"));
            reject(() -> CustomCa.inspect(leaf));
            reject(() -> CustomCa.inspect(wrongUsage));
            reject(() -> CustomCa.inspect(expired));
            reject(() -> CustomCa.inspect(new byte[0]));
            reject(() -> CustomCa.inspect("not PEM".getBytes(StandardCharsets.US_ASCII)));
            String text = new String(ca, StandardCharsets.US_ASCII);
            reject(() -> CustomCa.inspect((text + text).getBytes(StandardCharsets.US_ASCII)));
            reject(() -> CustomCa.inspect((text + "-----BEGIN PRIVATE KEY-----").getBytes(StandardCharsets.US_ASCII)));
            reject(() -> CustomCa.read(new ByteArrayInputStream(new byte[CustomCa.MAX_BYTES + 1])));
            check(CustomCa.read(new ByteArrayInputStream(ca)).length == ca.length);
            Path files = Files.createDirectory(temp.resolve("files"));
            reject(() -> CustomCa.install(files, ca, "0".repeat(64)));
            check(!Files.exists(files.resolve("custom-ca")));
            CustomCa.install(files, ca, info.sha256.toUpperCase(java.util.Locale.ROOT));
            CustomCa.install(files, ca, info.sha256);
            Path installed = CustomCa.verify(files, info.sha256);
            check(java.util.Arrays.equals(Files.readAllBytes(installed), ca));
            Map<String, String> env = new HashMap<>();
            env.put("HOME", "preserved");
            for (String key : java.util.List.of("NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "SSL_CERT_DIR",
                    "NODE_TLS_REJECT_UNAUTHORIZED", "NODE_USE_SYSTEM_CA", "NODE_OPTIONS", "BUN_OPTIONS")) env.put(key, "bad");
            CustomCa.apply(env, files, false, "missing");
            check(env.equals(Map.of("HOME", "preserved")));
            CustomCa.apply(env, files, true, info.sha256);
            check(env.get("NODE_EXTRA_CA_CERTS").equals(installed.toString()));
            Files.writeString(installed, "tampered");
            reject(() -> CustomCa.apply(env, files, true, info.sha256));
            check(!env.containsKey("NODE_EXTRA_CA_CERTS"));
            reject(() -> CustomCa.install(files, ca, info.sha256));
            reject(() -> CustomCa.verify(files, "../escape"));
            Files.delete(installed);
            reject(() -> CustomCa.verify(files, info.sha256));
            boolean links = false;
            try { Files.createSymbolicLink(installed, temp.resolve("ca.p12")); links = true; }
            catch (IOException | UnsupportedOperationException ignored) {}
            if (links) {
                reject(() -> CustomCa.verify(files, info.sha256));
                reject(() -> CustomCa.install(files, ca, info.sha256));
                Files.delete(installed);
                Files.delete(files.resolve("custom-ca"));
                Files.createSymbolicLink(files.resolve("custom-ca"), temp);
                reject(() -> CustomCa.install(files, ca, info.sha256));
                reject(() -> CustomCa.verify(files, info.sha256));
            }
            System.out.println("Custom CA: " + checks + " checks passed; symlink tests " + (links ? "passed" : "unavailable"));
        } finally {
            try (java.util.stream.Stream<Path> entries = Files.walk(temp)) {
                for (Path entry : entries.sorted(java.util.Comparator.reverseOrder()).toList()) Files.delete(entry);
            }
        }
    }
}
