# Makefile for c_word_counter

# Compiler and flags
CC = gcc
CFLAGS = -Wall -Wextra -std=c99

# Executable name
TARGET = word_counter_exec

# Source files
SOURCES = main.c counter.c

# Object files derived from source files
OBJECTS = $(SOURCES:.c=.o)

# Default target: build the executable
all: $(TARGET)

# Rule to link the object files into the final executable
$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJECTS)

# Rule to compile source files into object files
%.o: %.c counter.h
	$(CC) $(CFLAGS) -c $< -o $@

# Target to clean up the build artifacts
clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
