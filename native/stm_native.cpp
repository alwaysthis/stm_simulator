// SPDX-License-Identifier: GPL-2.0-or-later
// Linear search adapted from p4vasp STMSearchProcess, Orest Dubay (2003).
#include <charconv>
#include <cmath>
#include <cstddef>
#include <limits>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif

API long long parse_density(const char* text, size_t length, double* output, size_t capacity) {
    const char* cursor = text;
    const char* end = text + length;
    size_t count = 0;
    while (cursor < end) {
        while (cursor < end && (*cursor == ' ' || *cursor == '\n' || *cursor == '\r' || *cursor == '\t')) ++cursor;
        if (cursor == end) break;
        if (count == capacity) return -1;
        // from_chars does not accept a leading plus sign.
        if (*cursor == '+') ++cursor;
        auto parsed = std::from_chars(cursor, end, output[count], std::chars_format::general);
        if (parsed.ec != std::errc() || parsed.ptr == cursor || !std::isfinite(output[count])) return -1;
        cursor = parsed.ptr;
        if (cursor < end && *cursor != ' ' && *cursor != '\n' && *cursor != '\r' && *cursor != '\t') return -1;
        ++count;
    }
    return static_cast<long long>(count);
}

API void constant_current(const double* data, size_t nx, size_t ny, size_t nz,
                          size_t sx, size_t sy, size_t sz, double cell_height,
                          double threshold, int step, long long start, double* output) {
    const long long planes = static_cast<long long>(nz);
    auto wrap = [planes](long long z) { return (z % planes + planes) % planes; };
    const long long count = step < 0 ? planes + 1 : planes;
    for (size_t x = 0; x < nx; ++x) {
        for (size_t y = 0; y < ny; ++y) {
            double height = std::numeric_limits<double>::quiet_NaN();
            const double* column = data + x*sx + y*sy;
            for (long long offset = 0; offset < count; ++offset) {
                const long long inner = start + step*offset;
                const long long outer = inner-step;
                const double y1 = column[wrap(inner)*sz];
                if (y1 >= threshold) {
                    const double y2 = column[wrap(outer)*sz];
                    const double fraction = y1 == y2 ? 0.0 : (threshold-y1)/(y2-y1);
                    height = (inner+(outer-inner)*fraction)*cell_height/nz;
                    break;
                }
            }
            output[x*ny+y] = height;
        }
    }
}
