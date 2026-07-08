import ctypes
import os
import sys
import logging
import gc

logger = logging.getLogger("VaultWiper")

def physical_wipe(key: str):
    """
    Android-optimized physical memory erasure using libc.so (memset).
    """
    if key not in os.environ:
        return

    val = os.environ[key]
    if not val:
        return

    try:
        # Load Android's Bionic libc
        libc_name = "libc.so"
        libc = ctypes.CDLL(libc_name)

        # getenv returns a pointer to the value string in the environment block
        libc.getenv.restype = ctypes.c_void_p
        ptr = libc.getenv(key.encode('utf-8'))

        if ptr:
            # Overwrite the memory with 0x00 physically
            ctypes.memset(ptr, 0, len(val))
            logger.info(f"Physically wiped memory for key: {key}")
    except Exception as e:
        logger.error(f"Failed to physically wipe {key}: {e}")

    # Remove from Python's environment mapping
    if key in os.environ:
        del os.environ[key]

    gc.collect()

def wipe_all_sensitive():
    """Wipe all Vault and Token related environment variables."""
    sensitive_prefixes = ["VAULT_", "BUTLER_TOKEN", "SECRET_"]
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in sensitive_prefixes):
            physical_wipe(key)
    gc.collect()
