package dev.andcode.app;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** No third-party dependencies; run javac/java in a temporary directory without repository build artifacts. */
public class ProjectArchiveTest {
    static int checks;
    interface Checked { void run() throws Exception; }
    static void reject(Checked action) throws Exception {
        try { action.run(); } catch (IOException expected) { checks++; return; }
        throw new AssertionError("Expected IOException");
    }
    static void check(boolean value) {
        if (!value) throw new AssertionError("Check failed");
        checks++;
    }
    static byte[] zip(String name, String value) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(out)) {
            zip.putNextEntry(new ZipEntry(name));
            zip.write(value.getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
        }
        return out.toByteArray();
    }
    public static void main(String[] args) throws Exception {
        Path temp = Files.createTempDirectory("andcode-archive-test-");
        try {
            File root = Files.createDirectory(temp.resolve("project")).toFile();
            ProjectArchive.extract(new ByteArrayInputStream(zip("src/中文.txt", "hello")), root);
            check(Files.readString(root.toPath().resolve("src/中文.txt")).equals("hello"));
            for (String name : List.of("../escape", "/absolute", "a/../../escape", "C:/escape",
                    "a\\escape", "a//escape", "./escape", "a/../escape")) {
                reject(() -> ProjectArchive.extract(new ByteArrayInputStream(zip(name, "bad")), root));
            }
            reject(() -> ProjectArchive.extract(new ByteArrayInputStream(new byte[]{1, 2, 3}), root));
            reject(() -> ProjectArchive.extract(new ByteArrayInputStream(zip("fake-directory/", "not-directory-data")), root));
            reject(() -> ProjectArchive.extract(new ByteArrayInputStream(zip("src/中文.txt", "overwrite")), root));
            ProjectArchive.Budget budget = new ProjectArchive.Budget();
            budget.bytes = ProjectArchive.MAX_BYTES;
            reject(() -> budget.bytes(1));
            budget.entries = ProjectArchive.MAX_ENTRIES;
            reject(budget::entry);
            Files.createDirectory(root.toPath().resolve(".git"));
            Files.writeString(root.toPath().resolve(".git/config"), "git-config");
            Files.createDirectory(root.toPath().resolve("empty"));
            for (boolean git : List.of(false, true)) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                ProjectArchive.export(root, out, git);
                File roundtrip = Files.createDirectory(temp.resolve(git ? "with-git" : "without-git")).toFile();
                ProjectArchive.extract(new ByteArrayInputStream(out.toByteArray()), roundtrip);
                check(Files.readString(roundtrip.toPath().resolve("project/src/中文.txt")).equals("hello"));
                check(Files.isDirectory(roundtrip.toPath().resolve("project/empty")));
                check(Files.exists(roundtrip.toPath().resolve("project/.git/config")) == git);
            }
            boolean canSymlink = false;
            try { Files.createSymbolicLink(root.toPath().resolve("outside-link"), temp); canSymlink = true; }
            catch (IOException | UnsupportedOperationException ignored) {}
            if (canSymlink) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                check(ProjectArchive.export(root, out, true) == 1);
            } else System.out.println("SKIP symlink test: host does not permit symlink creation");
            check(!Files.exists(temp.resolve("escape")));
            System.out.println("PASS ProjectArchive: " + checks + " checks");
        } finally {
            try (java.util.stream.Stream<Path> paths = Files.walk(temp)) {
                for (Path path : paths.sorted(Comparator.reverseOrder()).toArray(Path[]::new)) Files.deleteIfExists(path);
            }
        }
    }
}
