#pragma once

#if __has_include(<Arduino.h>)
#include <Arduino.h>
#else
#include "wildlife/compat/stubs/Arduino.h"
#endif

#if __has_include(<WiFi.h>)
#include <WiFi.h>
#else
#include "wildlife/compat/stubs/WiFi.h"
#endif