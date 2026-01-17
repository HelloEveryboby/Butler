#ifndef COUNTER_H
#define COUNTER_H

#include <stdio.h>

// Struct to hold the counts
typedef struct {
    long lines;
    long words;
    long bytes;
} Counts;

// Function to perform the word count on a file stream
Counts count_stream(FILE *stream);

#endif // COUNTER_H
