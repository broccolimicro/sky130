#!/bin/bash

rm cells.spice
find pdk/libraries/*_sc_* pdk/libraries/sky130_fd_io -name '*.spice' | grep latest | xargs -I{} cat {} >> cells.spice
