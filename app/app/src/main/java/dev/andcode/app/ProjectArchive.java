package dev.andcode.app;

import java.io.*;
import java.nio.file.Files;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.*;

/** 不调用外部命令的 ZIP 数据导入/导出;导入目标必须是独立的空暂存目录。 */
public final class ProjectArchive {
    static final long MAX_BYTES = 512L * 1024 * 1024;
    static final int MAX_ENTRIES = 20000;
    private ProjectArchive() {}

    static final class Budget {
        long bytes;
        int entries;
        void entry() throws IOException {
            if (++entries > MAX_ENTRIES) throw new IOException("项目超过 20000 个文件/目录");
        }
        void bytes(int count) throws IOException {
            bytes += count;
            if (bytes > MAX_BYTES) throw new IOException("项目数据超过 512 MiB");
        }
    }

    static void copy(InputStream in, OutputStream out, Budget budget) throws IOException {
        byte[] buffer = new byte[32768];
        int count;
        while ((count = in.read(buffer)) != -1) {
            budget.bytes(count);
            out.write(buffer, 0, count);
        }
    }

    static File child(File root, String path) throws IOException {
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("\\")
                || path.indexOf(':') >= 0 || path.indexOf('\0') >= 0)
            throw new IOException("非法项目路径");
        String clean = path.endsWith("/") ? path.substring(0, path.length() - 1) : path;
        for (String part : clean.split("/", -1)) {
            if (part.isEmpty() || part.equals(".") || part.equals(".."))
                throw new IOException("项目路径包含空段或越界段");
        }
        if (clean.split("/").length > 64) throw new IOException("项目目录过深");
        File target = new File(root, clean);
        if (!target.getCanonicalPath().startsWith(root.getCanonicalPath() + File.separator))
            throw new IOException("项目路径越界");
        return target;
    }

    public static void extract(InputStream source, File target) throws IOException {
        Budget budget = new Budget();
        Set<String> names = new HashSet<>();
        try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(source))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                budget.entry();
                File file = child(target, entry.getName());
                if (!names.add(file.getCanonicalPath())) throw new IOException("ZIP 含重复路径");
                if (entry.isDirectory()) {
                    // 不让 closeEntry() 无限制地排空伪装成目录的压缩数据。
                    if (zip.read() != -1) throw new IOException("ZIP 目录项包含数据");
                    if (!file.isDirectory() && !file.mkdirs()) throw new IOException("无法创建目录");
                } else {
                    File parent = file.getParentFile();
                    if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("无法创建目录");
                    if (!file.createNewFile()) throw new IOException("ZIP 路径冲突");
                    try (OutputStream out = new BufferedOutputStream(new FileOutputStream(file))) {
                        copy(zip, out, budget);
                    }
                }
                zip.closeEntry();
            }
        }
        if (budget.entries == 0) throw new IOException("ZIP 为空或不是有效的 ZIP 文件");
    }

    public static int export(File project, OutputStream target, boolean includeGit) throws IOException {
        Budget budget = new Budget();
        int[] skipped = {0};
        try (ZipOutputStream zip = new ZipOutputStream(new BufferedOutputStream(target))) {
            writeTree(project, project.getName(), zip, includeGit, budget, skipped, 0);
        }
        return skipped[0];
    }

    private static void writeTree(File file, String name, ZipOutputStream zip, boolean includeGit,
                                  Budget budget, int[] skipped, int depth) throws IOException {
        if (Files.isSymbolicLink(file.toPath())) { skipped[0]++; return; }
        if (!includeGit && file.getName().equals(".git")) { skipped[0]++; return; }
        if (depth > 64) throw new IOException("项目目录过深");
        budget.entry();
        if (Files.isDirectory(file.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            zip.putNextEntry(new ZipEntry(name + "/"));
            zip.closeEntry();
            File[] children = file.listFiles();
            if (children == null) throw new IOException("无法读取项目目录");
            for (File child : children)
                writeTree(child, name + "/" + child.getName(), zip, includeGit, budget, skipped, depth + 1);
        } else if (Files.isRegularFile(file.toPath(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            zip.putNextEntry(new ZipEntry(name));
            try (InputStream in = new BufferedInputStream(Files.newInputStream(file.toPath(),
                    java.nio.file.LinkOption.NOFOLLOW_LINKS))) {
                copy(in, zip, budget);
            }
            zip.closeEntry();
        } else {
            skipped[0]++;
        }
    }
}
