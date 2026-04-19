#include <windows.h>
#include <string.h>
#include <stdio.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char path[MAX_PATH];
    if (GetModuleFileNameA(NULL, path, MAX_PATH) == 0) {
        return 1;
    }

    // Find the last backslash to get the directory
    char *lastBackslash = strrchr(path, '\\');
    if (lastBackslash != NULL) {
        *lastBackslash = '\0';
    }

    // Set working directory to where the exe is located
    if (!SetCurrentDirectoryA(path)) {
        return 1;
    }

    char venvPython[MAX_PATH];
    snprintf(venvPython, MAX_PATH, "%s\\venv\\Scripts\\pythonw.exe", path);

    char command[MAX_PATH + 128];

    // Check if venv python exists
    WIN32_FIND_DATAA findData;
    HANDLE hFind = FindFirstFileA(venvPython, &findData);
    if (hFind != INVALID_HANDLE_VALUE) {
        FindClose(hFind);
        snprintf(command, sizeof(command), "\"%s\" -m frontend.program.modern_app", venvPython);
    } else {
        // Fallback to system pythonw
        snprintf(command, sizeof(command), "pythonw.exe -m frontend.program.modern_app");
    }

    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    // Create the process
    if (!CreateProcessA(NULL, command, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        char errorMsg[512];
        snprintf(errorMsg, sizeof(errorMsg),
            "无法启动 Butler。\n\n尝试执行的命令: %s\n\n请确保已安装 Python 并在项目根目录下创建了虚拟环境 (venv)。",
            command);
        MessageBoxA(NULL, errorMsg, "Butler 启动错误", MB_OK | MB_ICONERROR);
        return 1;
    }

    // Success - close handles and exit the launcher
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return 0;
}
