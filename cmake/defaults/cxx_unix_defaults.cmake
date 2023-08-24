#
# Copyright (C) 2022  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

ADD_COMPILE_OPTIONS(-Wall -fPIC)

IF(${ARCH} STREQUAL "IA32_64")
  ADD_COMPILE_OPTIONS(-msse -msse2 -msse3 -mmmx -mfpmath=sse)
ENDIF()

IF(${CMAKE_BUILD_TYPE} STREQUAL "Release")
  ADD_COMPILE_OPTIONS(-DNDEBUG -O3)

ELSEIF(${CMAKE_BUILD_TYPE} STREQUAL "Debug")
  ADD_COMPILE_OPTIONS(-DDEBUG -g -O0)
ENDIF()
