@echo off
echo CLEAN %LocalAppData%\Temp
cd %LocalAppData%\Temp
del /q * >nul 2>&1
for /d %%x in (*) do @rd /s /q "%%x" >nul 2>&1
echo CLEAN %AppData%\undetected_chromedriver
cd %AppData%\undetected_chromedriver
del /q *
echo DONE
