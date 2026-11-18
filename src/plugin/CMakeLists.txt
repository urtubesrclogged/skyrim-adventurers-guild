cmake_minimum_required(VERSION 3.21)
project(AdventurersGuild VERSION 2.0.0 LANGUAGES CXX)  # the mod's version: the DLL reports it, package.sh names the zip after it
# The pre-release label, part of the version wherever it is shown (AG's log, CHIM's data, package.sh's zip and installer):
# "-alpha.N" until 2.0.0 is published, then "" (bumped per published alpha). The
# environment variable AG_VERSION_LABEL, if set when CMake configures, overrides it for that build.
set(AG_VERSION_LABEL "-alpha.4")
if(DEFINED ENV{AG_VERSION_LABEL})
	set(AG_VERSION_LABEL "$ENV{AG_VERSION_LABEL}")
endif()

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(COMMONLIB_DIR "$ENV{COMMONLIB_DIR}" CACHE PATH "CommonLibVR (alandtse, ng branch) checkout")
if(NOT COMMONLIB_DIR)
	message(FATAL_ERROR "Set COMMONLIB_DIR to a CommonLibVR (alandtse, ng branch) checkout (build.ps1 passes it from local.env)")
endif()
# Source file names compiled into the DLL (log lines, CommonLib's checks) would carry the building machine's folders into
# the release; trim both trees to paths relative to their roots. Before add_subdirectory, so CommonLib gets it too.
if(MSVC)
	file(TO_NATIVE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/" AG_TRIM_SELF)
	file(TO_NATIVE_PATH "${COMMONLIB_DIR}/" AG_TRIM_COMMONLIB)
	add_compile_options("/d1trimfile:${AG_TRIM_SELF}" "/d1trimfile:${AG_TRIM_COMMONLIB}")
endif()
add_subdirectory(${COMMONLIB_DIR} CommonLibSSE EXCLUDE_FROM_ALL)

add_library(AdventurersGuild SHARED src/main.cpp src/RankCore.cpp src/Adventurers.cpp src/Guild.cpp src/Counter.cpp src/SteamVRAim.cpp src/GuildCard.cpp src/Diag.cpp src/ControlsGuard.cpp src/Shop.cpp src/Papyrus.cpp src/NameHook.cpp src/LevelDisplay.cpp src/PrismaToast.cpp src/MissiveWatch.cpp src/NoticeWatch.cpp src/BountyWatch.cpp src/Dungeons.cpp src/Kills.cpp src/Loc.cpp src/Party.cpp src/ChoiceSwap.cpp src/MemberCards.cpp src/SkyrimNetData.cpp src/ChimData.cpp src/Wares.cpp src/Faces.cpp src/GuildHall.cpp src/GuildBoard.cpp src/LeaderBoard.cpp src/UiHost.cpp
	src/hall/navmesh.cpp src/hall/hall.cpp src/hall/outdoor.cpp src/hall/marker.cpp
	src/hall/grass.cpp)  # the Guild Hall's outside: idle without the hall's plugin
# the hall's outdoor navmesh clips and fills polygons (src/hall/outdoor.cpp)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(Clipper2 CONFIG REQUIRED)
find_path(EARCUT_HPP_INCLUDE_DIRS "mapbox/earcut.hpp")
target_link_libraries(AdventurersGuild PRIVATE CommonLibSSE::CommonLibSSE winhttp nlohmann_json::nlohmann_json Clipper2::Clipper2)
target_include_directories(AdventurersGuild PRIVATE ${EARCUT_HPP_INCLUDE_DIRS})
target_precompile_headers(AdventurersGuild PRIVATE <SKSE/SKSE.h> <RE/Skyrim.h>)
target_compile_definitions(AdventurersGuild PRIVATE _UNICODE UNICODE NOMINMAX
	AG_VERSION_MAJOR=${PROJECT_VERSION_MAJOR} AG_VERSION_MINOR=${PROJECT_VERSION_MINOR} AG_VERSION_PATCH=${PROJECT_VERSION_PATCH}
	AG_VERSION_LABEL="${AG_VERSION_LABEL}")   # (set at the top)
set_target_properties(AdventurersGuild PROPERTIES OUTPUT_NAME "AdventurersGuild")

# Diagnostic plugin, not part of the mod and not built by default: cmake --build build --target ControlsWatch
add_library(ControlsWatch SHARED EXCLUDE_FROM_ALL diag/ControlsWatch.cpp)
target_link_libraries(ControlsWatch PRIVATE CommonLibSSE::CommonLibSSE)
target_precompile_headers(ControlsWatch PRIVATE <SKSE/SKSE.h> <RE/Skyrim.h>)
target_compile_definitions(ControlsWatch PRIVATE _UNICODE UNICODE NOMINMAX)
