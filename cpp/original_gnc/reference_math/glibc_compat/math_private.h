#pragma once
#define __set_errno(value) (errno = (value))
#define attribute_hidden __attribute__((visibility("hidden")))

#define __always_inline inline __attribute__((always_inline))
