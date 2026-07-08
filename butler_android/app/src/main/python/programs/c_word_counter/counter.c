#include "counter.h"
#include <ctype.h>

Counts count_stream(FILE *stream) {
    Counts counts = {0, 0, 0};
    int c;
    int in_word = 0;

    while ((c = fgetc(stream)) != EOF) {
        counts.bytes++;
        if (c == '\n') {
            counts.lines++;
        }
        if (isspace(c)) {
            in_word = 0;
        } else if (in_word == 0) {
            in_word = 1;
            counts.words++;
        }
    }

    // If the file is not empty and doesn't end with a newline,
    // the last line still counts.
    if (counts.bytes > 0 && counts.lines == 0) {
        counts.lines = 1;
    } else if (counts.bytes > 0 && fseek(stream, -1, SEEK_END) == 0 && fgetc(stream) != '\n') {
        // This is a simplified check, a more robust solution would handle file read errors
        counts.lines++;
    }


    return counts;
}
