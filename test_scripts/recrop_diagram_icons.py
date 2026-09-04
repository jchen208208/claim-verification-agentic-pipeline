"""Re-cut two of the icons in paper/diagram_icons/ from the original artwork.

The ten icons were recovered on 3 September by cropping them out of the pre-3-Sep
model_diagram.png, which is in git at commit 00bb76f. Two of those crops were wrong,
found 3 September by measuring the ink that sits just outside each crop box:

  claim.png    the crop stopped 3 px short on the right, cutting the speech bubble's
               right-hand border clean off. Its ink ran to the file edge.
  verdict.png  the crop began 46 px too high, taking white and the bottom of the
               "Final Verdict" caption, and ended 27 px early, slicing the bottom
               quarter off the bar including its lower border.

The other eight measured clean: no ink of theirs falls outside their crop. In
particular filing.png and bm25.png are complete. The back sheets of the document
stack have no drawn right-hand border, and the magnifier handle ends in a blunt
diagonal, in the original artwork as much as in the crop.

Boxes below are ink bounding boxes in the original, each padded by 6 or 8 px of
white. The pad stops short of the neighbouring arrow where one is close.

Run:  <venv>/bin/python test_scripts/recrop_diagram_icons.py
Needs Pillow. Writes only the two icon files it names.
"""
import subprocess
from io import BytesIO
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "paper" / "diagram_icons"
SOURCE_COMMIT = "00bb76f"

# name: (left, top, right, bottom) in the original 2756x914 artwork
BOXES = {
    "claim":   (69, 59, 195, 171),      # ink (75, 65, 189, 165), pad 6
    "verdict": (2155, 468, 2718, 581),  # ink (2163, 476, 2710, 573), pad 8
}

raw = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:paper/model_diagram.png"],
                     cwd=ROOT, capture_output=True, check=True).stdout
art = Image.open(BytesIO(raw)).convert("RGB")
assert art.size == (2756, 914), f"unexpected artwork size {art.size}"

for name, box in BOXES.items():
    out = ICONS / f"{name}.png"
    before = Image.open(out).size
    art.crop(box).save(out)
    print(f"{name}: {before[0]}x{before[1]} -> {box[2]-box[0]}x{box[3]-box[1]}")
