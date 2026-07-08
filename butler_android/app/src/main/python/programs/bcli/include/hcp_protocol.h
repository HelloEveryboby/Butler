#ifndef HCP_PROTOCOL_H
#define HCP_PROTOCOL_H

#include <stdint.h>
#include <stdio.h>

#define PACKET_SIZE 10
#define PACKET_HEADER 0xAA
#define PACKET_END 0x55

typedef enum {
    TYPE_CTRL = 0x01,
    TYPE_QUERY = 0x02,
    TYPE_ALARM = 0x03
} hcp_type_t;

typedef enum {
    DEV_LED = 0x10,
    DEV_MOTOR = 0x20,
    DEV_SENSOR = 0x30,
    DEV_NFC = 0x40,
    DEV_SYSTEM = 0xFF
} hcp_dev_t;

void hcp_print_packet(hcp_type_t type, hcp_dev_t device, uint8_t action, uint32_t data);

#endif
