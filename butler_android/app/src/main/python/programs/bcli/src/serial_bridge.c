#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>

/**
 * Butler Serial Bridge
 * Handles raw serial communication between C Host and STM32.
 */

static int serial_fd = -1;

int serial_init(const char* device, int baudrate) {
    serial_fd = open(device, O_RDWR | O_NOCTTY | O_NDELAY);
    if (serial_fd == -1) return -1;

    struct termios options;
    tcgetattr(serial_fd, &options);
    cfsetispeed(&options, B115200);
    cfsetospeed(&options, B115200);

    options.c_cflag |= (CLOCAL | CREAD);
    options.c_cflag &= ~PARENB;
    options.c_cflag &= ~CSTOPB;
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;

    tcsetattr(serial_fd, TCSANOW, &options);
    return 0;
}

int serial_send(const char* data) {
    if (serial_fd == -1) return -1;
    return write(serial_fd, data, strlen(data));
}

int serial_receive(char* buffer, size_t size) {
    if (serial_fd == -1) return -1;
    ssize_t n = read(serial_fd, buffer, size - 1);
    if (n > 0) {
        buffer[n] = '\0';
        return n;
    }
    return 0;
}

void serial_close() {
    if (serial_fd != -1) close(serial_fd);
}
