#include "hcp_protocol.h"
#include <string.h>

void hcp_print_packet(hcp_type_t type, hcp_dev_t device, uint8_t action, uint32_t data) {
    uint8_t packet[PACKET_SIZE];
    packet[0] = PACKET_HEADER;
    packet[1] = (uint8_t)type;
    packet[2] = (uint8_t)device;
    packet[3] = action;
    packet[4] = (data >> 24) & 0xFF;
    packet[5] = (data >> 16) & 0xFF;
    packet[6] = (data >> 8) & 0xFF;
    packet[7] = data & 0xFF;

    // Checksum: XOR first 8 bytes
    uint8_t checksum = 0;
    for (int i = 0; i < 8; i++) {
        checksum ^= packet[i];
    }
    packet[8] = checksum;
    packet[9] = PACKET_END;

    printf("HCP Packet (Hex): ");
    for (int i = 0; i < PACKET_SIZE; i++) {
        printf("%02X ", packet[i]);
    }
    printf("\n");
}
