### Generic native Skirmish AI config
#

set(CMAKE_CXX_STANDARD 20)

set(mySourceDirRel         "src/") # Common values are "" or "src"
set(additionalSources      ${CMAKE_SOURCE_DIR}/rts/System/StringUtil.cpp)
set(additionalSources      ${additionalSources} ${CMAKE_SOURCE_DIR}/rts/System/Misc/SpringTime.cpp)
if (WIN32)  # spring::condition_variable_any requirement
	set(additionalSources  ${additionalSources} ${CMAKE_SOURCE_DIR}/rts/System/Platform/Win/CriticalSection.cpp)
elseif (APPLE)
	set(additionalSources  ${additionalSources} ${CMAKE_SOURCE_DIR}/rts/System/Platform/Mac/Signal.cpp)
else ()
	set(additionalSources  ${additionalSources} ${CMAKE_SOURCE_DIR}/rts/System/Platform/Linux/Futex.cpp)
endif ()
set(additionalLibraries    ${Cpp_AIWRAPPER_TARGET} CUtils)  # can't use Tracy::TracyClient in dll, requires -fPIC


#set(additionalCompileFlags "-Isrc/lib/ -Isrc/circuit/ -O1 -DDEBUG -DDEBUG_VIS -DDEBUG_LOG -Wall -Wextra -D_GLIBCXX_USE_CXX11_ABI=0")
if    (CIRCUIT_DEBUG)
	if (WIN32)
		set(additionalLibraries ${additionalLibraries} ${SDL2_LIBRARY})
	endif ()
	set(additionalCompileFlags "-DDEBUG_VIS -Wall")
	# set(additionalCompileFlags "-DDEBUG_VIS -Wall -fsanitize=address -fno-omit-frame-pointer -fno-common -O1 -fno-strict-aliasing")
else  (CIRCUIT_DEBUG)
	set(additionalCompileFlags "-Wall")
	# set(additionalCompileFlags "-Wall -fno-omit-frame-pointer -O1")
endif (CIRCUIT_DEBUG)

# set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} -static-libgcc -static-libstdc++ -lasan")


if    (CIRCUIT_AS_JIT)
	if (WIN32)
		set(additionalSources  ${additionalSources} platform/angelscript/jit/virtual_asm_windows.cpp)
	elseif (APPLE)
		set(additionalSources  ${additionalSources} platform/angelscript/jit/virtual_asm_linux.cpp)
	else ()
		set(additionalSources  ${additionalSources} platform/angelscript/jit/virtual_asm_linux.cpp)
	endif ()
	if (CMAKE_SIZEOF_VOID_P EQUAL 8)
		set(additionalSources  ${additionalSources} platform/angelscript/jit/virtual_asm_x64.cpp)
	else ()
		set(additionalSources  ${additionalSources} platform/angelscript/jit/virtual_asm_x86.cpp)
	endif ()
	set(additionalSources      ${additionalSources} platform/angelscript/jit/as_jit.cpp)
	set(additionalCompileFlags "${additionalCompileFlags} -DCIRCUIT_AS_JIT")
endif (CIRCUIT_AS_JIT)


if    (BUILD_Cpp_AIWRAPPER)
	include_directories(BEFORE
		${Cpp_AIWRAPPER_INCLUDE_DIRS}
		${SDL2_INCLUDE_DIR}
		${CMAKE_CURRENT_SOURCE_DIR}/src/lib/
		${CMAKE_CURRENT_SOURCE_DIR}/src/lib/angelscript/include/
		${CMAKE_CURRENT_SOURCE_DIR}/src/circuit/
	)
	get_target_property(TRACY_INCLUDE_DIRS Tracy::TracyClient INCLUDE_DIRECTORIES)
	include_directories(BEFORE ${TRACY_INCLUDE_DIRS})
	if (CIRCUIT_PROFILING)
		set(additionalCompileFlags "${additionalCompileFlags} -fno-omit-frame-pointer -DCIRCUIT_PROFILING")
		if (NOT TRACY_ENABLE)
			get_target_property(TRACY_SOURCES Tracy::TracyClient SOURCES)
			set(additionalSources ${additionalSources} ${TRACY_SOURCES})
			set(additionalCompileFlags "${additionalCompileFlags} -DTRACY_ENABLE -DTRACY_ON_DEMAND -DTRACY_CALLSTACK=10 -DTRACY_NO_CALLSTACK_INLINES")
			set(additionalCompileFlags "${additionalCompileFlags} -DTRACY_NO_BROADCAST -DTRACY_NO_FRAME_IMAGE -DTRACY_NO_SYSTEM_TRACING")  # -DTRACY_NO_SAMPLING
		endif ()
	endif ()

	# === V3: gRPC gateway additions (isolated for upstream-merge clarity, Constitution I) ===
	# Symbol-hiding on the plugin .so: the engine ships its own protobuf; unhidden
	# symbols resolve across library boundaries and crash rarely and dramatically.
	# See docs/architecture.md §Critical Pitfalls #3 and research.md §10.
	if (NOT WIN32 AND NOT APPLE)
		set(additionalCompileFlags "${additionalCompileFlags} -fvisibility=hidden -fvisibility-inlines-hidden")
		set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} -Wl,-Bsymbolic")
		set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-Bsymbolic")
	endif ()

	# T005: hard-fail when wire deps are missing (FR-002). The earlier
	# WARNING fallback let the gateway module build as a stub, producing
	# an .so that loaded but served no traffic — the exact silent-skip
	# failure mode 002 exists to close.
	option(HIGHBAR_REQUIRE_WIRE_DEPS
		"Fail the build if Protobuf/gRPC are not found via vcpkg" ON)

	# gRPC + Protobuf resolved via vcpkg manifest mode (see vcpkg.json).
	# Consumer should pass -DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake.
	find_package(Protobuf CONFIG QUIET)
	find_package(gRPC     CONFIG QUIET)
	if (Protobuf_FOUND AND gRPC_FOUND)
		set(HIGHBAR_PROTO_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen")
		file(MAKE_DIRECTORY "${HIGHBAR_PROTO_GEN_DIR}/highbar")
		# Pre-generated stubs live under HighBarV3/build/gen (emitted by
		# `cd proto && buf generate`, per BUILD.md step 3). When this
		# CMakeLists is included from the engine tree (AI-only build),
		# CMAKE_CURRENT_BINARY_DIR points under the engine's build tree
		# instead — copy the stubs in so the glob below resolves.
		set(HIGHBAR_PROTO_SRC_STUBS "${CMAKE_CURRENT_SOURCE_DIR}/build/gen/highbar")
		if (EXISTS "${HIGHBAR_PROTO_SRC_STUBS}")
			file(GLOB _src_stubs "${HIGHBAR_PROTO_SRC_STUBS}/*.pb.cc"
			                     "${HIGHBAR_PROTO_SRC_STUBS}/*.pb.h"
			                     "${HIGHBAR_PROTO_SRC_STUBS}/*.grpc.pb.cc"
			                     "${HIGHBAR_PROTO_SRC_STUBS}/*.grpc.pb.h")
			file(COPY ${_src_stubs}
			     DESTINATION "${HIGHBAR_PROTO_GEN_DIR}/highbar")
		endif ()
		file(GLOB HIGHBAR_PROTO_GEN_SRCS CONFIGURE_DEPENDS
			"${HIGHBAR_PROTO_GEN_DIR}/highbar/*.pb.cc"
			"${HIGHBAR_PROTO_GEN_DIR}/highbar/*.grpc.pb.cc"
		)
		# Placeholder: empty lib is legal; real sources land with T015 (buf generate).
		add_library(highbar_proto STATIC ${HIGHBAR_PROTO_GEN_SRCS})
		set_target_properties(highbar_proto PROPERTIES
			LINKER_LANGUAGE CXX
			POSITION_INDEPENDENT_CODE ON
		)
		if (HIGHBAR_PROTO_GEN_SRCS)
			target_include_directories(highbar_proto PUBLIC "${HIGHBAR_PROTO_GEN_DIR}")
			target_link_libraries(highbar_proto PUBLIC
				gRPC::grpc++
				protobuf::libprotobuf
			)
		endif ()
		list(APPEND additionalLibraries highbar_proto)
	elseif (HIGHBAR_REQUIRE_WIRE_DEPS)
		message(FATAL_ERROR
			"HighBarV3: gRPC/Protobuf not found via vcpkg. The gateway "
			"module MUST NOT build without wire deps (FR-002). Pass "
			"-DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake, "
			"or -DHIGHBAR_REQUIRE_WIRE_DEPS=OFF to intentionally produce "
			"a no-gateway .so (local development only).")
	else ()
		message(WARNING
			"HighBarV3: gRPC/Protobuf not found via vcpkg — gateway module "
			"building without wire dependencies. HIGHBAR_REQUIRE_WIRE_DEPS=OFF.")
	endif ()

	# T006: emit SpringHeadlessPin.h from data/config/spring-headless.pin
	# so GrpcGatewayModule.cpp's startup banner logs the engine pin
	# (release_id + sha256). Pin-file changes force a reconfigure.
	set(HIGHBAR_PIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/data/config/spring-headless.pin")
	set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${HIGHBAR_PIN_FILE}")
	file(READ "${HIGHBAR_PIN_FILE}" _highbar_pin_content)
	string(REGEX MATCH "release_id[ \t]*=[ \t]*\"([^\"]+)\"" _ "${_highbar_pin_content}")
	set(HIGHBAR_ENGINE_RELEASE_ID "${CMAKE_MATCH_1}")
	string(REGEX MATCH "sha256[ \t]*=[ \t]*\"([^\"]+)\"" _ "${_highbar_pin_content}")
	set(HIGHBAR_ENGINE_SHA256 "${CMAKE_MATCH_1}")
	if (NOT HIGHBAR_ENGINE_RELEASE_ID OR NOT HIGHBAR_ENGINE_SHA256)
		message(FATAL_ERROR
			"HighBarV3: failed to parse release_id/sha256 from ${HIGHBAR_PIN_FILE}")
	endif ()
	set(HIGHBAR_PIN_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen")
	file(MAKE_DIRECTORY "${HIGHBAR_PIN_GEN_DIR}")
	file(CONFIGURE
		OUTPUT "${HIGHBAR_PIN_GEN_DIR}/SpringHeadlessPin.h"
		CONTENT
[[// Generated from data/config/spring-headless.pin — do not edit.
#pragma once
namespace circuit::grpc {
constexpr const char* kEngineReleaseId = "@HIGHBAR_ENGINE_RELEASE_ID@";
constexpr const char* kEngineSha256    = "@HIGHBAR_ENGINE_SHA256@";
}  // namespace circuit::grpc
]]
		@ONLY)
	include_directories(BEFORE "${HIGHBAR_PIN_GEN_DIR}")
	# === end V3 additions ===

	configure_native_skirmish_ai(mySourceDirRel additionalSources additionalCompileFlags additionalLibraries)

	# T007: unit-test wiring (FR-015). Register every tests/unit/*_test.cc
	# as a ctest target. GTest is optional: if not found, the tests don't
	# build — but ctest still enumerates zero tests, which FR-016's CI
	# job upgrades to failure.
	option(HIGHBAR_BUILD_TESTS "Build HighBarV3 unit tests" ON)
	if (HIGHBAR_BUILD_TESTS AND Protobuf_FOUND AND gRPC_FOUND)
		enable_testing()
		find_package(GTest CONFIG QUIET)
		if (NOT GTest_FOUND)
			find_package(GTest QUIET)  # fall back to FindGTest module
		endif ()
		if (GTest_FOUND OR GTEST_FOUND)
			add_library(highbar_command_queue_test_support STATIC
				"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit/grpc/CommandQueue.cpp"
				"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit/grpc/Counters.cpp")
			target_include_directories(highbar_command_queue_test_support PUBLIC
				"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit"
				"${HIGHBAR_PROTO_GEN_DIR}"
				"${HIGHBAR_PIN_GEN_DIR}")
			target_link_libraries(highbar_command_queue_test_support PUBLIC
				highbar_proto
				gRPC::grpc++
				protobuf::libprotobuf)

			add_library(highbar_command_validator_test_support STATIC
				"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit/grpc/CommandValidator.cpp"
				"${CMAKE_CURRENT_SOURCE_DIR}/tests/unit/command_validator_test_stubs.cpp"
				"${CMAKE_SOURCE_DIR}/rts/System/float3.cpp")
			target_include_directories(highbar_command_validator_test_support PUBLIC
				"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit"
				"${HIGHBAR_PROTO_GEN_DIR}"
				"${HIGHBAR_PIN_GEN_DIR}")
			target_link_libraries(highbar_command_validator_test_support PUBLIC
				highbar_proto
				gRPC::grpc++
				protobuf::libprotobuf)

			file(GLOB HIGHBAR_UNIT_TEST_SRCS CONFIGURE_DEPENDS
				"${CMAKE_CURRENT_SOURCE_DIR}/tests/unit/*_test.cc")
			foreach (_test_src IN LISTS HIGHBAR_UNIT_TEST_SRCS)
				get_filename_component(_test_name "${_test_src}" NAME_WE)
				add_executable("${_test_name}" "${_test_src}")
				target_include_directories("${_test_name}" PRIVATE
					"${CMAKE_CURRENT_SOURCE_DIR}/src/circuit"
					"${HIGHBAR_PROTO_GEN_DIR}"
					"${HIGHBAR_PIN_GEN_DIR}")
				if (TARGET GTest::gtest_main)
					target_link_libraries("${_test_name}" PRIVATE
						GTest::gtest GTest::gtest_main)
				else ()
					target_link_libraries("${_test_name}" PRIVATE
						${GTEST_BOTH_LIBRARIES})
				endif ()
				target_link_libraries("${_test_name}" PRIVATE
					highbar_proto
					gRPC::grpc++
					protobuf::libprotobuf)
				if (_test_name STREQUAL "command_queue_test")
					target_link_libraries("${_test_name}" PRIVATE
						highbar_command_queue_test_support)
				elseif (_test_name STREQUAL "command_validation_test")
					target_link_libraries("${_test_name}" PRIVATE
						highbar_command_validator_test_support)
				endif ()
				add_test(NAME "${_test_name}" COMMAND "${_test_name}")
			endforeach ()
		else ()
			message(WARNING
				"HighBarV3: GTest not found; unit tests will not be built. "
				"Install via vcpkg (gtest) or disable with -DHIGHBAR_BUILD_TESTS=OFF.")
		endif ()
	endif ()

	# T008: aicommand-arm-coverage build-time check (FR-013). The helper
	# script (tests/headless/_gen-arm-coverage.sh) emits a CSV per
	# contracts/aicommand-coverage-report.md; the target returns
	# non-zero (failing the build) when any arm is unwired or uncovered.
	set(HIGHBAR_COVERAGE_CSV "${CMAKE_CURRENT_BINARY_DIR}/reports/aicommand-arm-coverage.csv")
	add_custom_target(aicommand-arm-coverage
		COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/tests/headless/_gen-arm-coverage.sh"
			--repo-root "${CMAKE_CURRENT_SOURCE_DIR}"
			--output    "${HIGHBAR_COVERAGE_CSV}"
			--strict
		BYPRODUCTS "${HIGHBAR_COVERAGE_CSV}"
		WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
		COMMENT "Generating AICommand arm-coverage CSV + strict check (FR-013)"
		VERBATIM)
else  (BUILD_Cpp_AIWRAPPER)
	message ("warning: (New) C++ Circuit AI will not be built! (missing Cpp Wrapper)")
endif (BUILD_Cpp_AIWRAPPER)
