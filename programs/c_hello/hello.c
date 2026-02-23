#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc > 1) {
        // Combine all arguments into a single string
        char message[1024] = "";
        for (int i = 1; i < argc; ++i) {
            strcat(message, argv[i]);
            if (i < argc - 1) {
                strcat(message, " ");
            }
        }
        printf("Hello, %s from C!\n", message);
    } else {
        printf("Hello World from C!\n");
    }
    return 0;
}
