#!/system/bin/sh
# patch-shebang.sh — Fix wrapper shebangs on devices: /bin/sh → /system/bin/sh
# (CI renders #!/bin/sh for container smoke tests; Android has no /bin.)
ROOT=/data/local/tmp/andcode
cd "$ROOT" || exit 1
n=0
for f in bin/* usr/bin/* usr/libexec/git-core/* sbin/*; do
  [ -f "$f" ] || continue
  h=$(head -n 1 "$f" 2>/dev/null)
  # Handle both historical forms: `#!/bin/sh` (container rendering) and `/bin/sh` (old artifacts where printf dropped #!).
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
