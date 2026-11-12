package dev.andcode.app;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import java.util.zip.GZIPOutputStream;

/** Platform JDK test: embedded rootfs installer safety gates (no Android). */
public class RootfsInstallerTest {
    private static final String fileSep = java.io.File.separator;
    private static int checks;

    private static void check(boolean ok) {
        if (!ok) throw new AssertionError("Check " + checks + " failed");
        checks++;
    }

    private static void rejectInstall(Path dir, RuntimePayload.Assets assets) {
        try {
            RootfsInstaller.install(dir, assets, null);
        } catch (IOException expected) {
            checks++;
            return;
        }
        throw new AssertionError("Expected IOException at check " + checks);
    }

    /** Minimal in-memory assets map. */
    private static final class MapAssets implements RuntimePayload.Assets {
        private final Map<String, byte[]> files = new HashMap<>();

        void put(String name, byte[] bytes) {
            files.put(name, bytes);
        }

        @Override public java.io.InputStream open(String name) throws IOException {
            byte[] bytes = files.get(name);
            if (bytes == null) throw new IOException("No asset: " + name);
            return new java.io.ByteArrayInputStream(bytes);
        }
    }

    private static final class Entry {
        final String name;
        final String type;
        final long mode;
        final byte[] data;
        final String link;
        final boolean longName;
        final boolean pax;

        Entry(String name, String type, long mode, byte[] data, String link,
              boolean longName, boolean pax) {
            this.name = name;
            this.type = type;
            this.mode = mode;
            this.data = data;
            this.link = link;
            this.longName = longName;
            this.pax = pax;
        }
    }

    private static Entry file(String name, long mode, String content) {
        return new Entry(name, "0", mode, content.getBytes(StandardCharsets.UTF_8), "", false, false);
    }

    private static Entry dir(String name) {
        return new Entry(name, "5", 0755, new byte[0], "", false, false);
    }

    private static Entry link(String name, String target) {
        return new Entry(name, "2", 0777, new byte[0], target, false, false);
    }

    private static Entry hard(String name, String target) {
        return new Entry(name, "1", 0644, new byte[0], target, false, false);
    }

    /** Minimal ustar writer with GNU long name and pax path support. */
    private static byte[] tar(List<Entry> entries) throws IOException {
        ByteArrayOutputStream tarBytes = new ByteArrayOutputStream();
        for (Entry e : entries) {
            if (e.longName) {
                byte[] nameData = (e.name + "\0").getBytes(StandardCharsets.UTF_8);
                tarBytes.write(header("././@LongLink", 0644, nameData.length, "L", ""));
                tarBytes.write(data(nameData));
                tarBytes.write(header("placeholder", e.mode, e.data.length, e.type, e.link));
            } else if (e.pax) {
                // pax record format: "<total-length> path=<value>\n", where the
                // leading decimal length counts the whole line including itself.
                String content = "path=" + e.name + "\n";
                int total = content.length() + 4;
                while ((String.valueOf(total) + " " + content).length() != total) {
                    total = (String.valueOf(total) + " " + content).length();
                }
                byte[] recordData = (total + " " + content).getBytes(StandardCharsets.UTF_8);
                tarBytes.write(header("PaxHeader", 0, recordData.length, "x", ""));
                tarBytes.write(data(recordData));
                tarBytes.write(header("placeholder", e.mode, e.data.length, e.type, e.link));
            } else {
                if (e.name.length() > 100) throw new IllegalStateException("use longName/pax");
                tarBytes.write(header(e.name, e.mode, e.data.length, e.type, e.link));
            }
            if (e.data.length > 0) tarBytes.write(data(e.data));
        }
        tarBytes.write(new byte[1024]);
        return tarBytes.toByteArray();
    }

    private static byte[] data(byte[] content) {
        int padded = ((content.length + 511) / 512) * 512;
        byte[] blocks = new byte[padded];
        System.arraycopy(content, 0, blocks, 0, content.length);
        return blocks;
    }

    private static byte[] header(String name, long mode, long size, String type, String link) {
        byte[] h = new byte[512];
        put(h, 0, name, 100);
        put(h, 100, String.format("%07o\0", mode), 8);
        put(h, 108, "0000000\0", 8);
        put(h, 116, "0000000\0", 8);
        put(h, 124, String.format("%011o\0", size), 12);
        put(h, 136, "00000000000\0", 12);
        for (int i = 148; i < 156; i++) h[i] = ' ';
        h[156] = (byte) type.charAt(0);
        if (!link.isEmpty()) put(h, 157, link, 100);
        put(h, 257, "ustar\0", 6);
        put(h, 263, "00", 2);
        int sum = 0;
        for (byte b : h) sum += b & 0xff;
        put(h, 148, String.format("%06o\0 ", sum), 8);
        return h;
    }

    private static void put(byte[] h, int off, String value, int len) {
        byte[] raw = value.getBytes(StandardCharsets.UTF_8);
        if (raw.length > len) throw new IllegalStateException("field overflow");
        System.arraycopy(raw, 0, h, off, raw.length);
    }

    private static byte[] gzip(byte[] tar) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try (GZIPOutputStream gz = new GZIPOutputStream(out)) {
            gz.write(tar);
        }
        return out.toByteArray();
    }

    private static String sha256(byte[] bytes) throws Exception {
        return hex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static String hex(byte[] digest) {
        StringBuilder sb = new StringBuilder(64);
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    private static MapAssets assetsFor(byte[] archive) throws Exception {
        MapAssets assets = new MapAssets();
        assets.put(RootfsInstaller.ARCHIVE_ASSET, archive);
        assets.put(RootfsInstaller.SHA_ASSET,
            (sha256(archive) + "  andcode-rootfs-arm64.tgz\n").getBytes(StandardCharsets.UTF_8));
        assets.put("andcode-rootfs/packages.txt",
            "bash\t5.2\tarm64\n".getBytes(StandardCharsets.UTF_8));
        return assets;
    }

    private static List<Entry> sampleTree() {
        List<Entry> entries = new ArrayList<>();
        entries.add(dir("./usr"));
        entries.add(dir("./usr/bin"));
        entries.add(file("./usr/bin/bash", 0755, "#!/bin/sh\nmarker\n"));
        entries.add(file("./etc/os-release", 0644, "PRETTY_NAME=\"Test 24.04\"\n"));
        entries.add(link("./usr/lib", "usr/lib-real"));
        entries.add(dir("./usr/lib-real"));
        entries.add(file("./usr/lib-real/libtest.so", 0644, "lib"));
        return entries;
    }

    private static void deleteRecursively(Path root) throws IOException {
        if (!Files.exists(root)) return;
        try (Stream<Path> stream = Files.walk(root)) {
            stream.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (IOException ignored) {
                    // best effort cleanup
                }
            });
        }
    }

    public static void main(String[] args) throws Exception {
        List<Entry> tree = sampleTree();
        byte[] archive = gzip(tar(tree));
        MapAssets assets = assetsFor(archive);

        // 1. Successful install publishes the instance and the digest marker.
        Path files = Files.createTempDirectory("rootfs-test-ok");
        RootfsInstaller.install(files, assets, null);
        Path rootfs = files.resolve(RootfsInstaller.ROOTFS_DIR);
        check(Files.isRegularFile(rootfs.resolve("usr/bin/bash")));
        check(Files.readString(rootfs.resolve("usr/bin/bash")).contains("marker"));
        check(Files.isSymbolicLink(rootfs.resolve("usr/lib")));
        check(Files.readString(files.resolve(RootfsInstaller.DIGEST_FILE)).trim()
            .equals(sha256(archive)));

        // 2. Matching digest marker skips re-installation.
        Files.writeString(rootfs.resolve("usr/bin/bash"), "corrupted");
        List<String> phases = new ArrayList<>();
        RootfsInstaller.install(files, assets, new RootfsInstaller.Progress() {
            @Override public void onPhase(String phase) {
                phases.add(phase);
            }
            @Override public void onBytes(long extracted) {
            }
        });
        check(phases.size() == 1 && phases.get(0).equals("already-installed"));
        check(Files.readString(rootfs.resolve("usr/bin/bash")).equals("corrupted"));
        deleteRecursively(files);

        // 3. Duplicate file entries are rejected and nothing is published.
        List<Entry> dup = sampleTree();
        dup.add(file("./etc/os-release", 0644, "again"));
        files = Files.createTempDirectory("rootfs-test-dup");
        rejectInstall(files, assetsFor(gzip(tar(dup))));
        check(!Files.exists(files.resolve(RootfsInstaller.ROOTFS_DIR)));
        try (Stream<Path> leftovers = Files.list(files)) {
            check(leftovers.filter(p -> p.getFileName().toString()
                .startsWith("proot-rootfs-stage-")).count() == 0);
        }
        deleteRecursively(files);

        // 4. Path traversal and absolute paths are rejected.
        List<Entry> abs = new ArrayList<>();
        abs.add(file("/etc/escape", 0644, "x"));
        files = Files.createTempDirectory("rootfs-test-abs");
        rejectInstall(files, assetsFor(gzip(tar(abs))));
        deleteRecursively(files);

        List<Entry> dotdot = new ArrayList<>();
        dotdot.add(file("./a/../escape", 0644, "x"));
        files = Files.createTempDirectory("rootfs-test-dotdot");
        rejectInstall(files, assetsFor(gzip(tar(dotdot))));
        deleteRecursively(files);

        // 5. Absolute targets that stay inside the root are legal (Debian
        // alternatives style) and keep their original target text.
        List<Entry> absLink = new ArrayList<>();
        absLink.add(dir("./usr"));
        absLink.add(dir("./usr/bin"));
        absLink.add(file("./usr/bin/bash", 0755, "bash"));
        absLink.add(dir("./etc"));
        absLink.add(file("./usr/bin/mawk", 0755, "mawk"));
        absLink.add(link("./etc/alternatives", "usr/bin"));
        absLink.add(link("./etc/awk", "/usr/bin/mawk"));
        files = Files.createTempDirectory("rootfs-test-abslink");
        RootfsInstaller.install(files, assetsFor(gzip(tar(absLink))), null);
        Path rootfsAbs = files.resolve(RootfsInstaller.ROOTFS_DIR);
        String awkTarget = Files.readSymbolicLink(rootfsAbs.resolve("etc/awk"))
            .toString();
        check(awkTarget.endsWith("usr" + fileSep + "bin" + fileSep + "mawk"));
        deleteRecursively(files);

        List<Entry> relLink = new ArrayList<>();
        relLink.add(link("./usr/escape", "../../../etc"));
        files = Files.createTempDirectory("rootfs-test-rellink");
        rejectInstall(files, assetsFor(gzip(tar(relLink))));
        deleteRecursively(files);

        // 5a-bis. Relative targets resolve against the link directory
        // (Debian font-config pattern: conf.d/x -> ../conf.avail/y).
        List<Entry> relInside = new ArrayList<>();
        relInside.add(dir("./etc"));
        relInside.add(dir("./etc/fonts"));
        relInside.add(dir("./etc/fonts/conf.avail"));
        relInside.add(dir("./etc/fonts/conf.d"));
        relInside.add(file("./etc/fonts/conf.avail/10.conf", 0644, "conf"));
        relInside.add(file("./usr/bin/bash", 0755, "bash"));
        relInside.add(link("./etc/fonts/conf.d/10.conf", "../conf.avail/10.conf"));
        files = Files.createTempDirectory("rootfs-test-relin");
        RootfsInstaller.install(files, assetsFor(gzip(tar(relInside))), null);
        check(Files.isSymbolicLink(files.resolve(RootfsInstaller.ROOTFS_DIR)
            .resolve("etc/fonts/conf.d/10.conf")));
        check(Files.readString(files.resolve(RootfsInstaller.ROOTFS_DIR)
            .resolve("etc/fonts/conf.avail/10.conf")).equals("conf"));
        deleteRecursively(files);

        // 5b. Absolute targets that escape via .. are rejected.
        List<Entry> absDotDot = new ArrayList<>();
        absDotDot.add(link("./usr/escape", "/../etc"));
        files = Files.createTempDirectory("rootfs-test-absdotdot");
        rejectInstall(files, assetsFor(gzip(tar(absDotDot))));
        deleteRecursively(files);

        // 5c. usrmerge dir symlinks write through: bin -> usr/bin then a file
        // created at bin/ls lands in usr/bin/ls, both guest paths valid.
        List<Entry> usrmerge = new ArrayList<>();
        usrmerge.add(dir("./usr"));
        usrmerge.add(dir("./usr/bin"));
        usrmerge.add(file("./usr/bin/bash", 0755, "bash"));
        usrmerge.add(link("./bin", "usr/bin"));
        usrmerge.add(file("./bin/ls", 0755, "ls"));
        files = Files.createTempDirectory("rootfs-test-usrmerge");
        RootfsInstaller.install(files, assetsFor(gzip(tar(usrmerge))), null);
        Path rootfsUm = files.resolve(RootfsInstaller.ROOTFS_DIR);
        check(Files.isSymbolicLink(rootfsUm.resolve("bin")));
        check(Files.readString(rootfsUm.resolve("usr/bin/ls")).equals("ls"));
        deleteRecursively(files);

        // 6. Symlink ancestors are rejected.
        List<Entry> ancestor = new ArrayList<>();
        ancestor.add(dir("./usr"));
        ancestor.add(link("./usr/share", "../../etc"));
        ancestor.add(file("./usr/share/inside", 0644, "x"));
        files = Files.createTempDirectory("rootfs-test-ancestor");
        rejectInstall(files, assetsFor(gzip(tar(ancestor))));
        deleteRecursively(files);

        // 7. setuid/setgid bits are stripped, not applied.
        List<Entry> suid = new ArrayList<>();
        suid.add(dir("./usr"));
        suid.add(dir("./usr/bin"));
        suid.add(file("./usr/bin/bash", 04755, "bash"));
        files = Files.createTempDirectory("rootfs-test-suid");
        RootfsInstaller.install(files, assetsFor(gzip(tar(suid))), null);
        check(Files.isRegularFile(files.resolve(RootfsInstaller.ROOTFS_DIR)
            .resolve("usr/bin/bash")));
        deleteRecursively(files);

        // 8. Special files (fifo/device) are rejected.
        List<Entry> fifo = new ArrayList<>();
        fifo.add(new Entry("./dev/null", "6", 0666, new byte[0], "", false, false));
        files = Files.createTempDirectory("rootfs-test-fifo");
        rejectInstall(files, assetsFor(gzip(tar(fifo))));
        deleteRecursively(files);

        // 9. Hardlinks copy the already-extracted source content.
        List<Entry> hard = new ArrayList<>();
        hard.add(dir("./usr"));
        hard.add(dir("./usr/bin"));
        hard.add(file("./usr/bin/bash", 0755, "bash"));
        hard.add(file("./usr/bin/test", 0755, "entry"));
        hard.add(hard("./usr/bin/[", "./usr/bin/test"));
        files = Files.createTempDirectory("rootfs-test-hard");
        RootfsInstaller.install(files, assetsFor(gzip(tar(hard))), null);
        check(Files.readString(files.resolve(RootfsInstaller.ROOTFS_DIR)
            .resolve("usr/bin/[")).equals("entry"));
        deleteRecursively(files);

        // 10. GNU long names create the full path.
        String longPath = "./usr/share/doc/" + "a".repeat(110);
        List<Entry> longEntries = new ArrayList<>();
        longEntries.add(dir("./usr"));
        longEntries.add(dir("./usr/bin"));
        longEntries.add(file("./usr/bin/bash", 0755, "bash"));
        longEntries.add(dir("./usr/share"));
        longEntries.add(dir("./usr/share/doc"));
        longEntries.add(new Entry(longPath, "0", 0644, "long".getBytes(StandardCharsets.UTF_8),
            "", true, false));
        files = Files.createTempDirectory("rootfs-test-long");
        RootfsInstaller.install(files, assetsFor(gzip(tar(longEntries))), null);
        check(Files.readString(files.resolve(RootfsInstaller.ROOTFS_DIR).resolve(
            longPath.substring(2))).equals("long"));
        deleteRecursively(files);

        // 11. pax path records create the full path.
        String paxPath = "./usr/share/doc/pax-" + "b".repeat(120);
        List<Entry> paxEntries = new ArrayList<>();
        paxEntries.add(dir("./usr"));
        paxEntries.add(dir("./usr/bin"));
        paxEntries.add(file("./usr/bin/bash", 0755, "bash"));
        paxEntries.add(dir("./usr/share"));
        paxEntries.add(dir("./usr/share/doc"));
        paxEntries.add(new Entry(paxPath, "0", 0644,
            "pax".getBytes(StandardCharsets.UTF_8), "", false, true));
        files = Files.createTempDirectory("rootfs-test-pax");
        RootfsInstaller.install(files, assetsFor(gzip(tar(paxEntries))), null);
        check(Files.readString(files.resolve(RootfsInstaller.ROOTFS_DIR).resolve(
            paxPath.substring(2))).equals("pax"));
        deleteRecursively(files);

        // 12. Digest mismatch is rejected and nothing is published.
        byte[] real = gzip(tar(sampleTree()));
        MapAssets tampered = new MapAssets();
        tampered.put(RootfsInstaller.ARCHIVE_ASSET, real);
        tampered.put(RootfsInstaller.SHA_ASSET, ("0".repeat(64) + "  name\n")
            .getBytes(StandardCharsets.UTF_8));
        files = Files.createTempDirectory("rootfs-test-digest");
        rejectInstall(files, tampered);
        check(!Files.exists(files.resolve(RootfsInstaller.ROOTFS_DIR)));
        deleteRecursively(files);

        // 13. An archive without the gate binary is rejected.
        List<Entry> noBash = new ArrayList<>();
        noBash.add(dir("./etc"));
        noBash.add(file("./etc/os-release", 0644, "no bash here"));
        files = Files.createTempDirectory("rootfs-test-nobash");
        rejectInstall(files, assetsFor(gzip(tar(noBash))));
        check(!Files.exists(files.resolve(RootfsInstaller.ROOTFS_DIR)));
        deleteRecursively(files);

        // 14. isInstalled is false without the gate file even with a marker.
        files = Files.createTempDirectory("rootfs-test-gate");
        MapAssets assets2 = assetsFor(archive);
        Files.writeString(files.resolve(RootfsInstaller.DIGEST_FILE), sha256(archive) + "\n");
        check(!RootfsInstaller.isInstalled(files, assets2));
        deleteRecursively(files);

        System.out.println("RootfsInstaller: " + checks + " checks passed");
    }
}
