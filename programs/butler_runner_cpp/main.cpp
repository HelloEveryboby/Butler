#define MINIAUDIO_IMPLEMENTATION
#include "include/miniaudio.h"
#include "include/fft.hpp"
#include "include/json.hpp"
#include "include/ixwebsocket/IXWebSocket.h"
#include "include/ixwebsocket/IXNetSystem.h"
#include "include/ixwebsocket/IXHttpClient.h"

#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <cmath>
#include <algorithm>

using json = nlohmann::json;

// Audio engine with simple ring buffer and URL support
class AudioRunner {
public:
    AudioRunner(const std::string& server_url, const std::string& token, const std::string& runner_id)
        : server_url_(server_url), token_(token), runner_id_(runner_id), is_playing_(false),
          ambient_noise_(0.0f), target_gain_(1.0f), current_gain_(1.0f) {

        ix::initNetSystem();

        webSocket_.setUrl(server_url_);
        webSocket_.setOnMessageCallback([this](const ix::WebSocketMessagePtr& msg) {
            if (msg->type == ix::WebSocketMessageType::Message) {
                handle_message(msg->str);
            } else if (msg->type == ix::WebSocketMessageType::Open) {
                std::cout << "Connected to server" << std::endl;
                register_runner();
            }
        });

        setup_audio();
    }

    void start() {
        webSocket_.start();
        while (true) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }

private:
    void setup_audio() {
        ma_device_config config = ma_device_config_init(ma_device_type_playback);
        config.playback.format   = ma_format_f32;
        config.playback.channels = 2;
        config.sampleRate        = 44100;
        config.dataCallback      = data_callback;
        config.pUserData         = this;

        if (ma_device_init(NULL, &config, &device_) != MA_SUCCESS) {
            return;
        }
    }

    static void data_callback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount) {
        AudioRunner* pRunner = (AudioRunner*)pDevice->pUserData;
        if (!pRunner->is_playing_) return;

        ma_uint32 framesRead = (ma_uint32)ma_decoder_read_pcm_frames(&pRunner->decoder_, pOutput, frameCount, NULL);

        if (framesRead > 0) {
            float* samples = (float*)pOutput;
            for(ma_uint32 i=0; i<framesRead * 2; ++i) {
                pRunner->current_gain_ = pRunner->current_gain_ * 0.999f + pRunner->target_gain_ * 0.001f;
                samples[i] *= pRunner->current_gain_;
            }

            static int fft_skip = 0;
            if (++fft_skip >= 2) {
                fft_skip = 0;
                std::vector<float> mono_samples(std::min(framesRead, (ma_uint32)512));
                for(size_t i=0; i<mono_samples.size(); ++i) {
                    mono_samples[i] = (samples[i*2] + samples[i*2+1]) / 2.0f;
                }
                auto spectrum = FFT::get_spectrum(mono_samples, 32);
                pRunner->send_spectrum(spectrum);
            }
        }

        if (framesRead < frameCount) {
            pRunner->is_playing_ = false;
            ma_device_stop(pDevice);
        }
    }

    void handle_message(const std::string& message) {
        try {
            auto j = json::parse(message);
            if (j["token"] != token_) return;

            std::string type = j["type"];
            if (type == "music_play") {
                play_music(j["payload"]);
            } else if (type == "music_pause") {
                pause_music();
            } else if (type == "music_stop") {
                stop_music();
            } else if (type == "music_volume") {
                set_volume(j["payload"]);
            } else if (type == "ambient_noise") {
                update_ambient_noise(j["payload"]);
            }
        } catch (...) {}
    }

    void update_ambient_noise(float level) {
        ambient_noise_ = level;
        if (ambient_noise_ > 60.0f) {
            target_gain_ = 1.0f + (ambient_noise_ - 60.0f) * 0.02f;
        } else {
            target_gain_ = 1.0f;
        }
        target_gain_ = std::min(2.0f, target_gain_);
    }

    void register_runner() {
        json reg = {{"type", "register"}, {"token", token_}, {"runner_id", runner_id_}};
        webSocket_.send(reg.dump());
    }

    void send_spectrum(const std::vector<double>& spectrum) {
        json msg = {
            {"type", "music_fft"},
            {"payload", spectrum},
            {"runner_id", runner_id_},
            {"token", token_}
        };
        webSocket_.send(msg.dump());
    }

    void play_music(const std::string& path) {
        if (is_playing_) {
            ma_device_stop(&device_);
            ma_decoder_uninit(&decoder_);
        }

        if (path.substr(0, 4) == "http") {
            // URL Stream: Download to memory first (Simple version)
            std::cout << "Downloading stream: " << path << std::endl;
            ix::HttpClient httpClient;
            auto response = httpClient.get(path);
            if (response->statusCode == 200) {
                if (ma_decoder_init_memory(response->payload.data(), response->payload.size(), NULL, &decoder_) == MA_SUCCESS) {
                    is_playing_ = true;
                    ma_device_start(&device_);
                }
            } else {
                std::cerr << "Failed to download music: " << response->errorMsg << std::endl;
            }
        } else {
            // Local file
            if (ma_decoder_init_file(path.c_str(), NULL, &decoder_) == MA_SUCCESS) {
                is_playing_ = true;
                ma_device_start(&device_);
            }
        }
    }

    void pause_music() {
        if (is_playing_) ma_device_stop(&device_);
        else ma_device_start(&device_);
        is_playing_ = !is_playing_;
    }

    void stop_music() {
        is_playing_ = false;
        ma_device_stop(&device_);
        ma_decoder_uninit(&decoder_);
    }

    void set_volume(float volume) {
        ma_device_set_master_volume(&device_, volume / 100.0f);
    }

    std::string server_url_, token_, runner_id_;
    ix::WebSocket webSocket_;
    ma_device device_;
    ma_decoder decoder_;
    std::atomic<bool> is_playing_;
    float ambient_noise_;
    float target_gain_;
    float current_gain_;
};

int main(int argc, char** argv) {
    std::string server = "ws://localhost:8000/ws/butler", token = "", id = "cpp_runner";
    for(int i=1; i<argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-server" && i+1 < argc) server = argv[++i];
        if (arg == "-token" && i+1 < argc) token = argv[++i];
        if (arg == "-id" && i+1 < argc) id = argv[++i];
    }

    if (token.empty()) {
        std::cerr << "Error: Token is required. Use -token to specify." << std::endl;
        return 1;
    }

    AudioRunner runner(server, token, id);
    runner.start();
    return 0;
}
