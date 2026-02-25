# STM32 BUCE Node Makefile
# Targeted for STM32F4 series (Cortex-M4)

CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
SIZE = arm-none-eabi-size

CFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -O3 -Wall -Isrc
LDFLAGS = -specs=nosys.specs

SRC = src/main.c
OBJ = main.o
TARGET = buce_stm32

all: $(TARGET).bin

$(TARGET).elf: $(SRC)
	$(CC) $(CFLAGS) $(SRC) $(LDFLAGS) -o $@
	$(SIZE) $@

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f *.o *.elf *.bin
