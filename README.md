
# CTI-Project
automatic cti ranker and GUI

## One-click launch on Windows

Double-click [`launch_cti.bat`](./launch_cti.bat). It creates the local Python environment if needed, installs the required packages, starts the CTI server, and opens the site at <http://127.0.0.1:5000>.

To create a Windows executable with the same behavior, first run `launch_cti.bat` once, then double-click `build_cti_launcher.bat`. This creates `CTI_Launcher.exe` in the project folder. Keep the executable beside the project files; it uses the same `.venv`, database, uploads, templates, and application code. On another computer, the first launch can install Python 3.12 through `winget` and then install the packages from `requirements.txt`.

If Python 3.12 is not installed, the launcher attempts to install it automatically through Windows Package Manager (`winget`). The first launch requires internet access for Python and package installation. If `winget` is unavailable, install Python 3.12 or newer from <https://www.python.org/downloads/windows/> and run the launcher again. Keep the CTI Engine window open while using the site; closing it stops the application.

To create the first login account, open PowerShell in the project folder after the first launch and run:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app create-user
```
