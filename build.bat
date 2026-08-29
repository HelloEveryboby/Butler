@echo off
chcp 65001 >nul 2>&1
title Butler 打包工具

echo.
echo  ========================================
echo   🤵 Butler 打包工具 (Windows)
echo  ========================================
echo.
echo  选择打包模式:
echo    1. TUI 终端版本 (默认)
echo    2. GUI 现代界面版本
echo    3. 统一启动器
echo    4. 全部打包
echo    5. 清理构建目录
echo    0. 退出
echo.

set /p choice=  请输入选项 [1]:

if "%choice%"=="1" goto tui
if "%choice%"=="2" goto gui
if "%choice%"=="3" goto launcher
if "%choice%"=="4" goto all
if "%choice%"=="5" goto clean
if "%choice%"=="0" goto end
goto tui

:tui
echo.
echo  [打包] TUI 终端版本...
python build.py --mode tui
goto done

:gui
echo.
echo  [打包] GUI 现代界面版本...
python build.py --mode gui
goto done

:launcher
echo.
echo  [打包] 统一启动器...
python build.py --mode launcher
goto done

:all
echo.
echo  [打包] 全部版本...
python build.py --mode all
goto done

:clean
echo.
echo  [清理] 构建目录...
python build.py --clean
goto done

:done
echo.
echo  ========================================
echo  打包完成！输出目录: dist\
echo  ========================================
echo.
pause

:end
