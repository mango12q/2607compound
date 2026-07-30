"""
figures.py — Generate all paper figures (Phase 4: Visualization)
"""
import os
import sys

from config import FIGURES_DIR


def main():
    print("=" * 60)
    print("Generating all paper figures...")
    print("=" * 60)

    os.makedirs(FIGURES_DIR, exist_ok=True)

    # Figure 1: compound spatial + time-series + co-occurrence prob
    print("\n[1/2] Figure 1 — Compound events spatial & time-series...")
    from fig1_compound_spatial import plot_figure1
    path1 = plot_figure1(FIGURES_DIR)

    # Figure 2: CHR analysis
    print("\n[2/2] Figure 2 — CHR analysis...")
    from fig2_chr import plot_figure2
    path2 = plot_figure2(FIGURES_DIR)

    print("\n" + "=" * 60)
    print(f"All figures generated in: {FIGURES_DIR}")
    print(f"  {path1}")
    print(f"  {path2}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
