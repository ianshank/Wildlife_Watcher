#pragma once

#if defined(PLATFORMIO)
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Seeed_Arduino_SSCMA.h>
#include <base64.hpp>
#else
#include "wildlife/compat/stubs/Arduino.h"
#include "wildlife/compat/stubs/Wire.h"
#include "wildlife/compat/stubs/WiFi.h"
#include "wildlife/compat/stubs/PubSubClient.h"
#include "wildlife/compat/stubs/ArduinoJson.h"
#include "wildlife/compat/stubs/Seeed_Arduino_SSCMA.h"
#include "wildlife/compat/stubs/base64.hpp"
#endif