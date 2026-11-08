#!/system/bin/sh
# Run manually from the lightweight app terminal, not inside Ubuntu or via run-as.
set -eu
FILES=${ANDCODE_APP_DATA:?run from app terminal}
umask 077
exec > "$FILES/proot-terminal-test.txt" 2>&1
id
cat /proc/self/attr/current
case "$(cat /proc/self/attr/current)" in
    *:untrusted_app:*) ;;
    *) echo 'REJECTED: not application domain'; exit 1 ;;
esac
if enforcement=$(getenforce 2>/dev/null); then
    [ "$enforcement" = Enforcing ]
else
    echo 'SELinux status unreadable in app domain; verify Enforcing separately with adb.'
fi
grep -Eq '^Seccomp:[[:space:]]+2$' /proc/self/status
LAUNCHER=$FILES/term-ubuntu-proot
sh -n "$LAUNCHER"
NAME=andcode-gate-$$
PROJECT=$FILES/projects/$NAME
LINK=$FILES/projects/$NAME-link
# Refuse any collision, including dangling links; do not touch user directories.
[ ! -e "$PROJECT" ] && [ ! -L "$PROJECT" ] && [ ! -e "$LINK" ] && [ ! -L "$LINK" ]
mkdir "$PROJECT"
cleanup() {
    rm -f "$PROJECT/probe.txt" "$LINK"
    rmdir "$PROJECT"
}
trap cleanup EXIT
call() {
    name=$1; shift
    ANDCODE_UBUNTU_PROJECT_NAME=$name /system/bin/sh "$LAUNCHER" "$@"
}
call "$NAME" /bin/bash --noprofile --norc -euc '
    test "$PWD" = "/workspace/$1"
    test -z "${http_proxy:-}${https_proxy:-}${HTTP_PROXY:-}${NODE_TLS_REJECT_UNAUTHORIZED:-}"
    printf "%s\n" "$2" > probe.txt
' -- "$NAME" 'literal argument with spaces $ ;'
[ "$(cat "$PROJECT/probe.txt")" = 'literal argument with spaces $ ;' ]
echo ANDCODE_PROJECT_BIND_WRITE_OK
call '' /bin/bash --noprofile --norc -euc 'test "$PWD" = /root'
code=0
call "$NAME" /bin/bash --noprofile --norc -c 'exit 42' || code=$?
[ "$code" = 42 ]
printf 'stdin intact\n' | call "$NAME" /bin/bash --noprofile --norc -euc 'read -r line; test "$line" = "stdin intact"'
for invalid in ../escape /absolute 'a:b' "$NAME-missing"; do
    if call "$invalid" /usr/bin/true; then echo 'FAIL: unsafe project accepted'; exit 1; fi
done
ln -s "$PROJECT" "$LINK"
if call "$NAME-link" /usr/bin/true; then echo 'FAIL: symlink project accepted'; exit 1; fi
echo ANDCODE_PROOT_TERMINAL_OK
