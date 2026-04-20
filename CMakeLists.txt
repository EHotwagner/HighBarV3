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

	# gRPC + Protobuf resolved via vcpkg manifest mode (see vcpkg.json).
	# Consumer should pass -DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake.
	find_package(Protobuf CONFIG QUIET)
	find_package(gRPC     CONFIG QUIET)
	if (Protobuf_FOUND AND gRPC_FOUND)
		set(HIGHBAR_PROTO_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen")
		file(MAKE_DIRECTORY "${HIGHBAR_PROTO_GEN_DIR}/highbar")
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
	else ()
		message(WARNING
			"HighBarV3: gRPC/Protobuf not found via vcpkg — the gateway module will "
			"build without its wire dependencies. Pass "
			"-DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake to enable.")
	endif ()
	# === end V3 additions ===

	configure_native_skirmish_ai(mySourceDirRel additionalSources additionalCompileFlags additionalLibraries)
else  (BUILD_Cpp_AIWRAPPER)
	message ("warning: (New) C++ Circuit AI will not be built! (missing Cpp Wrapper)")
endif (BUILD_Cpp_AIWRAPPER)
