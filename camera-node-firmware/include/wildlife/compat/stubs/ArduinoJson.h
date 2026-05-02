#pragma once

#include <cstddef>

class JsonArray;
class JsonObject;

class JsonValueProxy {
  public:
    template <typename T>
    JsonValueProxy& operator=(const T&) {
        return *this;
    }
};

class JsonArray {
  public:
    JsonObject createNestedObject();

    template <typename T>
    void add(const T&) {}

    std::size_t size() const {
        return 0;
    }
};

class JsonObject {
  public:
    JsonValueProxy operator[](const char*) {
        return JsonValueProxy{};
    }

    JsonArray createNestedArray(const char*) {
        return JsonArray{};
    }
};

inline JsonObject JsonArray::createNestedObject() {
    return JsonObject{};
}

template <std::size_t Capacity>
class StaticJsonDocument {
  public:
    JsonValueProxy operator[](const char*) {
        return JsonValueProxy{};
    }

    JsonArray createNestedArray(const char*) {
        return JsonArray{};
    }
};

template <std::size_t Capacity>
std::size_t serializeJson(const StaticJsonDocument<Capacity>&, char*, std::size_t) {
    return 0;
}