#ifndef HARDWARE_DB_H
#define HARDWARE_DB_H

typedef struct {
    unsigned short vendor_id;
    unsigned short device_id;
    const char* vendor_name;
    const char* device_name;
    const char* driver_module;
} PCIDevice;

// A comprehensive (simulated) PCI ID database for real system analysis
static const PCIDevice pci_db[] = {
    {0x8086, 0x1237, "Intel Corporation", "440FX - 82441FX PMC [Natoma]", "intel_agp"},
    {0x8086, 0x7000, "Intel Corporation", "82371SB PIIX3 ISA [Natoma/Triton II]", "piix_pci"},
    {0x8086, 0x7010, "Intel Corporation", "82371SB PIIX3 IDE [Natoma/Triton II]", "ata_piix"},
    {0x8086, 0x7110, "Intel Corporation", "82371AB/EB/MB PIIX4 ISA", "piix4_smbus"},
    {0x8086, 0x7111, "Intel Corporation", "82371AB/EB/MB PIIX4 IDE", "ata_piix"},
    {0x80ee, 0xbeef, "InnoTek Systemberatung GmbH", "VirtualBox Graphics Adapter", "vboxvideo"},
    {0x10de, 0x1c03, "NVIDIA Corporation", "GP106 [GeForce GTX 1060 6GB]", "nvidia"},
    {0x10de, 0x1b81, "NVIDIA Corporation", "GP104 [GeForce GTX 1070]", "nvidia"},
    {0x1002, 0x67df, "Advanced Micro Devices, Inc. [AMD/ATI]", "Ellesmere [Radeon RX 470/480/570/570X/580/580X/590]", "amdgpu"},
    {0x14e4, 0x43a0, "Broadcom Inc. and subsidiaries", "BCM4360 802.11ac Wireless Network Adapter", "wl"},
    // ... potentially thousands more in a real system
};

#endif
