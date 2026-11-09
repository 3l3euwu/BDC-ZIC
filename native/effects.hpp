#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

// 0 disables an effect. Volume is 1..10, with 5 = unity.
struct EffectSettings {
    int reverb = 0, distance = 0, clarity = 0, muffle = 0, size = 0, stereo = 0, volume = 5;
};
static inline int clamp_setting(int value, int low, int high) {
    return std::max(low, std::min(high, value));
}

class Effects {
    std::vector<float> delay_ = std::vector<float>(24000, 0.0f); // 500ms at 48kHz
    size_t position_ = 0;
    float low_ = 0, high_low_ = 0;
public:
    int16_t process(int16_t left, int16_t right, const EffectSettings& input) {
        const int reverb = clamp_setting(input.reverb, 0, 10);
        const int distance = clamp_setting(input.distance, 0, 10);
        const int clarity = clamp_setting(input.clarity, 0, 10);
        const int muffle = clamp_setting(input.muffle, 0, 10);
        const int size = clamp_setting(input.size, 0, 10);
        const int stereo = clamp_setting(input.stereo, 0, 10);
        const int volume = clamp_setting(input.volume, 1, 10);
        // A mono emitter cannot preserve stereo width: this is input L/R balance.
        const float balance = stereo ? (stereo - 5.5f) / 9.0f : 0.0f;
        float x = (left * (0.5f - balance) + right * (0.5f + balance)) / 32768.0f;
        float cutoff = 1.0f / (1.0f + 0.75f * muffle + 0.35f * distance);
        low_ += cutoff * (x - low_);
        x = low_ / (1.0f + 0.12f * distance);
        // A small high-frequency lift, not a promise of restoration or noise reduction.
        high_low_ += 0.2f * (x - high_low_);
        x += (x - high_low_) * (0.10f * clarity);
        // Size adds an early reflection; reverb adds a feedback tail.
        const size_t samples = static_cast<size_t>(2400 + 1680 * size); // 50..400ms
        const float echo = delay_[(position_ + delay_.size() - samples) % delay_.size()];
        delay_[position_] = std::clamp(x + echo * (0.045f * reverb), -2.0f, 2.0f);
        position_ = (position_ + 1) % delay_.size();
        x += echo * (0.035f * size + 0.055f * reverb);
        x *= volume / 5.0f;
        x = std::clamp(x, -1.0f, 32767.0f / 32768.0f);
        return static_cast<int16_t>(std::lround(x * 32768.0f));
    }
};
