@rem Gradle Wrapper 启动脚本 (Windows)
@rem 用法: gradlew.bat assembleDebug

@if "%DEBUG%"=="" @echo off
@rem Set local scope
setlocal

set DEFAULT_JVM_OPTS="-Xmx64m" "-Xms64m"

@rem 检查 JAVA_HOME
if defined JAVA_HOME goto findJavaFromJavaHome
set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if %ERRORLEVEL% equ 0 goto execute
echo 错误: 未找到 Java。请安装 JDK 17 并设置 JAVA_HOME。
goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe
if exist "%JAVA_EXE%" goto execute
echo 错误: JAVA_HOME 无效: %JAVA_HOME%
goto fail

:execute
set DIRNAME=%~dp0
set APP_BASE_NAME=%~n0
set CLASSPATH=%DIRNAME%\gradle\wrapper\gradle-wrapper.jar

"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% ^
  "-Dorg.gradle.appname=%APP_BASE_NAME%" ^
  -classpath "%CLASSPATH%" ^
  org.gradle.wrapper.GradleWrapperMain %*

:end
endlocal

:fail
exit /b 1
