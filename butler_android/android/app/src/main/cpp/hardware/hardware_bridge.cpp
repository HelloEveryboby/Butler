#include <jni.h>
#include <string>
#include <android/log.h>

#define TAG "ButlerHardware"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, TAG, __VA_ARGS__)

extern "C" JNIEXPORT jstring JNICALL
Java_com_butler_app_NativeLib_getHardwareStatus(JNIEnv* env, jobject /* this */) {
    // This is a placeholder for real hardware status detection on Android
    // (e.g. Battery, Sensors, NFC capability)
    LOGD("Detecting hardware status...");
    return env->NewStringUTF("{\"battery\": \"98%\", \"sensors\": \"active\", \"nfc\": \"ready\"}");
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_butler_app_NativeLib_controlLED(JNIEnv* env, jobject /* this */, jboolean turnOn) {
    // Android flashlight or screen brightness control placeholder
    if (turnOn) {
        LOGD("Hardware: Turning on system LED/Flashlight");
    } else {
        LOGD("Hardware: Turning off system LED/Flashlight");
    }
    return JNI_TRUE;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_butler_app_NativeLib_simulateNFCScan(JNIEnv* env, jobject /* this */) {
    // Porting the 'tag_detected' logic from nfc_service.c
    LOGD("Simulating NFC Scan...");
    return env->NewStringUTF("{\"uid\":\"55AA33DD\", \"type\":\"ISO14443A\"}");
}
