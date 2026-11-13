# Build libandcode-shim.so (within the baseline: aarch64-linux-gnu-gcc or native gcc)
CC      ?= gcc
CFLAGS  ?= -O2 -fPIC -Wall -Wextra
LDFLAGS ?= -shared -ldl

../libandcode-shim.so: shim.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -o $@ shim.c $(LDFLAGS)

.PHONY: clean
clean:
	rm -f ../libandcode-shim.so
