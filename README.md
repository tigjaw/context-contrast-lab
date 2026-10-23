# Context Contrast Lab

A Windows desktop application for edge-aware local contrast enhancement of photos and screenshots. It uses a deterministic image-processing pipeline; it does not use a generative model.

## Features

- Multiscale luminance processing with fine, medium, and broad detail controls.
- Edge-aware gain and noise protection to help limit halos and amplified grain.
- Context adaptation for subtle separation between nearby bright and dark areas.
- Live preview with original, processed, and split comparison modes.
- PNG and high-quality JPEG export.
- RGB and RGBA support; transparency is preserved.

## Windows setup

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/). During setup, enable **Add Python to PATH**.
2. Download and unzip this project folder somewhere convenient.
3. Double-click **Run Context Contrast Lab.bat**.

The launcher creates a private Python environment inside the project folder the first time it runs, installs or updates the required packages, and then opens the app. On later launches, it checks for dependency updates before opening. Python is the only prerequisite; you do not need to use PowerShell or install the packages by hand.

If the launcher says Python is missing or too old, install or update Python 3.10 or newer and enable **Add Python to PATH**. Pressing a key only closes the message; it does not resume startup. To check an existing installation, open a new Command Prompt and run `py --version`, then double-click the launcher again.

### Optional: run from a terminal

Open PowerShell in the project folder and run:

~~~powershell
python -m pip install -r requirements.txt
python main.py
~~~

## Using the app

Choose **Open image…**, then adjust contrast amount and detail scale first. The preview updates as you adjust the sliders.

In **Split** mode, click or drag the divider across the image to compare the original on the left with the processed result on the right. You can also use the **Split position** slider. Select **Original** or **Processed** for a full view. Choose **Export…** to save the processed image as PNG or JPEG.

## How the app works

The app adjusts image brightness detail at several sizes while trying to preserve colour and avoid emphasizing noise or strong edges.

1. **Work with brightness:** The image is converted from sRGB into linear-light RGB. The app calculates a brightness map (luminance) from the red, green, and blue channels. It performs the contrast calculations on this brightness map rather than boosting each colour channel separately.
2. **Separate detail by size:** The brightness map is smoothed at three scales using a guided filter. Each smoother creates a version with less fine detail. Subtracting neighboring versions gives three detail bands:
   - **Fine** is the difference between the original brightness and the finest smoothed version.
   - **Medium** is the difference between the fine and medium smoothed versions.
   - **Broad** is the difference between the medium and broad smoothed versions.
3. **Estimate edges and noise:** A structure-tensor calculation looks at local brightness gradients and how consistently they point in one direction. Strong, coherent gradients are treated as edges and receive less boost. The app also measures the locally smoothed magnitude of fine detail as a rough noise estimate, then reduces gain in noisy, less structured areas.
4. **Apply adaptive detail gain:** The three detail bands are weighted by their sliders, combined, and multiplied by the overall amount and protection masks.
5. **Add optional context adjustment:** A bounded curve compares each pixel’s brightness with a broad local illumination estimate. This can gently separate nearby bright and dark regions.
6. **Return to colour:** The adjusted brightness is converted back to sRGB. The app scales linear RGB in proportion to the brightness change, which helps keep hue and colour relationships stable. Brightness is clipped to the displayable range.

### Slider guide

| Slider | What it does | How it interacts |
|---|---|---|
| **Contrast amount** | Sets the overall strength of the effect. At zero, the image is unchanged. | Multiplies both the detail enhancement and context adjustment, so increasing it makes the other settings more noticeable. |
| **Detail scale** | Shifts the sizes targeted by all three detail bands. Lower values target smaller features; higher values move the effect toward larger features. | It changes the scale of Fine, Medium, and Broad together. Use the three detail sliders to choose how much each band contributes after choosing the overall size range. |
| **Fine detail** | Controls tiny texture and edges, such as skin texture, grass, or grain. | Raising it can make noise more visible; Noise protection can reduce fine-detail gain in flatter, noisy areas. |
| **Medium detail** | Controls mid-sized features, such as folds, markings, and surface patterns. | Works alongside Fine and Broad detail; changing Detail scale shifts which image features land in this band. |
| **Broad detail** | Controls larger variations, such as shading across a face or landscape. | Use it to emphasize larger forms without needing to raise Fine detail. Detail scale shifts its target size too. |
| **Edge / halo protection** | Reduces detail gain around strong, coherent edges to help prevent bright or dark outlines. | More protection means less boost near edges, including edge detail that might otherwise appear sharper. |
| **Noise protection** | Reduces gain where fine-scale variation looks like grain or compression speckles, especially in flatter areas. | It mainly reins in fine detail. It can balance a stronger Fine detail setting while leaving more structured edges less affected. |
| **Context adaptation** | Adds a restrained brightness adjustment based on how a pixel compares with its broader surroundings. | Contrast amount scales it. It works with the detail bands but adjusts broader light-dark relationships rather than a specific detail size. |

### The main detail calculation

In simplified form, the app combines the three detail bands like this:

~~~text
combined detail =
    fine detail × fine band
  + medium detail × medium band
  + broad detail × broad band

adjusted brightness =
    original brightness
  + contrast amount × combined detail × protection
~~~

The **protection** factor is smaller around strong edges and noisy flat areas. The actual calculation uses smooth masks rather than a hard on/off switch, so changes blend gradually.

Detail scale controls the smoothing radii used to make the bands. If `r` is the Detail scale value, the three guided-filter radii are approximately `1.1 × r`, `4 × r`, and `14 × r` pixels. Changing `r` therefore shifts all three bands together; it does not independently change their strengths.

The context adjustment uses a logarithmic brightness comparison, then limits the result with a `tanh` curve so it remains bounded. In simplified form:

~~~text
relative brightness = log(pixel brightness + offset)
                    - log(local illumination + offset)

context adjustment ≈ context amount
                     × contrast amount
                     × bounded(relative brightness)
~~~

The implementation also reduces this adjustment near strong edges and limits its strength in darker regions.

## Image quality notes

The pipeline is deterministic and does not invent image content. It works on the image’s existing brightness structure. Moderate settings are a good starting point; extreme values can still look artificial or emphasize unwanted texture.

Processing happens in memory. Very large images may take several seconds and use substantial RAM. Export uses 8-bit PNG or JPEG; the preview is resized for display while export retains the input dimensions.

## Project layout

~~~text
context-contrast-lab/
├── context_contrast_lab/
│   ├── __init__.py
│   ├── app.py
│   └── processor.py
├── Run Context Contrast Lab.bat
├── main.py
├── pyproject.toml
├── requirements.txt
└── README.md
~~~
