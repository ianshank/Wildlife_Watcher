#pragma once

class TwoWire {
  public:
    void begin() {}
    void setClock(unsigned long) {}
};

inline TwoWire Wire;