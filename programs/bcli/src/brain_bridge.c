#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <fcntl.h>

/**
 * Butler Brain Bridge
 * Handles communication between the C Hand and the Python Brain.
 */

int brain_call(const char* command, char* out_buffer, size_t out_size) {
    int pipe_in[2], pipe_out[2];
    if (pipe(pipe_in) == -1 || pipe(pipe_out) == -1) return -1;

    pid_t pid = fork();
    if (pid == 0) { // Child
        dup2(pipe_in[0], STDIN_FILENO);
        dup2(pipe_out[1], STDOUT_FILENO);
        close(pipe_in[1]);
        close(pipe_out[0]);

        char* args[] = {"python3", "programs/bcli/brain_interface.py", NULL};
        execvp("python3", args);
        exit(1);
    } else { // Parent
        close(pipe_in[0]);
        close(pipe_out[1]);

        // Send command to Python Brain
        write(pipe_in[1], command, strlen(command));
        write(pipe_in[1], "\n", 1);
        close(pipe_in[1]);

        // Read response
        ssize_t n = read(pipe_out[0], out_buffer, out_size - 1);
        if (n > 0) {
            out_buffer[n] = '\0';
        }
        close(pipe_out[0]);
        waitpid(pid, NULL, 0);
        return 0;
    }
}
