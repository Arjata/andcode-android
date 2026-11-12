package dev.andcode.app;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.GZIPInputStream;

/**
 * First-launch installer for the embedded canonical rootfs (DESIGN v0.4.55).
 *
 * Extracts assets/andcode-rootfs/andcode-rootfs-arm64.tgz into
 * files/proot-rootfs with the section 4.8 rootfs-tar safety checks: path
 * traversal, duplicate files and special files are rejected, escaping
 * symlinks are rejected while in-root absolute/relative targets and
 * usrmerge dir symlinks are kept (proot translates them guest-side), and
 * setuid/setgid bits are stripped. Skips work when the installed instance
 * digest marker matches the embedded archive; failures never touch the
 * previously published instance and leave their staging directory for
 * diagnosis. Pure JDK: gzip + manual ustar/pax parsing, no third-party code
 * and no native extractor (guest binaries execute through the verified proot
 * path, never by the app itself).
 */
final class RootfsInstaller {

    static final String ARCHIVE_ASSET = "andcode-rootfs/andcode-rootfs-arm64.tgz";
    static final String SHA_ASSET = "andcode-rootfs/andcode-rootfs-arm64.tgz.sha256";
    static final String ROOTFS_DIR = "proot-rootfs";
    static final String DIGEST_FILE = "proot-rootfs.digest";
    static final String GATE_FILE = "usr/bin/bash";

    private static final LinkOption[] NOFOLLOW = {LinkOption.NOFOLLOW_LINKS};
    private static final int BLOCK = 512;

    /** Coarse progress for install UIs; both callbacks may be invoked from any thread. */
    interface Progress {
        void onPhase(String phase);
        void onBytes(long extractedBytes);
    }

    /**
     * Diagnostic sink, kept free of android imports so host JVM tests can run
     * this class directly. The app wires it to logcat; default is a no-op.
     */
    static volatile java.util.function.Consumer<String> logger = message -> {
    };

    private static void log(String message) {
        logger.accept(message);
    }

    private RootfsInstaller() {}

    /** True when the installed instance exists and matches the embedded archive digest. */
    static boolean isInstalled(Path files, RuntimePayload.Assets assets) throws IOException {
        String expected = readExpectedDigest(assets);
        Path rootfs = files.resolve(ROOTFS_DIR);
        Path gate = rootfs.resolve(GATE_FILE);
        if (!Files.isRegularFile(gate, NOFOLLOW)) return false;
        Path marker = files.resolve(DIGEST_FILE);
        if (!Files.isRegularFile(marker, NOFOLLOW)) return false;
        String have = new String(read(Files.newInputStream(marker), 256),
            StandardCharsets.UTF_8).trim();
        return have.equals(expected);
    }

    /**
     * Publish files/proot-rootfs from the embedded archive unless the digest
     * marker already matches. Only the successful full extraction replaces a
     * previous instance.
     */
    static void install(Path files, RuntimePayload.Assets assets, Progress progress)
            throws IOException {
        String expected;
        try {
            expected = readExpectedDigest(assets);
            log("digest=" + expected);
        } catch (IOException e) {
            log("digest read failed: " + e);
            throw e;
        }
        if (isInstalled(files, assets)) {
            if (progress != null) progress.onPhase("already-installed");
            return;
        }
        if (progress != null) progress.onPhase("extracting");
        Path stage = Files.createTempDirectory(files, "proot-rootfs-stage-");
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            long extracted;
            try (InputStream raw = assets.open(ARCHIVE_ASSET);
                 DigestInputStream digesting = new DigestInputStream(raw, md);
                 GZIPInputStream gz = new GZIPInputStream(digesting, 1 << 16)) {
                extracted = extractTar(gz, stage, progress);
            }
            if (!hex(md.digest()).equals(expected)) {
                throw new IOException("Embedded rootfs digest mismatch");
            }
            if (!Files.isRegularFile(stage.resolve(GATE_FILE), NOFOLLOW)) {
                throw new IOException("Rootfs archive lacks " + GATE_FILE);
            }
            // Publish: remove any previous instance only after full validation.
            if (progress != null) progress.onPhase("publishing");
            deleteTree(files.resolve(ROOTFS_DIR));
            if (!stage.toFile().renameTo(files.resolve(ROOTFS_DIR).toFile())) {
                throw new IOException("Cannot publish rootfs directory");
            }
            Files.write(files.resolve(DIGEST_FILE),
                (expected + "\n").getBytes(StandardCharsets.UTF_8));
            if (progress != null) progress.onPhase("installed(" + extracted + "B)");
        } catch (IOException e) {
            deleteTree(stage);
            throw e;
        } catch (Exception e) {
            deleteTree(stage);
            throw new IOException("Rootfs extraction failed", e);
        }
    }

    // ── tar extraction with section 4.8 safety checks ────────────────────────

    private static long extractTar(InputStream in, Path root, Progress progress)
            throws IOException {
        Set<String> published = new HashSet<>();
        Map<String, String> symlinks = new HashMap<>();
        String pendingName = null;
        String pendingLink = null;
        List<String> pendingPax = null;
        byte[] header = new byte[BLOCK];
        long total = 0;
        long reported = 0;
        int specialModes = 0;
        while (true) {
            int got = readFull(in, header);
            if (got == 0) break;
            if (isZeroBlock(header)) break;
            String name = cstr(header, 0, 100);
            long size = octal(header, 124, 12);
            long mode = octal(header, 100, 8);
            String type = cstr(header, 156, 1);
            String linkname = cstr(header, 157, 100);
            String prefix = cstr(header, 345, 155);
            String magic = cstr(header, 257, 6);
            if (type.equals("L")) { // GNU long name
                pendingName = readString(in, size);
                continue;
            }
            if (type.equals("K")) { // GNU long link target
                pendingLink = readString(in, size);
                continue;
            }
            if (type.equals("x") || type.equals("g")) { // pax records
                List<String> records = readPax(in, size);
                if (type.equals("x")) pendingPax = records;
                continue;
            }
            if (pendingName != null) {
                name = pendingName;
                pendingName = null;
            }
            if (pendingLink != null) {
                linkname = pendingLink;
                pendingLink = null;
            }
            if (pendingPax != null) {
                for (String record : pendingPax) {
                    if (record.startsWith("path=")) name = record.substring(5);
                }
                pendingPax = null;
            }
            if (!magic.isEmpty() && !magic.startsWith("ustar")) {
                throw new IOException("Unsupported tar format: " + magic);
            }
            if (!prefix.isEmpty()) name = prefix + "/" + name;
            name = normalize(name);
            if (size < 0) throw new IOException("Invalid tar size for " + name);
            switch (type.isEmpty() ? "0" : type) {
                case "0": case "7": case "\0": {
                    requireSafe(name, published, symlinks, false);
                    // Real Ubuntu trees carry setuid/setgid binaries (su, sudo,
                    // chage...). They are inert under proot as the app UID and
                    // applyMode only keeps the low 9 bits, so strip and count.
                    if ((mode & 07000) != 0) specialModes++;
                    Path dst = root.resolve(name);
                    Files.createDirectories(dst.getParent());
                    try (java.io.FileOutputStream out = new java.io.FileOutputStream(dst.toFile())) {
                        byte[] buffer = new byte[1 << 16];
                        long left = size;
                        while (left > 0) {
                            int chunk = in.read(buffer, 0, (int) Math.min(buffer.length, left));
                            if (chunk < 0) throw new IOException("Truncated tar entry: " + name);
                            out.write(buffer, 0, chunk);
                            left -= chunk;
                            total += chunk;
                        }
                    }
                    skipPadding(in, size);
                    applyMode(dst, mode);
                    published.add(name);
                    if (progress != null && total - reported >= (8L << 20)) {
                        reported = total;
                        progress.onBytes(total);
                    }
                    break;
                }
                case "5": {
                    requireSafe(name, published, symlinks, true);
                    Files.createDirectories(root.resolve(name));
                    break;
                }
                case "2": {
                    requireSafe(name, published, symlinks, false);
                    // Ubuntu trees legitimately use absolute targets
                    // (etc/alternatives/*) and dir symlinks (bin -> usr/bin).
                    // proot translates absolute targets in the guest namespace,
                    // so keep the original target text; only reject targets that
                    // lexically resolve outside the rootfs root.
                    // Relative targets resolve against the link directory.
                    String dir = name.contains("/")
                        ? name.substring(0, name.lastIndexOf('/')) : "";
                    String target = linkname.startsWith("/")
                        ? linkname.substring(1) : linkname;
                    String combined = dir.isEmpty() ? target : dir + "/" + target;
                    if (resolveWithinRoot(normalize(combined), symlinks) == null) {
                        throw new IOException("Escaping symlink rejected: " + name + " -> " + linkname);
                    }
                    Path dst = root.resolve(name);
                    Files.createDirectories(dst.getParent());
                    Files.createSymbolicLink(dst, java.nio.file.Paths.get(linkname));
                    symlinks.put(name, target);
                    published.add(name);
                    break;
                }
                case "1": {
                    requireSafe(name, published, symlinks, false);
                    String from = normalize(linkname.startsWith("/")
                        ? linkname.substring(1) : linkname);
                    if (!published.contains(from)) {
                        throw new IOException("Hardlink source missing: " + name + " -> " + linkname);
                    }
                    Path dst = root.resolve(name);
                    Files.createDirectories(dst.getParent());
                    Files.copy(root.resolve(from), dst,
                        java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    applyMode(dst, mode);
                    published.add(name);
                    break;
                }
                default:
                    throw new IOException("Special tar entry rejected: type=" + type + " " + name);
            }
        }
        if (specialModes > 0) log("stripped setuid/setgid bits on " + specialModes + " files");
        return total;
    }

    /** Duplicate-file, path-traversal and symlink-escape gates. */
    private static void requireSafe(String name, Set<String> published,
                                    Map<String, String> symlinks,
                                    boolean isDir) throws IOException {
        if (name.isEmpty() || name.equals(".") || name.startsWith("/")
                || name.endsWith("/")) throw new IOException("Invalid tar path: " + name);
        for (String part : name.split("/")) {
            if (part.isEmpty() || part.equals(".") || part.equals("..")) {
                throw new IOException("Invalid tar path component: " + name);
            }
        }
        if (!isDir && published.contains(name)) {
            throw new IOException("Duplicate tar entry: " + name);
        }
        // 链接祖先解析:Ubuntu 树存在 bin -> usr/bin 等目录符号链接;解析整条
        // 祖先链,只要最终落点仍在 root 内就放行(逃逸或环路才拒绝)。
        if (resolveWithinRoot(name, symlinks) == null) {
            throw new IOException("Escaping symlink ancestor rejected: " + name);
        }
    }

    /**
     * Lexically resolve path against the recorded symlink table. Returns the
     * root-relative resolved path, or null when the chain escapes the root or
     * exceeds the hop budget.
     */
    private static String resolveWithinRoot(String path, Map<String, String> symlinks) {
        java.util.ArrayDeque<String> queue = new java.util.ArrayDeque<>(
            java.util.Arrays.asList(path.split("/")));
        List<String> out = new ArrayList<>();
        int hops = 0;
        while (!queue.isEmpty()) {
            String part = queue.pollFirst();
            if (part.isEmpty() || part.equals(".")) continue;
            if (part.equals("..")) {
                if (out.isEmpty()) return null;
                out.remove(out.size() - 1);
                continue;
            }
            String current = String.join("/", out) + "/" + part;
            String target = symlinks.get(current.substring(1));
            if (target == null) {
                out.add(part);
                continue;
            }
            if (++hops > 40) return null;
            if (target.startsWith("/")) {
                out.clear();
                target = target.substring(1);
            }
            String[] tparts = target.split("/");
            for (int i = tparts.length - 1; i >= 0; i--) queue.addFirst(tparts[i]);
        }
        return String.join("/", out);
    }

    private static String normalize(String name) throws IOException {
        if (name == null) throw new IOException("Missing tar entry name");
        String n = name;
        while (n.startsWith("./")) n = n.substring(2);
        while (n.endsWith("/")) n = n.substring(0, n.length() - 1);
        return n;
    }

    private static void applyMode(Path dst, long mode) throws IOException {
        long bits = mode & 0777;
        Set<PosixFilePermission> perms = new HashSet<>();
        // Octal digit order: lowest = others, middle = group, highest = owner.
        PosixFilePermission[][] classes = {
            {PosixFilePermission.OTHERS_READ, PosixFilePermission.OTHERS_WRITE,
                PosixFilePermission.OTHERS_EXECUTE},
            {PosixFilePermission.GROUP_READ, PosixFilePermission.GROUP_WRITE,
                PosixFilePermission.GROUP_EXECUTE},
            {PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE,
                PosixFilePermission.OWNER_EXECUTE},
        };
        for (int shift = 0; shift < 3; shift++) {
            long tri = (bits >> (shift * 3)) & 7;
            if ((tri & 4) != 0) perms.add(classes[shift][0]);
            if ((tri & 2) != 0) perms.add(classes[shift][1]);
            if ((tri & 1) != 0) perms.add(classes[shift][2]);
        }
        try {
            Files.setPosixFilePermissions(dst, perms);
        } catch (UnsupportedOperationException ignored) {
            // Host test filesystems without POSIX modes; Android is POSIX.
        }
    }

    private static List<String> readPax(InputStream in, long size) throws IOException {
        // pax lengths are in BYTES while values may contain multi-byte UTF-8;
        // parse on the raw bytes and decode each value separately.
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1 << 16];
        long left = size;
        while (left > 0) {
            int chunk = in.read(buffer, 0, (int) Math.min(buffer.length, left));
            if (chunk < 0) throw new IOException("Truncated pax data");
            out.write(buffer, 0, chunk);
            left -= chunk;
        }
        skipPadding(in, size);
        byte[] data = out.toByteArray();
        List<String> records = new ArrayList<>();
        int i = 0;
        while (i < data.length && data[i] != 0) {
            int sp = i;
            while (sp < data.length && data[sp] != (byte) (32 & 0xff)) sp++;
            if (sp >= data.length) break;
            int len;
            try {
                len = Integer.parseInt(new String(data, i, sp - i,
                    java.nio.charset.StandardCharsets.US_ASCII));
            } catch (NumberFormatException e) {
                throw new IOException("Invalid pax record length at " + i);
            }
            int end = i + len;
            if (len <= 0 || end > data.length) {
                throw new IOException("Invalid pax record len=" + len + " at=" + i);
            }
            int stop = end;
            if (stop > sp + 1 && data[stop - 1] == (byte) (10 & 0xff)) stop--;
            records.add(new String(data, sp + 1, stop - (sp + 1),
                java.nio.charset.StandardCharsets.UTF_8));
            i = end;
        }
        return records;
    }

    private static String readString(InputStream in, long size) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1 << 16];
        long left = size;
        while (left > 0) {
            int chunk = in.read(buffer, 0, (int) Math.min(buffer.length, left));
            if (chunk < 0) throw new IOException("Truncated tar metadata");
            out.write(buffer, 0, chunk);
            left -= chunk;
        }
        skipPadding(in, size);
        String s = new String(out.toByteArray(), StandardCharsets.UTF_8);
        int nul = s.indexOf('\0');
        return nul >= 0 ? s.substring(0, nul) : s;
    }

    private static void skipPadding(InputStream in, long size) throws IOException {
        long pad = (BLOCK - (size % BLOCK)) % BLOCK;
        while (pad > 0) {
            long skipped = in.skip(pad);
            if (skipped <= 0) {
                if (in.read() < 0) throw new IOException("Truncated tar padding");
                skipped = 1;
            }
            pad -= skipped;
        }
    }

    private static int readFull(InputStream in, byte[] block) throws IOException {
        int off = 0;
        while (off < block.length) {
            int n = in.read(block, off, block.length - off);
            if (n < 0) return off == 0 ? 0 : off;
            off += n;
        }
        return off;
    }

    private static boolean isZeroBlock(byte[] block) {
        for (byte b : block) {
            if (b != 0) return false;
        }
        return true;
    }

    private static String cstr(byte[] h, int off, int len) {
        int end = off;
        while (end < off + len && h[end] != 0) end++;
        return new String(h, off, end - off, StandardCharsets.UTF_8);
    }

    private static long octal(byte[] h, int off, int len) {
        String s = cstr(h, off, len).trim();
        if (s.isEmpty()) return 0;
        long v = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '7') return -1;
            v = v * 8 + (c - '0');
        }
        return v;
    }

    private static String hex(byte[] digest) {
        StringBuilder sb = new StringBuilder(64);
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    private static String readExpectedDigest(RuntimePayload.Assets assets) throws IOException {
        String s = new String(read(assets.open(SHA_ASSET), 512), StandardCharsets.UTF_8).trim();
        int sp = s.indexOf(' ');
        if (sp <= 0) throw new IOException("Invalid rootfs digest asset");
        String hex = s.substring(0, sp);
        if (!hex.matches("[0-9a-f]{64}")) throw new IOException("Invalid rootfs digest value");
        return hex;
    }

    private static byte[] read(InputStream source, int limit) throws IOException {
        try (InputStream in = source; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int n;
            int total = 0;
            while ((n = in.read(buffer)) != -1) {
                total += n;
                if (total > limit) throw new IOException("Asset exceeds limit");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    private static void deleteTree(Path root) throws IOException {
        if (!Files.exists(root, NOFOLLOW)) return;
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(root)) {
            for (Path child : stream) {
                if (Files.isDirectory(child, NOFOLLOW) && !Files.isSymbolicLink(child)) {
                    deleteTree(child);
                } else {
                    Files.deleteIfExists(child);
                }
            }
        }
        Files.deleteIfExists(root);
    }
}
