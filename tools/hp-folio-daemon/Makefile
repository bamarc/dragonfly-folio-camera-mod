ZIG ?= zig
DESTDIR ?=
PREFIX ?= /usr

BIN = hp-folio-daemon
SRC = hp_folio_daemon.zig

all: $(BIN)

$(BIN): $(SRC)
	$(ZIG) build-exe $(SRC) -lc -O ReleaseSmall -fstrip -femit-bin=$(BIN)

clean:
	rm -f $(BIN) $(BIN).o

install: $(BIN)
	install -d $(DESTDIR)$(PREFIX)/libexec
	install -m 755 $(BIN) $(DESTDIR)$(PREFIX)/libexec/$(BIN)
	install -d $(DESTDIR)/etc/systemd/system
	install -m 644 hp-folio-daemon.service $(DESTDIR)/etc/systemd/system/hp-folio-daemon.service

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/libexec/$(BIN)
	rm -f $(DESTDIR)/etc/systemd/system/hp-folio-daemon.service

.PHONY: all clean install uninstall
