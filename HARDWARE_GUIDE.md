# Hardware Integration Guide for the Butler Voice Assistant

This guide provides a list of recommended hardware components and step-by-step instructions for assembling a portable voice assistant using a Raspberry Pi Zero W. This setup is designed to be "headless," meaning it does not require a screen or keyboard once configured.

## 1. Required Components

Here is a list of suggested components that are known to work well together.

*   **Single-Board Computer:** [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/)
    *   The **W** is essential as it includes built-in Wi-Fi and Bluetooth, which are necessary for network connectivity.
*   **Microphone:** [Adafruit I2S MEMS Microphone Breakout - SPH0645LM4H](https://www.adafruit.com/product/3421)
    *   An I2S microphone provides a direct digital audio signal and is well-supported by the Raspberry Pi.
*   **Audio Amplifier:** [Adafruit I2S 3W Class D Amplifier Breakout - MAX98357A](https://www.adafruit.com/product/3006)
    *   Since the Raspberry Pi Zero has no audio output jack, an I2S amplifier is needed to drive a speaker.
*   **Speaker:** A small 4Ω or 8Ω speaker (e.g., 3W).
    *   Any small speaker will work. Ensure it matches the power output of your amplifier.
*   **Power Supply:** A high-quality 5V 2.5A Micro USB power supply.
*   **Storage:** A reliable microSD card (16GB or larger, Class 10).
*   **GPIO Header:** A 2x20 Male GPIO Header.
    *   The Raspberry Pi Zero usually comes without a header, so you will need to solder one on.

## 2. Assembling the Hardware

### Step 2.1: Soldering the GPIO Header

Before you can connect the components, you must solder the 2x20 male GPIO header onto your Raspberry Pi Zero. If you are new to soldering, there are many excellent tutorials available online.

### Step 2.2: Wiring the Components

Connect the microphone and amplifier to the Raspberry Pi Zero's GPIO pins as described below. **It is crucial to connect the pins correctly to avoid damaging your components.**

| Raspberry Pi Pin # | GPIO Name | Connects to (Microphone)       | Connects to (Amplifier) |
| :----------------- | :-------- | :----------------------------- | :---------------------- |
| Pin 12             | `GPIO18`  | **BCLK** (Bit Clock)           | **BCLK** (Bit Clock)    |
| Pin 35             | `GPIO19`  | **LRCL** (Left-Right Clock)    | **LRC** (Left-Right Clock) |
| Pin 38             | `GPIO20`  | **DOUT** (Data Out)            | -                       |
| Pin 40             | `GPIO21`  | -                              | **DIN** (Data In)       |
| Pin 2 (5V)         | `5V`      | -                              | **Vin** (Power In)      |
| Pin 1 (3.3V)       | `3.3V`    | **Vin** (Power In)             | -                       |
| Pin 6 (GND)        | `GND`     | **GND** (Ground)               | **GND** (Ground)        |

**Microphone Specifics:**
*   Connect the **SEL** (Select) pin on the microphone to **GND** to set it to the Left channel.

**Amplifier Specifics:**
*   Connect your speaker wires to the `(+)` and `(-)` terminals on the amplifier board.

## 3. Software Configuration

### Step 3.1: Install Raspberry Pi OS

Use the official [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash "Raspberry Pi OS Lite (32-bit)" onto your microSD card. The "Lite" version does not have a desktop environment, which is ideal for a headless project.

Use the imager's advanced settings (`Ctrl+Shift+X`) to pre-configure SSH, your Wi-Fi network, and a user account.

### Step 3.2: Configure the I2S Audio Device

After booting your Raspberry Pi, connect to it via SSH and perform the following steps to configure the I2S hardware.

1.  **Edit the `/boot/config.txt` file:**
    ```bash
    sudo nano /boot/config.txt
    ```
    Comment out the default audio line (`dtparam=audio=on`) and add the following line to enable a generic I2S audio driver that works with our components:
    ```
    # dtparam=audio=on
    dtoverlay=i2s-mems-master
    ```
    Save the file (`Ctrl+X`, then `Y`, then `Enter`).

2.  **Create an ALSA configuration file:**
    The system needs to know how to use the I2S hardware. Create a new ALSA configuration file:
    ```bash
    sudo nano /etc/asound.conf
    ```
    Paste the following configuration into the file. This tells the system to use the I2S microphone for recording (`pcm.mic`) and the I2S amplifier for playback (`pcm.speaker`), and sets them as the default (`pcm.!default`).
    ```
    pcm.mic {
        type dsnoop
        ipc_key 1024
        slave {
            pcm "hw:CARD=sndrpisimplecard,DEV=0"
            channels 2
            format S32_LE
            rate 44100
        }
    }

    pcm.speaker {
        type plug
        slave {
            pcm "hw:CARD=sndrpisimplecard,DEV=0"
            channels 2
            format S32_LE
            rate 44100
        }
    }

    pcm.!default {
        type asym
        capture.pcm "mic"
        playback.pcm "speaker"
    }

    ctl.!default {
        type hw
        card sndrpisimplecard
    }
    ```
    Save the file (`Ctrl+X`, then `Y`, then `Enter`).

3.  **Reboot the Raspberry Pi:**
    Apply the changes by rebooting.
    ```bash
    sudo reboot
    ```

### Step 3.3: Test the Hardware

After the reboot, connect via SSH again and test the microphone and speaker.

1.  **Test the Microphone (Record):**
    Record a 5-second audio clip.
    ```bash
    arecord -d 5 --device=default --format=S32_LE --rate=44100 test.wav
    ```
    If this command runs without errors, your microphone is likely working.

2.  **Test the Speaker (Playback):**
    Play back the audio clip you just recorded.
    ```bash
    aplay --device=default test.wav
    ```
    You should hear the recorded audio playing from your speaker. If you do, your hardware is fully configured!

## 4. Next Steps

Your hardware is now assembled and configured. You are ready to install the Butler assistant software. For detailed instructions on how to do this, please refer to the `RASPBERRY_PI_DEPLOY.md` guide.
