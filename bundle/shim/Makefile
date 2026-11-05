# libandcode-shim.so 构建(基线内: aarch64-linux-gnu-gcc 或原生 gcc)
CC      ?= gcc
CFLAGS  ?= -O2 -fPIC -Wall -Wextra
LDFLAGS ?= -shared -ldl

../libandcode-shim.so: shim.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -o $@ shim.c $(LDFLAGS)

.PHONY: clean
clean:
	rm -f ../libandcode-shim.so
