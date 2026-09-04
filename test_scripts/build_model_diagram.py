"""Regenerate paper/model_diagram.png.

The diagram was a flat asset with no regenerator: it was built from artwork that is no
longer on disk and the build script was deleted on 26 August. The ten original icons have
been recovered by cropping them out of that PNG and are kept in paper/diagram_icons/, so
the figure is reproducible from here on. Two of those crops were cutting the artwork and
were re-cut on 3 September; see test_scripts/recrop_diagram_icons.py.

Two components were added on 3 September: the audit trigger and the arbiter. Their icons
are drawn here as vector shapes rather than cropped, because no artwork for them exists.

Redrawn 3 September for legibility. Four changes:
  1. One font size for every piece of text in the figure, and smaller than before.
  2. Thinner lines and smaller arrowheads.
  3. Fewer labels. Four are gone: the two parentheticals on the detector branches, and
     the two on the red edges into the cloud, which were restating what the colour
     already says in the most crowded part of the figure. The claim now reaches the
     retriever and the detector along one shared trunk instead of two parallel lines.
  4. Colour is reserved for the outcome edges. The gate's own two branches are black,
     because a disagreement routed to the arbiter has not yet been decided either way.

Run:  <venv>/bin/python test_scripts/build_model_diagram.py
Needs matplotlib and Pillow, which are not project dependencies. It writes
paper/model_diagram.png and nothing else.
"""
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle, Polygon, FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.image as mpimg

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "paper" / "diagram_icons"
OUT = ROOT / "paper" / "model_diagram.png"

# Colours sampled from the original artwork so the new figure matches it.
# Colour is semantic in this figure and the caption depends on it:
#   GREEN = the claim is answered on the device
#   RED   = the gate's own components sent the claim to the cloud
#   BLACK = pipeline flow
# The numeric escalation is black. It is a routing decision taken before any model
# runs, not an outcome of the gate, and in red it was the loudest line in the figure.
GREEN = "#28734f"
RED = "#8b4f56"
INK = "#111111"
PAPER = "white"
# The palette of the cropped icons, sampled from them, so the two icons that are
# drawn here instead of cropped sit with the rest rather than beside them.
GLOSS_TOP = "#f7f7f9"     # the light end of the fill gradient, at the top
GLOSS_BOT = "#c9d1dd"     # the blue-grey end, at the bottom
GLOSS_EDGE = "#0b0b0d"    # the outline, near black
GLOSS_RULE = "#3f4652"    # the ruled lines that stand for text
GLOSS_METAL = "#9aa2b1"   # the magnifier ring and handle
# Avenir Next: a humanist sans, warmer and less anonymous than Helvetica without
# being decorative. "Optima" and "Gill Sans" are the two other safe swaps here;
# both are installed and both stay inside what a paper figure can wear.
FONT = "Avenir Next"

W, H = 118.0, 42.5      # data units; the figure is saved at 30 px per unit

# Two sizes, and only two. SIZE names the things in the pipeline. EDGE labels the
# arrows between them, and is deliberately well below SIZE so the arrow text reads as
# annotation rather than as another component. At width=\textwidth on a 5.5in NeurIPS
# page these land at roughly 4.9pt and 3.7pt.
SIZE = 10.5
EDGE = 8.0
plt.rcParams["font.family"] = FONT

LW = 1.3                # every arrow and connector in the figure
EW = 1.15               # the outline of a drawn icon
RULE = 0.85             # the ruled lines that stand for text in one
HEAD = 9                # arrowhead size

fig, ax = plt.subplots(figsize=(W / 10, H / 10))
ax.set_xlim(0, W); ax.set_ylim(0, H)
ax.set_aspect("equal"); ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)

# --- node positions ---------------------------------------------------------
# One column per pipeline stage. The two new components get their own column
# between the gate and the cloud model, on the two branches the gate produces.
P = {
    "claim":    (7.0, 39.0),   # sits ON the escalation lane; see TOP below
    "filing":   (7.0, 21.0),
    "bm25":     (17.5, 21.0),
    "chunks":   (28.0, 21.0),
    "numeric":  (38.5, 21.0),
    "qwen3b":   (51.0, 33.5),
    "qwen7b":   (51.0, 8.5),
    "gate":     (62.5, 21.0),
    "arbiter":  (75.0, 33.5),
    "audit":    (75.0, 8.5),
    "whale":    (91.0, 21.0),
    "verdict":  (106.5, 21.0),
}
# Icon heights in data units, chosen so every icon reads at the same visual weight.
# The verdict bar is sized by WIDTH instead, because it is a wide label and not an icon.
ICON_H = {"filing": 6.0, "chunks": 10.5, "numeric": 5.6,
          "qwen3b": 5.8, "qwen7b": 5.8, "gate": 5.4, "whale": 4.4}
ICON_W = {"verdict": 15.0}
_extent = {}


def put_icon(name):
    """Place an icon by data-coordinate extent.

    imshow with an explicit extent is used rather than OffsetImage, whose zoom is
    measured in points and therefore silently rescales when the save dpi differs
    from the figure dpi. Extents are exact and dpi-independent.
    """
    img = mpimg.imread(ICONS / f"{name}.png")
    ih, iw = img.shape[0], img.shape[1]
    if name in ICON_W:
        w = ICON_W[name]; h = w * ih / iw
    else:
        h = ICON_H[name]; w = h * iw / ih
    cx, cy = P[name]
    ax.imshow(img, extent=[cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2],
              zorder=4, interpolation="antialiased")
    _extent[name] = (w, h)
    return w, h


def half(name, axis="w"):
    """Half-width or half-height of a placed icon, for anchoring arrows."""
    w, h = _extent[name]
    return (w if axis == "w" else h) / 2


def node_label(name, text, dy=None):
    """A caption under an icon. Same size as every other piece of text."""
    x, y = P[name]
    h = _extent[name][1] if name in _extent else 5.0
    if dy is None:
        dy = -(h / 2 + 1.2)
    ax.text(x, y + dy, text, ha="center", va="top", fontsize=SIZE,
            color=INK, linespacing=1.2)


def arrow_label(a, b, text, color=INK, frac=0.5, off=0.25):
    """A label lying along its arrow, so the arrow reads as its underline.

    Placed `frac` of the way from a to b, rotated to the arrow's angle, and pushed
    `off` clear of the line along the arrow's normal. rotation_mode="anchor" makes
    va="bottom" mean "above the line" in the ROTATED frame, which is what puts the
    text on the line rather than beside it. Every arrow in this figure points
    rightward, so the angle never needs flipping to keep the text upright.
    """
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
    ax.text(a[0] + (b[0] - a[0]) * frac + nx * off,
            a[1] + (b[1] - a[1]) * frac + ny * off,
            text, ha="center", va="bottom", rotation=ang, rotation_mode="anchor",
            fontsize=EDGE, color=color)


def arrow(a, b, color=INK, rad=0.0, shrinkA=1, shrinkB=1):
    ax.add_patch(FancyArrowPatch(
        a, b, arrowstyle="-|>", mutation_scale=HEAD, lw=LW, color=color,
        shrinkA=shrinkA, shrinkB=shrinkB, zorder=3,
        connectionstyle=f"arc3,rad={rad}", joinstyle="miter", capstyle="butt"))


def elbow(pts, color=INK):
    """Orthogonal multi-segment route; arrowhead on the final segment."""
    for i in range(len(pts) - 2):
        ax.plot([pts[i][0], pts[i + 1][0]], [pts[i][1], pts[i + 1][1]],
                color=color, lw=LW, solid_capstyle="projecting", zorder=2)
    arrow(pts[-2], pts[-1], color=color, shrinkA=0)


def line(a, b, color=INK, zorder=2):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=LW,
            solid_capstyle="projecting", zorder=zorder)


# --- icons drawn rather than cropped ----------------------------------------
# Four of the twelve are drawn here. The gavel and the checklist because no artwork
# for them exists. The claim and the retriever because the artwork that does exist is
# truncated: the speech bubble's tail is cut flat across its point and the magnifier's
# handle is cut across its end, in the original PNG and not just in the crop, so there
# is nothing to re-cut. These two are drawn to match the cropped icons' palette.

def gloss(patch, box, z=4, top=GLOSS_TOP, bot=GLOSS_BOT):
    """Fill a shape with the icons' vertical gradient and draw its outline."""
    patch.set_facecolor("none")
    ax.add_patch(patch)
    x0, y0, x1, y1 = box
    grad = ax.imshow(np.linspace(0, 1, 64).reshape(-1, 1), extent=[x0, x1, y0, y1],
                     origin="upper", aspect="auto", interpolation="bilinear",
                     zorder=z, cmap=LinearSegmentedColormap.from_list("g", [top, bot]))
    grad.set_clip_path(patch)
    return patch


def draw_claim(cx, cy, w, h):
    """Claim. A speech bubble with a tail at the bottom left and four ruled lines."""
    _extent["claim"] = (w, h)
    bh = 0.80 * h                                  # the body; the rest is the tail
    left, right = cx - w / 2, cx + w / 2
    top, bot = cy + h / 2, cy + h / 2 - bh

    body = FancyBboxPatch((left, bot), w, bh, zorder=4, linewidth=EW,
                          boxstyle=f"round,pad=0,rounding_size={0.12 * w}",
                          edgecolor=GLOSS_EDGE)
    gloss(body, (left, top, right, bot))

    # The tail is filled with no edge of its own, then only its two OUTER sides are
    # stroked. Stroking it as a closed polygon would draw a line across its mouth.
    mx0, mx1 = left + 0.16 * w, left + 0.36 * w
    apex = (left + 0.18 * w, bot - 0.20 * h)
    ax.add_patch(Polygon([(mx0, bot), (mx1, bot), apex], closed=True, zorder=5,
                         facecolor=GLOSS_BOT, edgecolor="none"))
    ax.plot([mx0, apex[0], mx1], [bot, apex[1], bot], color=GLOSS_EDGE, lw=EW,
            solid_joinstyle="miter", solid_capstyle="butt", zorder=6)

    rows = [0.22, 0.42, 0.62, 0.82]
    runs = [[(0.09, 0.44), (0.49, 0.58), (0.64, 0.92)],
            [(0.09, 0.62), (0.68, 0.92)],
            [(0.09, 0.29), (0.35, 0.92)],
            [(0.09, 0.54), (0.62, 0.68)]]
    for fy, segs in zip(rows, runs):
        y = top - fy * bh
        for a, b in segs:
            ax.plot([left + a * w, left + b * w], [y, y], color=GLOSS_RULE,
                    lw=RULE, solid_capstyle="round", zorder=6)


def draw_bm25(cx, cy, w, h):
    """Retriever. A ruled page with a folded corner and a magnifier over its lower
    right, the magnifier overhanging the page to the right and below."""
    _extent["bm25"] = (w, h)
    left, top = cx - w / 2, cy + h / 2
    dw, dh = 0.74 * w, h
    fold = 0.30 * dw
    page = FancyBboxPatch((left, top - dh), dw, dh, zorder=4, linewidth=EW,
                          boxstyle=f"round,pad=0,rounding_size={0.07 * dw}",
                          edgecolor=GLOSS_EDGE)
    gloss(page, (left, top, left + dw, top - dh))

    # cut the rounded top right corner away against the paper, then lay the fold in
    m = 0.04 * dw
    ax.add_patch(Polygon([(left + dw - fold, top + m), (left + dw + m, top + m),
                          (left + dw + m, top - fold)], closed=True, zorder=5,
                         facecolor=PAPER, edgecolor="none"))
    ax.add_patch(Polygon([(left + dw - fold, top), (left + dw, top - fold),
                          (left + dw - fold, top - fold)], closed=True, zorder=6,
                         facecolor=GLOSS_METAL, edgecolor=GLOSS_EDGE, linewidth=EW))

    for i, fy in enumerate([0.28, 0.40, 0.52, 0.64, 0.76]):
        y = top - fy * dh
        ax.plot([left + 0.12 * dw, left + (0.84 if i == 0 else 0.44) * dw], [y, y],
                color=GLOSS_RULE, lw=RULE, solid_capstyle="round", zorder=5)

    # the magnifier, drawn outwards from the glass so the ring covers the handle join
    mx, my, r = left + 0.62 * w, top - 0.62 * h, 0.25 * w
    k = 0.7071 * (r + 0.02 * w)
    tip = (cx + w / 2 - 0.05 * w, cy - h / 2 + 0.04 * h)
    for colour, weight in ((GLOSS_EDGE, 4.2), (GLOSS_METAL, 2.9)):
        ax.plot([mx + k, tip[0]], [my - k, tip[1]], color=colour, lw=weight,
                solid_capstyle="round", zorder=5)
    glass = Circle((mx, my), r - 0.05 * w, zorder=6, edgecolor="none")
    gloss(glass, (mx - r, my + r, mx + r, my - r), z=6, top="#ffffff", bot="#dde3ec")
    ax.add_patch(Circle((mx, my), r, zorder=7, facecolor="none",
                        edgecolor=GLOSS_METAL, lw=2.4))
    for rr in (r + 0.037 * w, r - 0.037 * w):
        ax.add_patch(Circle((mx, my), rr, zorder=7, facecolor="none",
                            edgecolor=GLOSS_EDGE, lw=EW))


# --- the two components with no artwork at all -------------------------------
def draw_gavel(cx, cy, s=1.0):
    """Arbiter. A gavel silhouette: a chamfered head with a striking face set off at
    each end, a collar, and a tapered handle ending in a knob. No sounding block.

    Everything is drawn in the gavel's own frame with the head lying along x, then
    rotated by ang. The detail that survives at print size is the OUTLINE, so the
    parts are separated by shape and by two thin paper-coloured gaps rather than by
    outlines, which would close up to a smudge.
    """
    ang = -40
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    # the gavel alone leans up and to the right, so the middle of its ink is not the
    # middle of its frame. Shift it back so it sits centred on the node like the rest.
    cx -= 0.486 * s
    cy -= 0.367 * s

    def R(px, py):
        return (cx + (px * ca - py * sa) * s, cy + (px * sa + py * ca) * s)

    def piece(pts, color=INK, z=6):
        ax.add_patch(Polygon([R(*pt) for pt in pts], closed=True,
                             facecolor=color, edgecolor="none", zorder=z))

    # handle, tapering from the collar down to the knob
    piece([(-0.22, -2.45), (0.22, -2.45), (0.28, 0.30), (-0.28, 0.30)], z=5)
    ax.add_patch(Circle(R(0.0, -2.55), 0.44 * s, facecolor=INK, edgecolor="none",
                        zorder=5))
    # collar, the ring where the handle enters the head
    piece([(-0.55, 0.20), (0.55, 0.20), (0.55, 0.66), (-0.55, 0.66)], z=6)
    # head, a bar with the four corners chamfered
    hx, y0, y1, c = 1.90, 0.78, 2.48, 0.22
    piece([(-hx + c, y0), (hx - c, y0), (hx, y0 + c), (hx, y1 - c),
           (hx - c, y1), (-hx + c, y1), (-hx, y1 - c), (-hx, y0 + c)], z=6)
    # the two striking faces, cut away from the body of the head by a thin gap
    for gx in (-1.26, 1.26):
        piece([(gx - 0.09, y0), (gx + 0.09, y0), (gx + 0.09, y1), (gx - 0.09, y1)],
              color=PAPER, z=7)


def draw_checklist(cx, cy, s=1.0):
    """Audit. A checklist: two items pass, the third does not."""
    w, h = 4.3 * s, 5.4 * s
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0,rounding_size=0.45",
                                facecolor="none", edgecolor=INK, lw=1.9 * s, zorder=5))
    # clip at the top
    ax.add_patch(FancyBboxPatch((cx - 0.95 * s, cy + h / 2 - 0.5 * s), 1.9 * s, 1.0 * s,
                                boxstyle="round,pad=0,rounding_size=0.25",
                                facecolor=INK, edgecolor="none", zorder=6))
    rows = [cy + 1.15 * s, cy - 0.15 * s, cy - 1.45 * s]
    for i, ry in enumerate(rows):
        mx = cx - 1.25 * s
        if i < 2:   # tick
            ax.plot([mx - 0.45 * s, mx - 0.05 * s, mx + 0.6 * s],
                    [ry, ry - 0.42 * s, ry + 0.5 * s],
                    color=INK, lw=1.7 * s, solid_capstyle="round", zorder=5)
        else:       # cross
            for d in (1, -1):
                ax.plot([mx - 0.4 * s, mx + 0.5 * s], [ry - 0.45 * s * d, ry + 0.45 * s * d],
                        color=RED, lw=1.7 * s, solid_capstyle="round", zorder=5)
        ax.plot([cx + 0.05 * s, cx + 1.5 * s], [ry, ry], color=INK, lw=1.4 * s,
                solid_capstyle="round", zorder=5)


# --- draw ------------------------------------------------------------------
for n in ("filing", "chunks", "numeric", "qwen3b", "qwen7b",
          "gate", "whale", "verdict"):
    put_icon(n)
draw_claim(*P["claim"], w=4.40, h=3.85)
draw_bm25(*P["bm25"], w=4.24, h=4.85)
draw_gavel(*P["arbiter"], s=0.95)
draw_checklist(*P["audit"], s=0.855)

node_label("claim", "Claim")
node_label("filing", "10K Filing\n(~41k words)")
node_label("bm25", "BM25\nRetriever")
node_label("chunks", "Retrieved\nChunks")
node_label("numeric", "Numeric\nDetector")
node_label("qwen3b", "Qwen 2.5\nCoder 3B")
node_label("qwen7b", "Qwen 2.5\nCoder 7B")
node_label("gate", "Verification\nGate")
node_label("arbiter", "Arbiter", dy=-4.3)
node_label("audit", "Audit", dy=-4.0)
node_label("whale", "DeepSeek\nV4 Flash")

GAP = 1.2        # breathing room between an icon edge and an arrow end
MID = 21.0       # the spine the pipeline runs along
TRUNK = P["claim"][1]   # the lane the claim travels along to reach its two readers
TOP = 39.0       # the lane the numeric escalation runs along. Deliberately the same
                 # height as TRUNK: the claim runs in at that level, turns down into
                 # the detector, and the escalation carries on out of it and to the
                 # right, so the two read as one line passing through the detector.
RET = 101.5      # the column the on-device answers return down to the verdict

vw, vh = _extent["verdict"][0] / 2, _extent["verdict"][1] / 2
ax.text(P["verdict"][0] + vw, MID + vh + 1.0, "Final Verdict",
        ha="right", va="bottom", fontsize=SIZE, color=INK)

# main left-to-right flow along the spine
for a, b in (("filing", "bm25"), ("bm25", "chunks"), ("chunks", "numeric")):
    arrow((P[a][0] + half(a) + GAP, MID), (P[b][0] - half(b) - GAP, MID))

# The claim is read twice, by the retriever and by the detector. One trunk with a
# drop at each reader, rather than two long parallel lines.
DROP = P["numeric"][0] - 1.4          # where the trunk turns down into the detector
line((P["claim"][0] + half("claim") + 0.5, TRUNK), (DROP, TRUNK))
arrow((P["bm25"][0], TRUNK), (P["bm25"][0], MID + half("bm25", "h") + GAP), shrinkA=0)
arrow((DROP, TRUNK), (DROP, MID + half("numeric", "h") + GAP), shrinkA=0)

# a numeric claim skips the local tier and goes straight to the cloud.
# It leaves the top of the detector to the right of where the claim comes in.
RISE = P["numeric"][0] + 1.4
elbow([(RISE, MID + half("numeric", "h") + GAP), (RISE, TOP),
       (P["whale"][0], TOP), (P["whale"][0], P["whale"][1] + half("whale", "h") + GAP)])
# on the long horizontal run of that elbow, not on its riser, which is vertical and
# would have stood the word on its end
arrow_label((RISE, TOP), (P["whale"][0], TOP), "Yes")

# every other claim goes to the two local arms
for arm, sgn in (("qwen3b", 1), ("qwen7b", -1)):
    a = (P["numeric"][0] + half("numeric") + 0.5, MID + 1.5 * sgn)
    b = (P[arm][0] - half(arm) - GAP, P[arm][1] - 2.6 * sgn)
    arrow(a, b)
    arrow_label(a, b, "No")

# the two local arms -> the gate
for arm, sgn in (("qwen3b", 1), ("qwen7b", -1)):
    arrow((P[arm][0] + half(arm) + GAP, P[arm][1] - 2.6 * sgn),
          (P["gate"][0] - half("gate") - GAP, MID + 2.0 * sgn))

# The gate splits into the two new components. Both branches are black: the gate has
# routed the claim but has not decided where it will be answered.
for comp, sgn, word in (("arbiter", 1, "Disagree"), ("audit", -1, "Agree")):
    a = (P["gate"][0] + half("gate") + GAP, MID + 1.8 * sgn)
    b = (P[comp][0] - 3.6, P[comp][1] - 2.8 * sgn)
    arrow(a, b)
    arrow_label(a, b, word)

# Each new component either escalates to the cloud or answers on the device.
a = (P["arbiter"][0] + 3.9, P["arbiter"][1] - 2.2)
b = (P["whale"][0] - half("whale") - GAP, P["whale"][1] + 3.0)
arrow(a, b, color=RED)
arrow_label(a, b, "Agrees with 3B", color=RED)

a = (P["audit"][0] + 3.4, P["audit"][1] + 2.8)
b = (P["whale"][0] - half("whale") - GAP, P["whale"][1] - 3.0)
arrow(a, b, color=RED)
arrow_label(a, b, "Unconfirmed", color=RED)

# The on-device answers return along their own column to the verdict. The arbiter's
# return is the one line in the figure that another line crosses, so it is broken
# where the numeric escalation passes over it.
CROSS = P["whale"][0]
line((P["arbiter"][0] + 3.9, P["arbiter"][1]), (CROSS - 1.0, P["arbiter"][1]), color=GREEN)
line((CROSS + 1.0, P["arbiter"][1]), (RET, P["arbiter"][1]), color=GREEN)
arrow((RET, P["arbiter"][1]), (RET, MID + vh + GAP), color=GREEN, shrinkA=0)
# centred on the run BEFORE the break, since the true midpoint of the whole line
# falls exactly where the escalation crosses it
arrow_label((P["arbiter"][0] + 3.9, P["arbiter"][1]), (CROSS - 1.0, P["arbiter"][1]),
            "Agrees with 7B", color=GREEN)

a = (P["audit"][0] + 3.4, P["audit"][1])
elbow([a, (RET, P["audit"][1]), (RET, MID - vh - GAP)], color=GREEN)
arrow_label(a, (RET, P["audit"][1]), "Confirmed", color=GREEN)

# the cloud model answers
arrow((P["whale"][0] + half("whale") + GAP, MID), (P["verdict"][0] - vw - GAP, MID))

# imshow resets limits and aspect, so restore them before saving
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
fig.savefig(OUT, dpi=300, facecolor=PAPER)
print("wrote", OUT)
