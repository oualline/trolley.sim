Here's how to get `libmpv-2.dll` set up on Windows for use with
python-mpv:

**1. Download a libmpv build**

The standard source is the shinchiro mpv builds, distributed via
SourceForge. You specifically want the *dev/lib* package, not
the regular player:

- Go to https://sourceforge.net/projects/mpv-player-windows/files/
- Open the `libmpv/` folder
- Download the latest `mpv-dev-x86_64-...7z` (use
`mpv-dev-x86_64-v3-...` only if your CPU supports AVX2; the
plain `x86_64` build is the safe choice). Match your Python
architecture — if you're on 64-bit Python, get the 64-bit build.

These are `.7z` archives, so you'll need 7-Zip (https://www.7-zip.org/) to extract them.

**2. Extract the DLL**

Open the archive and pull out `libmpv-2.dll`. Older builds named
it `mpv-2.dll` or `mpv-1.dll`; current python-mpv expects
`libmpv-2.dll`, so if you only see an older name, rename it to
`libmpv-2.dll`.

**3. Put the DLL where Python can find it**

python-mpv loads the DLL via the OS loader, so it needs to be on
the DLL search path. Easiest reliable options:

- Drop `libmpv-2.dll` directly in the same folder as your script
/ the Python executable, **or**

- Place it in a dedicated folder (e.g. `C:\mpv\`) and add that
folder at the top of your script before importing mpv:

```python
import os
os.add_dll_directory(r"C:\mpv")  # Python 3.8+
import mpv
```

`os.add_dll_directory` is the modern, robust way — better than
relying on `PATH`, though adding the folder to `PATH` also works
if you prefer.

**4. Install the Python binding**

```
pip install python-mpv
```

**5. Verify**

```python
import mpv
player = mpv.MPV()
print(player.mpv_version)
```

If it prints a version string, the DLL loaded correctly.

A couple of gotchas worth knowing: a 32-bit/64-bit mismatch
between the DLL and your Python interpreter is the most common
failure (you'll see `OSError` / `could not find libmpv`), so
double-check both are 64-bit. And if you hit a missing-DLL error
despite the file being present, it's almost always the
search-path issue from step 3 rather than a bad download.
