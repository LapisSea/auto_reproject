@echo off

set root=%CD%

for %%f in (%root%) do set folder_name=%%~nxf

cd ..
rmdir /Q /S tmp

mkdir tmp
cd tmp 
mkdir %folder_name%
cd ..


copy %root%\*.py tmp\%folder_name%

for %%f in (
SpikeDetector\bin\x64\SpikeDetector\SpikeDetector.exe
) do (
	ECHO F|xcopy %root%\%%f tmp\%folder_name%\%%f
)

cd tmp
jar -cfM %folder_name%.zip %folder_name%
move %folder_name%.zip ..
cd ..
rmdir /Q /S tmp

cd %root%
