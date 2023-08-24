#
# Copyright (C) 2022  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# specify the C/C++ standard
SET(CMAKE_CXX_STANDARD
    17
)
SET(CMAKE_C_STANDARD
    17
)
SET(CMAKE_CXX_STANDARD_REQUIRED
    TRUE
)
SET(CMAKE_C_STANDARD_REQUIRED
    TRUE
)

#
# Ref.: https://cmake.org/cmake/help/latest/variable/CMAKE_LANG_COMPILER_ID.html#variable:CMAKE_%3CLANG%3E_COMPILER_ID
#
# Also consider this one: https://stackoverflow.com/a/10055571
#

IF(NOT DEFINED RV_MAJOR_VERSION)
  MESSAGE(FATAL_ERROR "The 'RV_MAJOR_VERSION' CMake variable is not set!")
ENDIF()
IF(NOT DEFINED RV_MINOR_VERSION)
  MESSAGE(FATAL_ERROR "The 'RV_MINOR_VERSION' CMake variable is not set!")
ENDIF()
IF(NOT DEFINED RV_REVISION_NUMBER)
  MESSAGE(FATAL_ERROR "The 'RV_REVISION_NUMBER' CMake variable is not set!")
ENDIF()

ADD_COMPILE_OPTIONS(-DMAJOR_VERSION=${RV_MAJOR_VERSION} -DMINOR_VERSION=${RV_MINOR_VERSION} -DREVISION_NUMBER=${RV_REVISION_NUMBER})

IF(UNIX)
  INCLUDE(cxx_unix_defaults)
ENDIF()

IF(CMAKE_CXX_COMPILER_ID MATCHES "GNU")
  INCLUDE(cxx_gcc_defaults)
ELSEIF(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  INCLUDE(cxx_clang_defaults)
ELSEIF(MSVC)
  INCLUDE(cxx_msvc_defaults)
ELSE()
  MESSAGE(FATAL_ERROR "Couldn't determine compiler identity")
ENDIF()
