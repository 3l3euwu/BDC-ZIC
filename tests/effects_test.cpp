#include "../native/effects.hpp"
#include <cassert>
#include <cstdlib>
int main() {
    EffectSettings s; Effects dry;
    assert(dry.process(10000, 10000, s) == 10000);
    s.volume = 10; Effects loud; assert(loud.process(20000, 20000, s) == 32767);
    s = {}; s.stereo = 1; Effects left; assert(left.process(12000, 0, s) > 11000);
    s.stereo = 10; Effects right; assert(right.process(12000, 0, s) == 0);
    s = {}; s.muffle = 10; Effects muffled; assert(muffled.process(10000, 10000, s) < 2000);
    s = {}; s.distance = 10; Effects far; assert(far.process(10000, 10000, s) < 2000);
    s = {}; s.reverb = 8; s.size = 2; Effects echo;
    assert(echo.process(10000, 10000, s) == 10000);
    bool heard_echo = false;
    for (int i = 0; i < 10000; ++i) if (echo.process(0, 0, s) != 0) heard_echo = true;
    assert(heard_echo);
    s = {}; s.clarity = 8; Effects clear; assert(clear.process(10000, 10000, s) > 10000);
}
