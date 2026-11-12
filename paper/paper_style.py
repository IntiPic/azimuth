"""Local publication style; never update global matplotlib rcParams."""

import matplotlib as mpl

# Okabe-Ito colors, reinforced by different marker shapes.
ORIENTATIONS = {
    0.0: ("#0072B2", "o"),
    10.0: ("#D55E00", "s"),
    20.0: ("#009E73", "^"),
    30.0: ("#CC79A7", "D"),
    40.0: ("#E69F00", "P"),
    50.0: ("#56B4E9", "v"),
    60.0: ("#000000", "X"),
}
BLUE = "#0072B2"
ORANGE = "#D55E00"


def paper_context():
    # Reset inherited style inside a context, including text.usetex and grids.
    settings = dict(mpl.rcParamsDefault)
    settings.pop("backend", None)
    settings.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.0,
        "mathtext.fontset": "dejavusans",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.dpi": 300,
        "savefig.facecolor": "white",
    })
    return mpl.rc_context(rc=settings)
