#!/system/bin/sh
# Manual read-only Android 13 diagnosis. No firewall/UID/settings changes.
set -eu
[ "$(id -u)" = 0 ] || { echo 'root diagnosis required' >&2; exit 1; }
[ "$#" = 0 ] || { echo 'no arguments accepted' >&2; exit 1; }
APP_UID=$(stat -c %u /data/data/dev.andcode.app)
case "$APP_UID" in ''|*[!0-9]*) exit 1 ;; esac
[ "$APP_UID" -ge 10000 ] || { echo 'missing application UID' >&2; exit 1; }
printf 'restricted_networking_mode='
settings get global restricted_networking_mode
# /proc/1/root is used only by this explicit human root diagnostic, never by
# normal guest sessions. The three BPF descriptors are opened BPF_F_RDONLY.
sh /data/adb/andcode-ubuntu/andcode-ubuntu admin /usr/bin/python3 -c '
import ctypes, os, platform, sys
if platform.machine() != "aarch64":
    raise SystemExit("diagnostic requires arm64; syscall number not portable")
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
class Obj(ctypes.Structure):
    _fields_ = [("pathname", ctypes.c_uint64), ("bpf_fd", ctypes.c_uint32),
                ("file_flags", ctypes.c_uint32)]
class Elem(ctypes.Structure):
    _fields_ = [("map_fd", ctypes.c_uint32), ("pad", ctypes.c_uint32),
                ("key", ctypes.c_uint64), ("value", ctypes.c_uint64),
                ("flags", ctypes.c_uint64)]
class Info(ctypes.Structure):
    _fields_ = [("fd", ctypes.c_uint32), ("length", ctypes.c_uint32),
                ("info", ctypes.c_uint64)]
def bpf(command, attr):
    result = libc.syscall(280, command, ctypes.byref(attr), ctypes.sizeof(attr))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result
def lookup_map(name, expected_type, value_type, keys):
    path = ctypes.create_string_buffer(("/proc/1/root/sys/fs/bpf/netd_shared/" + name).encode())
    fd = bpf(7, Obj(ctypes.addressof(path), 0, 8))  # OBJ_GET, BPF_F_RDONLY
    try:
        info = (ctypes.c_uint32 * 6)()
        try:
            bpf(15, Info(fd, ctypes.sizeof(info), ctypes.addressof(info)))
            layout = (info[0], info[2], info[3])
        except OSError as error:
            if error.errno not in (22, 38): raise
            # Linux 4.9 predates BPF_OBJ_GET_INFO_BY_FD. Its fdinfo exposes
            # the same required layout; absent metadata still fails closed.
            with open("/proc/self/fdinfo/" + str(fd)) as source:
                fields = dict(line.strip().split(":", 1) for line in source if ":" in line)
            layout = tuple(int(fields[key].strip(), 0)
                           for key in ("map_type", "key_size", "value_size"))
        if layout != (expected_type, 4, ctypes.sizeof(value_type)):
            raise RuntimeError("unsupported map layout: " + name)
        result = {}
        for number in keys:
            key, value = ctypes.c_uint32(number), value_type()
            try:
                bpf(1, Elem(fd, 0, ctypes.addressof(key), ctypes.addressof(value), 0))
                result[number] = value
            except OSError as error:
                if error.errno != 2: raise
                result[number] = None
        return result
    finally:
        os.close(fd)
class Owner(ctypes.Structure):
    _fields_ = [("iif", ctypes.c_uint32), ("rule", ctypes.c_uint32)]
app_uid = int(sys.argv[1])
config = lookup_map("map_netd_configuration_map", 2, ctypes.c_uint32, [0])[0]
if config is None: raise SystemExit("missing global configuration")
print("android13-enabled-rules=" + hex(config.value))
owners = lookup_map("map_netd_uid_owner_map", 1, Owner, [app_uid, 60000])
permissions = lookup_map("map_netd_uid_permission_map", 1, ctypes.c_uint8,
                         [app_uid % 100000, 60000])
for uid in [app_uid, 60000]:
    owner, permission = owners[uid], permissions[uid % 100000]
    rule = owner.rule if owner is not None else 0
    print("uid=%d owner=%s inet-permission-entry=%s" %
          (uid, "absent" if owner is None else "iif=%d rule=%s" % (owner.iif, hex(rule)),
           "absent (not proof of denial)" if permission is None else hex(permission.value)))
    if config.value & 0x20 and not rule & 0x20:
        print("ANDROID13_RESTRICTED_RULE_BLOCKS_UID=%d" % uid)
print("READ_ONLY_DIAGNOSIS_COMPLETE; no network support claim or policy changes")
' "$APP_UID"
