# Moss Native — build system for standalone Moss without Python runtime
#
# Build:  make
# Usage:  ./moss-native run examples/order.moss
#         (compiles with Python, executes with C VM)

CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra
LDFLAGS ?= -lm

TARGET  = mossvm
SRCDIR  = src/vm
BINDIR  = bin

all: $(BINDIR)/$(TARGET)

$(BINDIR)/$(TARGET): $(SRCDIR)/mossvm.c
	mkdir -p $(BINDIR)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -rf $(BINDIR)

test: all
	python -m pytest tests/test_mosslang.py -q --tb=short

.PHONY: all clean test
