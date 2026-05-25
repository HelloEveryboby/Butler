#include <jni.h>
#include <string>

extern "C" JNIEXPORT jfloat JNICALL
Java_com_butler_app_NativeLib_calculateOptimalVolume(JNIEnv* env, jobject /* this */, jfloat ambientNoise) {
    // Ported from hybrid_math
    // Basic logic: adjust gain based on ambient noise level
    float gain = 1.0f + (ambientNoise / 100.0f);

    // Clamp gain to a reasonable range
    if (gain > 2.0f) gain = 2.0f;
    if (gain < 0.5f) gain = 0.5f;

    return gain;
}
