package dev.andcode.app;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class RuntimePayloadTest {
    private static int checks;
    private static void check(boolean value) { if (!value) throw new AssertionError(); checks++; }
    private static String row(String path, String phys, String kind) {
        return path + "\t" + phys + "\t" + kind + "\tMIT\t1\tfixture\n";
    }
    private static final class Fixture {
        final Path base = Files.createTempDirectory("andcode-runtime-test-");
        final Path files = Files.createDirectory(base.resolve("files"));
        final Path nat = Files.createDirectory(base.resolve("native"));
        final Map<String, byte[]> data = new HashMap<>();
        Fixture() throws IOException {
            Files.write(nat.resolve("libandcode-bash.so"), new byte[]{127, 'E', 'L', 'F'});
            text("manifest", row("bin/bash.bin", "libandcode-bash.so", "elf-exec") + row("etc/cert", "-", "data"));
            text("manifest.farm", "bin/bash.bin\tlibandcode-bash.so\n");
            text("etc/cert", "trusted data");
        }
        void text(String key, String text) { data.put(key, text.getBytes(StandardCharsets.UTF_8)); }
        Path prepare() throws IOException {
            return RuntimePayload.prepare(files, nat, name -> {
                byte[] bytes = data.get(name);
                if (bytes == null) throw new IOException("Missing asset");
                return new ByteArrayInputStream(bytes);
            });
        }
        void rejects() throws IOException {
            try { prepare(); throw new AssertionError("Accepted invalid payload"); }
            catch (IOException expected) { checks++; }
        }
    }
    public static void main(String[] args) throws Exception {
        if (args.length == 2) {
            Path assets = Path.of(args[1]);
            Path files = Files.createTempDirectory("andcode-real-runtime-");
            Path root = RuntimePayload.prepare(files, Path.of(args[0]), name -> Files.newInputStream(assets.resolve(name)));
            check(Files.isSymbolicLink(root.resolve("bin/bash.bin")));
            check(RuntimePayload.prepare(files, Path.of(args[0]), name -> Files.newInputStream(assets.resolve(name))).equals(root));
            System.out.println("Real CI manifest prepared and revalidated: " + root);
            return;
        }
        Fixture f = new Fixture();
        Path root = f.prepare();
        check(Files.isSymbolicLink(root.resolve("bin/bash.bin")));
        check(Files.readSymbolicLink(root.resolve("bin/bash.bin")).equals(f.nat.resolve("libandcode-bash.so")));
        check(Files.readString(root.resolve("etc/cert")).equals("trusted data"));
        check(f.prepare().equals(root));
        Files.writeString(root.resolve("etc/cert"), "changed");
        f.rejects();
        f = new Fixture(); root = f.prepare();
        Files.delete(root.resolve("bin/bash.bin"));
        Files.createSymbolicLink(root.resolve("bin/bash.bin"), Path.of("/untrusted"));
        f.rejects();
        for (String path : new String[]{"../escape", "/etc/cert", "etc/../escape", "etc//cert", "etc/./cert", "etc/a:b", "etc/a\\b"}) {
            f = new Fixture(); f.text("manifest", row(path, "-", "data")); f.rejects();
        }
        f = new Fixture(); f.data.put("etc/cert", new byte[]{127, 'E', 'L', 'F'}); f.rejects();
        f = new Fixture(); f.text("manifest.farm", "wrong\n"); f.rejects();
        f = new Fixture(); Files.delete(f.nat.resolve("libandcode-bash.so")); f.rejects();
        f = new Fixture(); Files.delete(f.nat.resolve("libandcode-bash.so"));
        Files.createSymbolicLink(f.nat.resolve("libandcode-bash.so"), Path.of("/etc/passwd")); f.rejects();
        f = new Fixture(); f.text("manifest", row("bin/bash.bin", "libandcode-bash.so", "elf-exec")
            + row("bin/other", "libandcode-bash.so", "elf-exec")); f.rejects();
        f = new Fixture(); f.text("manifest", row("bin/bash.bin", "libandcode-bash.so", "elf-exec")
            + row("bin/bash.bin", "libandcode-bash.so", "elf-exec")); f.rejects();
        f = new Fixture(); f.text("manifest", row("bin/cert", "-", "data")); f.rejects();
        f = new Fixture(); root = f.prepare();
        Files.delete(root.resolve("etc/cert")); Files.delete(root.resolve("etc"));
        Files.createSymbolicLink(root.resolve("etc"), f.base); f.rejects();
        System.out.println("RuntimePayload: " + checks + " checks passed");
    }
}
