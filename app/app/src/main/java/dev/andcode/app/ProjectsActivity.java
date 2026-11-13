package dev.andcode.app;

import android.app.Application;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.view.View;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.widget.*;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.widget.PopupMenu;
import androidx.lifecycle.*;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import com.google.android.material.textfield.TextInputLayout;
import com.google.android.material.textfield.TextInputEditText;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.Executors;

/** SAF file exchange; import copies only, without modifying source files selected in the system picker. */
public class ProjectsActivity extends UtilityActivity {
    private String pendingName;
    private String pendingExport;
    private TextView status;
    private LinearLayout list;
    private JobState jobs;
    private final List<Button> importButtons = new ArrayList<>();
    private LinearLayout statusCard;
    private LinearProgressIndicator progress;
    private TextView countLabel;

    private final ActivityResultLauncher<String[]> zipPicker = registerForActivityResult(
        new ActivityResultContracts.OpenDocument(), uri -> { if (uri != null) importProject(uri, false); });
    private final ActivityResultLauncher<Uri> folderPicker = registerForActivityResult(
        new ActivityResultContracts.OpenDocumentTree(), uri -> { if (uri != null) importProject(uri, true); });
    private final ActivityResultLauncher<String> exportPicker = registerForActivityResult(
        new ActivityResultContracts.CreateDocument("application/zip"), uri -> {
            if (uri == null || pendingExport == null) return;
            Application app = getApplication();
            File project = new File(AppSettings.projectsDir(app), pendingExport);
            boolean git = AppSettings.includeGit(app);
            jobs.run(() -> {
                if (!project.isDirectory() || Files.isSymbolicLink(project.toPath()))
                    throw new IOException("项目不存在");
                try (OutputStream out = app.getContentResolver().openOutputStream(uri, "wt")) {
                    if (out == null) throw new IOException("无法写入所选文件");
                    int skipped = ProjectArchive.export(project, out, git);
                    return "已导出 " + project.getName() + "（跳过 " + skipped + " 个 .git / 链接 / 特殊文件）";
                } catch (Exception e) {
                    try { DocumentsContract.deleteDocument(app.getContentResolver(), uri); }
                    catch (Exception ignored) {}
                    throw e;
                }
            });
        });

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) {
            pendingName = state.getString("name");
            pendingExport = state.getString("export");
        }
        jobs = new ViewModelProvider(this).get(JobState.class);
        pageTitle("项目", "把代码带进来，随时继续创造");
        LinearLayout imports = card(body, false);
        imports.addView(label("导入到工作区", 18, true, false));
        gap(imports, 6);
        imports.addView(label("保留源文件，只在应用中创建独立副本", 13, false, true));
        gap(imports, 16);
        LinearLayout actions = row();
        MaterialButton zip = action("导入 ZIP", true, () -> askName(false));
        MaterialButton folder = action("选择文件夹", false, () -> askName(true));
        LinearLayout.LayoutParams left = new LinearLayout.LayoutParams(0, -2, 1);
        left.setMarginEnd(dp(8));
        actions.addView(zip, left);
        actions.addView(folder, new LinearLayout.LayoutParams(0, -2, 1));
        importButtons.add(zip);
        importButtons.add(folder);
        imports.addView(actions);
        gap(imports, 10);
        imports.addView(label("最多 512 MiB · 20,000 项 · 不覆盖同名项目", 11, false, true));

        statusCard = card(body, false);
        status = label("", 13, false, true);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        statusCard.addView(status);
        progress = new LinearProgressIndicator(this);
        progress.setIndeterminate(true);
        gap(statusCard, 10);
        statusCard.addView(progress, new LinearLayout.LayoutParams(-1, dp(4)));
        countLabel = section("我的项目", "");
        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        body.addView(list);
        jobs.message.observe(this, message -> {
            status.setText(message);
            ((View) statusCard.getParent()).setVisibility("就绪".equals(message) ? View.GONE : View.VISIBLE);
            progress.setVisibility(jobs.busy ? View.VISIBLE : View.GONE);
            status.setTextColor(color(message.startsWith("操作失败")
                ? androidx.appcompat.R.attr.colorError
                : com.google.android.material.R.attr.colorOnSurfaceVariant));
            for (Button button : importButtons) button.setEnabled(!jobs.busy);
            renderProjects();
        });
        renderProjects();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("name", pendingName);
        state.putString("export", pendingExport);
        super.onSaveInstanceState(state);
    }

    @Override protected void onResume() {
        super.onResume();
        renderProjects();
    }

    private void askName(boolean folder) {
        LinearLayout content = column();
        content.setPadding(dp(24), dp(8), dp(24), 0);
        TextInputLayout field = new TextInputLayout(this);
        field.setHint("项目名称");
        field.setHelperText("支持中文、字母、数字和 . _ -，最多 64 字符");
        TextInputEditText name = new TextInputEditText(field.getContext());
        name.setSingleLine(true);
        name.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        field.addView(name);
        content.addView(field);
        AlertDialog dialog = new MaterialAlertDialogBuilder(this).setTitle("导入" + (folder ? "文件夹" : " ZIP"))
            .setView(content).setNegativeButton("取消", null).setPositiveButton("下一步", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String value = name.getText().toString().trim();
            if (!value.matches("[\\p{L}\\p{N}][\\p{L}\\p{N}._-]{0,63}")
                    || new File(AppSettings.projectsDir(this), value).exists()) {
                field.setError("请输入有效且不重复的项目名");
                return;
            }
            pendingName = value;
            dialog.dismiss();
            if (folder) folderPicker.launch(null);
            else zipPicker.launch(new String[]{"application/zip", "application/x-zip-compressed", "application/octet-stream"});
        }));
        dialog.show();
    }

    private void importProject(Uri uri, boolean folder) {
        if (pendingName == null) return;
        String name = pendingName;
        Application app = getApplication();
        jobs.run(() -> {
            File root = AppSettings.projectsDir(app);
            if (!root.isDirectory() && !root.mkdirs()) throw new IOException("无法创建项目目录");
            File destination = ProjectArchive.child(root, name);
            File staging = Files.createTempDirectory(app.getFilesDir().toPath(), "import-").toFile();
            try {
                if (folder) {
                    Uri source = DocumentsContract.buildDocumentUriUsingTree(uri, DocumentsContract.getTreeDocumentId(uri));
                    copyFolder(app, uri, source, staging, new ProjectArchive.Budget(), 0);
                } else {
                    try (InputStream in = app.getContentResolver().openInputStream(uri)) {
                        if (in == null) throw new IOException("无法读取 ZIP");
                        ProjectArchive.extract(in, staging);
                    }
                }
                if (destination.exists()) throw new IOException("项目已存在，未覆盖");
                Files.move(staging.toPath(), destination.toPath());
                return "已导入 " + name + "。可复制路径在 Web 中打开，或设为新终端目录。";
            } finally {
                // Clean up only this task's staging directory, without following symbolic links.
                if (staging.exists()) {
                    try (java.util.stream.Stream<Path> paths = Files.walk(staging.toPath())) {
                        for (Path path : paths.sorted(Comparator.reverseOrder()).toArray(Path[]::new))
                            Files.deleteIfExists(path);
                    }
                }
            }
        });
    }

    private static void copyFolder(Context context, Uri tree, Uri source, File target,
                                   ProjectArchive.Budget budget, int depth) throws IOException {
        if (depth > 64) throw new IOException("项目目录过深");
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getDocumentId(source));
        String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor cursor = context.getContentResolver().query(children, columns, null, null, null)) {
            if (cursor == null) throw new IOException("无法读取文件夹");
            while (cursor.moveToNext()) {
                budget.entry();
                String name = cursor.getString(1);
                if (name == null || name.contains("/")) throw new IOException("非法文件名");
                File file = ProjectArchive.child(target, name);
                Uri child = DocumentsContract.buildDocumentUriUsingTree(tree, cursor.getString(0));
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2))) {
                    if (!file.mkdir()) throw new IOException("文件夹重名或无法创建");
                    copyFolder(context, tree, child, file, budget, depth + 1);
                } else {
                    if (!file.createNewFile()) throw new IOException("文件重名或无法创建");
                    try (InputStream in = context.getContentResolver().openInputStream(child);
                         OutputStream out = new BufferedOutputStream(new FileOutputStream(file))) {
                        if (in == null) throw new IOException("无法读取文件");
                        ProjectArchive.copy(in, out, budget);
                    }
                }
            }
        }
    }

    private void renderProjects() {
        list.removeAllViews();
        File[] projects = AppSettings.projectsDir(this).listFiles(file ->
            file.isDirectory() && !Files.isSymbolicLink(file.toPath()));
        countLabel.setText((projects == null ? 0 : projects.length) + " 个项目");
        if (projects == null || projects.length == 0) {
            LinearLayout empty = card(list, false);
            empty.setGravity(android.view.Gravity.CENTER);
            empty.setPadding(dp(24), dp(32), dp(24), dp(32));
            ImageView icon = new ImageView(this);
            icon.setImageResource(R.drawable.ic_nav_terminal);
            icon.setColorFilter(color(androidx.appcompat.R.attr.colorPrimary));
            empty.addView(icon, new LinearLayout.LayoutParams(dp(32), dp(32)));
            gap(empty, 16);
            empty.addView(label("从第一个项目开始", 16, true, false));
            gap(empty, 8);
            TextView hint = label("导入 ZIP 或文件夹，\n在终端与 Web 中继续工作。", 13, false, true);
            hint.setGravity(android.view.Gravity.CENTER);
            empty.addView(hint);
            return;
        }
        Arrays.sort(projects, Comparator.comparing(File::getName));
        File selected = AppSettings.selectedProject(this);
        for (File project : projects) {
            LinearLayout card = card(list, false);
            LinearLayout header = row();
            LinearLayout identity = column();
            TextView title = label(project.getName(), 18, true, false);
            title.setMaxLines(2);
            title.setEllipsize(TextUtils.TruncateAt.END);
            identity.addView(title);
            gap(identity, 6);
            if (project.equals(selected)) identity.addView(badge("新终端默认项目"),
                new LinearLayout.LayoutParams(-2, -2));
            else identity.addView(label("本地工作区", 12, false, true));
            header.addView(identity, new LinearLayout.LayoutParams(0, -2, 1));
            androidx.appcompat.widget.AppCompatImageButton more = new androidx.appcompat.widget.AppCompatImageButton(this);
            more.setImageResource(R.drawable.ic_more);
            more.setImageTintList(android.content.res.ColorStateList.valueOf(
                color(com.google.android.material.R.attr.colorOnSurfaceVariant)));
            android.util.TypedValue ripple = new android.util.TypedValue();
            getTheme().resolveAttribute(android.R.attr.selectableItemBackgroundBorderless, ripple, true);
            more.setBackgroundResource(ripple.resourceId);
            more.setContentDescription(project.getName() + "：更多操作");
            more.setEnabled(!jobs.busy);
            header.addView(more, new LinearLayout.LayoutParams(dp(48), dp(48)));
            more.setOnClickListener(v -> showProjectMenu(more, project));
            card.addView(header);
            gap(card, 14);
            TextView path = label(project.getAbsolutePath(), 11, false, true);
            path.setTypeface(Typeface.MONOSPACE);
            path.setMaxLines(2);
            path.setEllipsize(TextUtils.TruncateAt.MIDDLE);
            card.addView(path);
            gap(card, 14);
            LinearLayout footer = row();
            footer.addView(label("私有副本 · 仅保存在本机", 11, false, true),
                new LinearLayout.LayoutParams(0, -2, 1));
            MaterialButton open = action("打开终端", false, () -> {
                AppSettings.prefs(this).edit().putString("selected-project", project.getName()).apply();
                Toast.makeText(this, "已有终端不自动 cd；请手动 cd 到项目，或退出 shell 后重进终端", Toast.LENGTH_LONG).show();
                startActivity(new Intent(this, TerminalActivity.class));
            });
            open.setEnabled(!jobs.busy);
            footer.addView(open);
            card.addView(footer);
        }
        TextView note = label("在 Web 中打开：通过项目右上角菜单复制路径，\n再粘贴到 Web 的“打开项目”。卸载应用将删除私有项目。", 12, false, true);
        note.setPadding(dp(4), dp(4), dp(4), dp(8));
        list.addView(note);
    }

    private void showProjectMenu(View anchor, File project) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add(0, 1, 0, "复制项目路径");
        menu.getMenu().add(0, 2, 1, "导出 ZIP");
        menu.setOnMenuItemClickListener(item -> {
            if (jobs.busy) return true;
            if (item.getItemId() == 1) {
                getSystemService(ClipboardManager.class).setPrimaryClip(
                    ClipData.newPlainText("项目路径", project.getAbsolutePath()));
                Toast.makeText(this, "已复制，可在 Web 的打开项目中粘贴", Toast.LENGTH_LONG).show();
            } else {
                new MaterialAlertDialogBuilder(this).setTitle("导出 " + project.getName())
                    .setMessage("包含除符号链接/特殊文件" + (AppSettings.includeGit(this) ? "" : "和 .git")
                        + "以外的所有项目文件，包括 .env 等隐藏文件。请确认不含密钥。")
                    .setNegativeButton("取消", null).setPositiveButton("选择保存位置", (d, w) -> {
                        pendingExport = project.getName();
                        exportPicker.launch(project.getName() + ".zip");
                    }).show();
            }
            return true;
        });
        menu.show();
    }

    /** Task state without Activity references; rotation neither repeats imports nor loses completion callbacks. */
    public static class JobState extends ViewModel {
        final MutableLiveData<String> message = new MutableLiveData<>("就绪");
        boolean busy;
        interface Work { String run() throws Exception; }
        void run(Work work) {
            if (busy) return;
            busy = true;
            message.setValue("正在处理，请勿关闭应用；大项目可能需要一些时间…");
            java.util.concurrent.ExecutorService executor = Executors.newSingleThreadExecutor();
            executor.execute(() -> {
                String result;
                try { result = work.run(); }
                catch (Exception e) { result = "操作失败：" + e.getMessage(); }
                String value = result;
                new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> {
                    busy = false;
                    message.setValue(value);
                });
            });
            executor.shutdown();
        }
    }
}
