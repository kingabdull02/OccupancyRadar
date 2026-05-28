import sysconfig
import sys
import os
import importlib
import numpy as np
from scipy.stats import entropy
from scipy.signal import savgol_filter, find_peaks

"""
Extract statistical and spatial features from radar range-Doppler maps.

This module processes CSV files containing raw radar data and computes
a comprehensive set of features for occupancy detection or classification.
Features include energy metrics, spatial distributions, peak characteristics,
and doppler analysis.
"""

# Radar dimensions
DOPPLER_BINS = 20
RANGE_BINS = 16

# File paths (change as needed)
INPUT_CSV  = "data/subtracted2.csv"
OUTPUT_CSV = "data/radar_features.csv"

def _import_stdlib(name):
    """Import a module from the standard library, avoiding local conflicts."""
    stdlib_path = sysconfig.get_paths().get("stdlib")
    if not stdlib_path or not os.path.isdir(stdlib_path):
        raise ImportError("Cannot locate stdlib path")
    script_dir = os.path.abspath(os.path.dirname(__file__))
    removed = False
    try:
        if script_dir in sys.path:
            sys.path.remove(script_dir)
            removed = True
        module = importlib.import_module(name)
    finally:
        if removed:
            sys.path.insert(0, script_dir)
    return module

csv = _import_stdlib("csv") #We have a local csv.py, so import stdlib version

def _extract_features(rdmap, eps=1e-9):
    """
    Extract features from a range-Doppler map.

    Args:
        rdmap: Flat array of 320 values (20 Doppler bins × 16 Range bins).
        eps: Small epsilon to prevent division by zero.

    Returns:
        Dictionary of computed features.
    """
    rd = np.asarray(rdmap, dtype=np.float64).reshape(DOPPLER_BINS, RANGE_BINS)
    H, W = rd.shape

    total = rd.sum()
    mean = rd.mean()
    mx = rd.max()

    base = np.median(rd)
    mad = np.median(np.abs(rd - base)) + eps
    thresh = base + 3 * 1.4826 * mad
    mask = rd > thresh
    active = int(mask.sum())

    doppler_sum = rd.sum(axis=1)
    range_sum   = rd.sum(axis=0)

    var_d = np.var(doppler_sum)
    var_r = np.var(range_sum)
    var_d_norm = np.var(doppler_sum / (doppler_sum.sum() + eps))
    var_r_norm = np.var(range_sum / (range_sum.sum() + eps))

    p = rd.flatten() / (total + eps)
    ent = entropy(p + eps)

    flat = rd.flatten()
    top = np.sort(flat)[-5:][::-1]
    peak_ratio_12 = (top[0] / (top[1] + eps)) if top.size >= 2 else 0.0
    energy_top5_ratio = top.sum() / (total + eps)

    range_idxs = np.where(mask.any(axis=0))[0]
    doppler_idxs = np.where(mask.any(axis=1))[0]
    width_range = (range_idxs.max() - range_idxs.min()) if range_idxs.size else 0
    width_doppler = (doppler_idxs.max() - doppler_idxs.min()) if doppler_idxs.size else 0
    doppler_width_rel = width_doppler / max(H - 1, 1)

    rs_smooth = savgol_filter(range_sum, window_length=min(7, max(5, W//10)|1), polyorder=2, mode="interp")
    peaks, props = find_peaks(rs_smooth, prominence=rs_smooth.max()*0.05)
    num_range_peaks = len(peaks)
    if num_range_peaks >= 2:
        order = np.argsort(props["prominences"])[-2:]
        pidx = peaks[order]
        distance_top2 = int(abs(pidx[1] - pidx[0]))
    else:
        distance_top2 = 0

    mid = H // 2
    doppler_pos_frac = doppler_sum[mid:].sum() / (doppler_sum.sum() + eps)

    return {
        "total_energy": total,
        "mean_energy": mean,
        "max_energy": mx,
        "active_cells": active,
        "var_range": var_r,
        "var_doppler": var_d,
        "var_range_norm": var_r_norm,
        "var_doppler_norm": var_d_norm,
        "entropy": ent,
        "top1": top[0] if top.size>0 else 0,
        "top2": top[1] if top.size>1 else 0,
        "top3": top[2] if top.size>2 else 0,
        "top4": top[3] if top.size>3 else 0,
        "top5": top[4] if top.size>4 else 0,
        "peak_ratio_12": peak_ratio_12,
        "number_of_range_peaks": num_range_peaks,
        "distance_between_top2_range_peaks": distance_top2,
        "std_range_sum": float(np.std(range_sum)),
        "std_doppler_sum": float(np.std(doppler_sum)),
        "width_range": int(width_range),
        "width_doppler": int(width_doppler),
        "doppler_width_rel": float(doppler_width_rel),
        "energy_top5_ratio": float(energy_top5_ratio),
        "doppler_pos_frac": float(doppler_pos_frac),
    }

def _process_csv(input_path, output_path):
    """
    Process radar CSV and extract features for each frame.

    Args:
        input_path: Path to input CSV with 'timestamp' and 'raw' columns.
        output_path: Path to output CSV with extracted features.
    """
    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_path}")

    with open(input_path, mode="r", encoding="utf-8") as f_in, \
         open(output_path, mode="w", newline="", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        
        #Generate fieldnames from a dummy feature extraction
        fieldnames = ["timestamp"] + list(_extract_features(np.zeros(DOPPLER_BINS*RANGE_BINS)).keys())
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        count = 0
        for row in reader:
            timestamp = row["timestamp"]
            values = list(map(float, row["raw"].split()))
            feats = _extract_features(values)
            feats["timestamp"] = timestamp
            writer.writerow(feats)
            count += 1

    print(f"Processed {count} frames successfully.")

if __name__ == "__main__":
    _process_csv(INPUT_CSV, OUTPUT_CSV)