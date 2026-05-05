cmake_minimum_required(VERSION 3.22.1)

project("butler-native")

add_library(butler-native SHARED
    native-lib.cpp
    hardware/hardware_bridge.cpp
)

find_library(log-lib log)

target_link_libraries(butler-native ${log-lib})
