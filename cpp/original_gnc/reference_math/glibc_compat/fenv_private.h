#pragma once
#define SET_RESTORE_ROUND_53BIT(mode) ::original_gnc_glibc::ScopedRounding rounding_guard(mode)
#define SET_RESTORE_ROUND(mode) ::original_gnc_glibc::ScopedRounding rounding_guard(mode)
