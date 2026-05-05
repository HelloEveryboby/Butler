package com.butler.app

class NativeLib {
    companion object {
        init {
            System.loadLibrary("butler-native")
        }
    }

    /**
     * Native method for volume adaptive adjustment.
     */
    external fun calculateOptimalVolume(ambientNoise: Float): Float

    /**
     * Get system hardware status (Battery, NFC, etc.)
     */
    external fun getHardwareStatus(): String

    /**
     * Control system LED or Flashlight.
     */
    external fun controlLED(turnOn: Boolean): Boolean

    /**
     * Simulate an NFC Tag Scan.
     */
    external fun simulateNFCScan(): String
}
