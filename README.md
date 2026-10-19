# Context Contrast Lab

A Windows desktop application for edge-aware local contrast enhancement of photos and screenshots. It uses a deterministic image-processing pipeline; it does not use a generative model.

## Features

- Multiscale luminance decomposition with fine, medium, and broad detail controls.
- Edge-aware adaptive gain from local structure, plus noise suppression in flatter regions.
- Bounded contextual adaptation for subtle local separation.
- Controls update the preview as you adjust them.
- Split comparison with a draggable divider, original-only, and processed-only modes.
- PNG and high-quality JPEG export. Input EXIF orientation is applied on load.
- RGB and RGBA are supported; alpha is kept intact.

## Windows setup

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/). During setup, enable **Add Python to PATH**.
2. Download and unzip this project folder somewhere convenient.
3. Double-click **Run Context Contrast Lab.bat**.

The launcher creates a private Python environment inside the project folder the first time it runs, installs or updates the required packages, and then opens the app. On later launches, it checks for dependency updates before opening. Python is the only prerequisite; you do not need to use PowerShell or install the packages by hand.

If Windows says Python is missing, install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH** during setup. Then double-click the launcher again.

### Optional: run from a terminal

If you prefer to start the app manually, open PowerShell in this folder and run:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Using the app

Choose **Open image…**, then adjust contrast amount and detail scale first. Fine, medium, and broad detail sliders control the contribution of each spatial scale. Edge / halo protection reduces gain around strong coherent edges. Noise protection limits amplification of small-scale variation, especially in flat areas. Context adaptation adds a restrained large-scale illumination-relative adjustment.

In **Split** mode, drag the split position slider or click across the preview to compare the original on the left with the processed image on the right. Select **Original** or **Processed** for a full view. **Export…** saves the processed result as PNG or JPEG.

## Image quality notes

Processing is performed on linear-light luminance and then applied as a luminance ratio to linear RGB, which keeps chroma/hue more stable than separate per-channel contrast changes. The guided multiscale bases preserve major edges better than a plain Gaussian unsharp mask. The controls intentionally allow a wide range, so extreme values can still look artificial; moderate settings are a good starting point.

The application currently processes images in memory. Very large images may take several seconds and use substantial RAM. Export uses 8-bit PNG/JPEG; the preview is resized for display while export retains the input dimensions.

## Project layout

```text
context-contrast-lab/
├── context_contrast_lab/
│   ├── __init__.py
│   ├── app.py
│   └── processor.py
├── main.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

