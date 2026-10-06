# Top-level Makefile for HP Dragonfly Folio G3 camera drivers & tools
KERNELRELEASE ?= $(shell uname -r)
KDIR ?= /lib/modules/$(KERNELRELEASE)/build

MODULE_DIRS := drivers/int3472 drivers/ov08a10 drivers/og0va1b drivers/lm3643

.PHONY: all modules ir-grab clean

all: modules ir-grab

modules:
	@for dir in $(MODULE_DIRS); do \
		echo "===> Building kernel module in $$dir..."; \
		$(MAKE) -C $$dir KDIR=$(KDIR) || exit 1; \
	done

ir-grab:
	@echo "===> Building tools/ir-grab..."
	@mkdir -p tools/ir-grab/build
	@if [ ! -f tools/ir-grab/build/build.ninja ]; then \
		meson setup tools/ir-grab/build tools/ir-grab; \
	else \
		meson setup --reconfigure tools/ir-grab/build tools/ir-grab; \
	fi
	@ninja -C tools/ir-grab/build

clean:
	@for dir in $(MODULE_DIRS); do \
		echo "===> Cleaning $$dir..."; \
		$(MAKE) -C $$dir KDIR=$(KDIR) clean; \
	done
	@rm -rf tools/ir-grab/build
