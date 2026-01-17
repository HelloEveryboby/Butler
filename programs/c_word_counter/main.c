#include <stdio.h>
#include <stdlib.h>
#include "counter.h"

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <file_path>\n", argv[0]);
        return 1;
    }

    char *file_path = argv[1];
    FILE *file = fopen(file_path, "r");

    if (file == NULL) {
        perror("Error opening file");
        return 1;
    }

    Counts counts = count_stream(file);
    fclose(file);

    printf(" %ld %ld %ld %s\n", counts.lines, counts.words, counts.bytes, file_path);

    return 0;
}
