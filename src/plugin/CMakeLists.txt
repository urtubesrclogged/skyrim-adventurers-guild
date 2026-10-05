cmake_minimum_required(VERSION 3.21)
project(AdventurersGuild VERSION 1.0.1 LANGUAGES CXX)  # the mod's version: the DLL reports it, package.sh names the zip after it

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(COMMONLIB_DIR "$ENV{COMMONLIB_DIR}" CACHE PATH "CommonLibVR (alandtse, ng branch) checkout")
if(NOT COMMONLIB_DIR)
	message(FATAL_ERROR "Set COMMONLIB_DIR to a CommonLibVR (alandtse, ng branch) checkout (build.ps1 passes it from local.env)")
endif()
add_subdirectory(${COMMONLIB_DIR} CommonLibSSE EXCLUDE_FROM_ALL)

add_library(AdventurersGuild SHARED src/main.cpp src/RankCore.cpp src/Adventurers.cpp src/Guild.cpp src/Counter.cpp src/Diag.cpp src/ControlsGuard.cpp src/Shop.cpp src/Papyrus.cpp src/NameHook.cpp src/LevelDisplay.cpp src/PrismaToast.cpp src/MissiveWatch.cpp src/NoticeWatch.cpp src/Dungeons.cpp src/Kills.cpp src/Loc.cpp src/Party.cpp)
target_link_libraries(AdventurersGuild PRIVATE CommonLibSSE::CommonLibSSE)
target_precompile_headers(AdventurersGuild PRIVATE <SKSE/SKSE.h> <RE/Skyrim.h>)
target_compile_definitions(AdventurersGuild PRIVATE _UNICODE UNICODE NOMINMAX
	AG_VERSION_MAJOR=${PROJECT_VERSION_MAJOR} AG_VERSION_MINOR=${PROJECT_VERSION_MINOR} AG_VERSION_PATCH=${PROJECT_VERSION_PATCH})
set_target_properties(AdventurersGuild PROPERTIES OUTPUT_NAME "AdventurersGuild")

# Diagnostic plugin, not part of the mod and not built by default: cmake --build build --target ControlsWatch
add_library(ControlsWatch SHARED EXCLUDE_FROM_ALL diag/ControlsWatch.cpp)
target_link_libraries(ControlsWatch PRIVATE CommonLibSSE::CommonLibSSE)
target_precompile_headers(ControlsWatch PRIVATE <SKSE/SKSE.h> <RE/Skyrim.h>)
target_compile_definitions(ControlsWatch PRIVATE _UNICODE UNICODE NOMINMAX)
