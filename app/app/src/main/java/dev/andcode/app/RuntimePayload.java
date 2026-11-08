package dev.andcode.app;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashSet;
import java.util.Set;

/** Installs trusted APK data and links only; never extracts executable ELF. */
final class RuntimePayload {
    interface Assets { InputStream open(String name) throws IOException; }
    private static final LinkOption[] NOFOLLOW = {LinkOption.NOFOLLOW_LINKS};

    static boolean present(Path nativeDir) throws IOException {
        if (nativeDir == null) return false;
        if (!Files.isDirectory(nativeDir, NOFOLLOW) || Files.isSymbolicLink(nativeDir))
            throw new IOException("Invalid native payload directory");
        try (java.nio.file.DirectoryStream<Path> entries = Files.newDirectoryStream(nativeDir, "libandcode-*.so")) {
            return entries.iterator().hasNext();
        }
    }

    static synchronized Path prepare(Path files, Path nativeDir, Assets assets) throws IOException {
        if (Files.isSymbolicLink(files) || Files.isSymbolicLink(nativeDir)
                || !Files.isDirectory(nativeDir, NOFOLLOW)) throw new IOException("Invalid payload directories");
        byte[] manifest = read(assets.open("manifest"), 1024 * 1024);
        String identity = digest(manifest, nativeDir.toAbsolutePath().toString());
        Path target = files.resolve("andcode-runtime-" + identity);
        // An existing directory is usable only after the atomic publication below.
        // Validate links again because Android changes nativeLibraryDir on update.
        boolean existing = Files.exists(target, NOFOLLOW);
        if (existing && (Files.isSymbolicLink(target) || !Files.isDirectory(target, NOFOLLOW)))
            throw new IOException("Invalid existing runtime root");
        Path root = existing ? target : Files.createTempDirectory(files, "andcode-runtime-stage-");
        Set<String> logical = new HashSet<>(), physical = new HashSet<>();
        StringBuilder farm = new StringBuilder();
        for (String line : new String(manifest, StandardCharsets.UTF_8).split("\n")) {
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] fields = line.split("\t", -1);
            if (fields.length != 6) throw new IOException("Invalid manifest row");
            String name = fields[0], phys = fields[1], kind = fields[2];
            validatePath(name);
            if (!logical.add(name)) throw new IOException("Duplicate logical path");
            Path dst = root.resolve(name);
            ensureParents(root, dst.getParent(), !existing);
            if (kind.equals("data")) {
                if (!phys.equals("-") || !name.startsWith("etc/")) throw new IOException("Invalid data entry");
                byte[] bytes = read(assets.open(name), 8 * 1024 * 1024);
                if (bytes.length >= 4 && bytes[0] == 127 && bytes[1] == 'E' && bytes[2] == 'L' && bytes[3] == 'F')
                    throw new IOException("ELF forbidden in runtime data");
                if (existing) {
                    if (!Files.isRegularFile(dst, NOFOLLOW) || Files.size(dst) != bytes.length
                            || !java.util.Arrays.equals(read(Files.newInputStream(dst), 8 * 1024 * 1024), bytes))
                        throw new IOException("Runtime data changed");
                } else Files.write(dst, bytes, java.nio.file.StandardOpenOption.CREATE_NEW);
            } else {
                if (!kind.matches("glibc-lib|elf-exec|preload-lib|wrapper-sh|launcher|script|alias")
                        || !phys.matches("libandcode-[a-z0-9-]+\\.so") || phys.length() > 64
                        || !physical.add(phys)) throw new IOException("Invalid native entry");
                Path src = nativeDir.resolve(phys).toAbsolutePath();
                if (!Files.isRegularFile(src, NOFOLLOW)) throw new IOException("Missing native payload: " + phys);
                farm.append(name).append('\t').append(phys).append('\n');
                if (existing) {
                    if (!Files.isSymbolicLink(dst) || !Files.readSymbolicLink(dst).equals(src))
                        throw new IOException("Runtime link changed");
                } else Files.createSymbolicLink(dst, src);
            }
        }
        String declaredFarm = new String(read(assets.open("manifest.farm"), 1024 * 1024), StandardCharsets.UTF_8);
        if (!farm.toString().equals(declaredFarm)) throw new IOException("Manifest/farm disagreement");
        if (!existing && !root.toFile().renameTo(target.toFile())) throw new IOException("Cannot publish runtime");
        // Failures intentionally leave their unique staging directory for diagnosis.
        return target;
    }

    private static void validatePath(String name) throws IOException {
        if (!name.matches("(?:bin|sbin|lib|shim|usr|etc)/[^\\\\:\\s]+") || name.startsWith("/"))
            throw new IOException("Invalid logical path");
        for (String part : name.split("/", -1))
            if (part.isEmpty() || part.equals(".") || part.equals("..")) throw new IOException("Invalid path component");
    }

    private static void ensureParents(Path root, Path parent, boolean create) throws IOException {
        Path current = root;
        for (Path part : root.relativize(parent)) {
            current = current.resolve(part);
            if (!Files.exists(current, NOFOLLOW) && create) Files.createDirectory(current);
            if (!Files.isDirectory(current, NOFOLLOW)) throw new IOException("Invalid runtime parent");
        }
    }

    private static byte[] read(InputStream source, int limit) throws IOException {
        try (InputStream in = source; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = in.read(buffer)) != -1) {
                if (out.size() > limit - count) throw new IOException("Runtime asset too large");
                out.write(buffer, 0, count);
            }
            return out.toByteArray();
        }
    }

    private static String digest(byte[] manifest, String nativePath) throws IOException {
        try {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            hash.update(manifest);
            hash.update((byte) 0);
            byte[] bytes = hash.digest(nativePath.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder();
            for (byte b : bytes) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (NoSuchAlgorithmException error) { throw new IOException(error); }
    }
}
