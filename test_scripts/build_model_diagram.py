"""Regenerate paper/model_diagram.png.

The diagram was a flat asset with no regenerator: it was built from artwork that is no
longer on disk and the build script was deleted on 26 August. The ten original icons have
been recovered by cropping them out of that PNG and are kept in paper/diagram_icons/, so
the figure is reproducible from here on.

Two components were added on 3 September: the audit trigger and the arbiter. Their icons
are drawn here as vector shapes rather than cropped, because no artwork for them exists.

Redrawn 3 September for legibility. Four changes:
  1. One font size for every piece of text in the figure, and smaller than before.
  2. Thinner lines and smaller arrowheads.
  3. Fewer labels. The two parentheticals on the detector branches are gone, and the
     claim now reaches the retriever and the detector along one shared trunk instead of
     two parallel lines.
  4. Colour is reserved for the outcome edges. The gate's own two branches are black,
     because a disagreement routed to the arbiter has not yet been decided either way.

Run:  <venv>/bin/python test_scripts/build_model_diagram.py
Needs matplotlib and Pillow, which are not project dependencies. It writes
paper/model_diagram.png and nothing else.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon, FancyBboxPatch
import matplotlib.image as mpimg

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "paper" / "diagram_icons"
OUT = ROOT / "paper" / "model_diagram.png"

# Colours sampled from the original artwork so the new figure matches it.
# Colour is semantic in this figure and the caption depends on it:
#   GREEN = the claim is answered on the device
#   RED   = the claim is sent to the cloud
#   BLACK = pipeline flow, with the outcome not yet decided
GREEN = "#28734f"
RED = "#8b4f56"
INK = "#111111"
PAPER = "white"
FONT = "Helvetica"

W, H = 118.0, 48.0      # data units; the figure is saved at 30 px per unit

# ONE size for every piece of text in the figure, node labels and edge labels alike.
# At width=\textwidth on a 5.5in NeurIPS page this lands at about 4.9pt.
SIZE = 10.5
plt.rcParams["font.family"] = FONT

LW = 1.3                # every line in the figure
HEAD = 9                # arrowhead size

fig, ax = plt.subplots(figsize=(W / 10, H / 10))
ax.set_xlim(0, W); ax.set_ylim(0, H)
ax.set_aspect("equal"); ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)

# --- node positions ---------------------------------------------------------
# One column per pipeline stage. The two new components get their own column
# between the gate and the cloud model, on the two branches the gate produces.
P = {
    "claim":    (7.0, 43.5),
    "filing":   (7.0, 21.0),
    "bm25":     (17.5, 21.0),
    "chunks":   (28.0, 21.0),
    "numeric":  (38.5, 21.0),
    "qwen3b":   (51.0, 34.0),
    "qwen7b":   (51.0, 8.0),
    "gate":     (62.5, 21.0),
    "arbiter":  (75.0, 34.0),
    "audit":    (75.0, 8.0),
    "whale":    (91.0, 21.0),
    "verdict":  (106.5, 21.0),
}
# Icon heights in data units, chosen so every icon reads at the same visual weight.
# The verdict bar is sized by WIDTH instead, because it is a wide label and not an icon.
ICON_H = {"claim": 4.6, "filing": 6.0, "bm25": 5.6, "chunks": 10.5, "numeric": 5.6,
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
            color=INK, linespacing=1.4)


def edge_label(x, y, text, color=INK, ha="center", va="center"):
    ax.text(x, y, text, ha=ha, va=va, fontsize=SIZE, color=color, linespacing=1.4)


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


# --- the two new icons, drawn rather than cropped ----------------------------
def draw_gavel(cx, cy, s=1.0):
    """Arbiter. A gavel: head, handle, sounding block."""
    import math
    ang = -40

    def R(px, py):
        a = math.radians(ang)
        return (cx + (px * math.cos(a) - py * math.sin(a)) * s,
                cy + (px * math.sin(a) + py * math.cos(a)) * s)

    # handle, running down-left from under the head
    ax.add_patch(Polygon([R(-0.36, -3.05), R(0.36, -3.05), R(0.36, 0.35), R(-0.36, 0.35)],
                         closed=True, facecolor=INK, edgecolor="none", zorder=5))
    # head, a thick bar across the top of the handle
    ax.add_patch(Polygon([R(-1.65, 0.45), R(1.65, 0.45), R(1.65, 2.15), R(-1.65, 2.15)],
                         closed=True, facecolor=INK, edgecolor="none", zorder=6))
    # sounding block
    ax.add_patch(FancyBboxPatch((cx - 2.45 * s, cy - 3.45 * s), 4.9 * s, 1.05 * s,
                                boxstyle="round,pad=0,rounding_size=0.35",
                                facecolor=INK, edgecolor="none", zorder=5))


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
for n in ("claim", "filing", "bm25", "chunks", "numeric", "qwen3b", "qwen7b",
          "gate", "whale", "verdict"):
    put_icon(n)
draw_gavel(*P["arbiter"], s=1.05)
draw_checklist(*P["audit"], s=1.05)

node_label("claim", "Claim")
node_label("filing", "10K Filing\n(~41k words)")
node_label("bm25", "BM25\nRetriever")
node_label("chunks", "Retrieved\nChunks")
node_label("numeric", "Numeric\nDetector")
node_label("qwen3b", "Qwen 2.5\nCoder 3B")
node_label("qwen7b", "Qwen 2.5\nCoder 7B")
node_label("gate", "Verification\nGate")
node_label("arbiter", "Arbiter", dy=-5.0)
node_label("audit", "Audit", dy=-4.5)
node_label("whale", "DeepSeek\nV4 Flash")

GAP = 1.2        # breathing room between an icon edge and an arrow end
MID = 21.0       # the spine the pipeline runs along
TRUNK = P["claim"][1]   # the lane the claim travels along to reach its two readers
TOP = 39.0       # the lane the numeric escalation runs along
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
       (P["whale"][0], TOP), (P["whale"][0], P["whale"][1] + half("whale", "h") + GAP)],
      color=RED)
edge_label(RISE + 1.1, 33.5, "Yes", color=RED, ha="left")

# every other claim goes to the two local arms
for arm, sgn in (("qwen3b", 1), ("qwen7b", -1)):
    arrow((P["numeric"][0] + half("numeric") + 0.5, MID + 1.5 * sgn),
          (P[arm][0] - half(arm) - GAP, P[arm][1] - 2.6 * sgn))
edge_label(45.0, MID, "No")

# the two local arms -> the gate
for arm, sgn in (("qwen3b", 1), ("qwen7b", -1)):
    arrow((P[arm][0] + half(arm) + GAP, P[arm][1] - 2.6 * sgn),
          (P["gate"][0] - half("gate") - GAP, MID + 2.0 * sgn))

# The gate splits into the two new components. Both branches are black: the gate has
# routed the claim but has not decided where it will be answered.
arrow((P["gate"][0] + half("gate") + GAP, MID + 1.8),
      (P["arbiter"][0] - 3.6, P["arbiter"][1] - 2.8))
edge_label(67.6, 28.4, "Disagree", va="bottom")
arrow((P["gate"][0] + half("gate") + GAP, MID - 1.8),
      (P["audit"][0] - 3.6, P["audit"][1] + 2.8))
edge_label(67.6, 13.6, "Agree", va="top")

# Each new component either escalates to the cloud or answers on the device.
arrow((P["arbiter"][0] + 3.4, P["arbiter"][1] - 2.2),
      (P["whale"][0] - half("whale") - GAP, P["whale"][1] + 3.0), color=RED)
edge_label(84.0, 26.4, "Sides with 3B", color=RED, va="top")

arrow((P["audit"][0] + 3.4, P["audit"][1] + 2.2),
      (P["whale"][0] - half("whale") - GAP, P["whale"][1] - 3.0), color=RED)
edge_label(83.5, 15.6, "Unconfirmed", color=RED, va="bottom")

# The on-device answers return along their own column to the verdict. The arbiter's
# return is the one line in the figure that another line crosses, so it is broken
# where the numeric escalation passes over it.
CROSS = P["whale"][0]
line((P["arbiter"][0] + 3.4, P["arbiter"][1]), (CROSS - 1.0, P["arbiter"][1]), color=GREEN)
line((CROSS + 1.0, P["arbiter"][1]), (RET, P["arbiter"][1]), color=GREEN)
arrow((RET, P["arbiter"][1]), (RET, MID + vh + GAP), color=GREEN, shrinkA=0)
edge_label(84.0, P["arbiter"][1] + 1.0, "Keeps 7B", color=GREEN, va="bottom")

elbow([(P["audit"][0] + 3.4, P["audit"][1]), (RET, P["audit"][1]),
       (RET, MID - vh - GAP)], color=GREEN)
edge_label(84.0, P["audit"][1] - 1.0, "Confirmed", color=GREEN, va="top")

# the cloud model answers
arrow((P["whale"][0] + half("whale") + GAP, MID), (P["verdict"][0] - vw - GAP, MID))

# imshow resets limits and aspect, so restore them before saving
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
fig.savefig(OUT, dpi=300, facecolor=PAPER)
print("wrote", OUT)
