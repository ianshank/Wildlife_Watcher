// power_mgr_stubs.cpp
// Minimal stub definitions of PowerManager for the Unity native-test binary.
// PlatformIO always compiles every .cpp in the active test directory, so these
// symbols are available to the linker without an Arduino runtime.

#include "wildlife/config.h"
#include "wildlife/power_mgmt.h"

namespace wildlife {

void PowerManager::begin() {}

void PowerManager::maybe_sleep(bool /*saw_activity*/) {
    // ARDUINO_ARCH_ESP32 is never defined in native; deep-sleep is unreachable.
}

bool PowerManager::pir_wake_enabled() const {
    return kPirWakeEnabled;
}

}  // namespace wildlife
