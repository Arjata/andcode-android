#!/system/bin/sh
# patch-shebang.sh — 真机 wrapper shebang 修正: /bin/sh → /system/bin/sh
# (CI 渲染的 #!/bin/sh 为容器冒烟用;Android 无 /bin)
ROOT=/data/local/tmp/andcode
cd "$ROOT" || exit 1
n=0
for f in bin/* usr/bin/* usr/libexec/git-core/* sbin/*; do
  [ -f "$f" ] || continue
  h=$(head -n 1 "$f" 2>/dev/null)
  # 兼容两种损坏历史: `#!/bin/sh`(容器渲染)与 `/bin/sh`(printf 丢 #! 的旧工件)
  if [ "$h" = '#!/bin/sh' ] || [ "$h" = '/bin/sh' ]; then
    printf '#!/system/bin/sh\n' > "$f.n"
    tail -n +2 "$f" >> "$f.n"
    cat "$f.n" > "$f"
    rm -f "$f.n"
    chmod 0755 "$f"
    n=$((n + 1))
  fi
done
echo "patched: $n wrappers"
"$ROOT/bin/opencode" --version >/dev/null 2>&1 && echo "opencode --version: OK" || echo "opencode --version: FAIL"
