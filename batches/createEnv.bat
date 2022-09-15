@echo off
python -m venv .suivi
.suivi\scripts\python -m pip install --upgrade pip
.suivi\scripts\pip install -r requirements.txt
.suivi\scripts\pip install -r requirements_dev.txt
echo DONE
