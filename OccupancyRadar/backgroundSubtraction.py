import numpy as np
import pandas as pd

test_csv = "data/2peopleTest2.csv"
background_csv = "data/avg_background2.csv"
output_csv = "data/subtracted2.csv"

def subtract_background(test_csv, background_csv, output_csv):
    test_data = pd.read_csv(test_csv, sep=",")
    
    parsed_rows = []
    timestamps = []
    for idx, (ts, line) in enumerate(zip(test_data["timestamp"], test_data["raw"])):
        tokens = str(line).split()
        if len(tokens) == 320:
            parsed_rows.append([int(v) for v in tokens])
            timestamps.append(ts)
        else:
            print(f"Skipping row {idx}: expected 320 values, got {len(tokens)}")
    
    values = np.array(parsed_rows)
    num_frames = values.shape[0]
    num_bins = 20 * 16
    
    if values.shape[1] != num_bins:
        raise ValueError(f"Expected 320 values per frame, got {values.shape[1]}")
    
    rd_maps = values.reshape(num_frames, 20, 16)
    
    background = pd.read_csv(background_csv, header=None).values
    if background.shape != (20, 16):
        raise ValueError("Background CSV must be 20x16.")
    
    subtracted = rd_maps - background    
    subtracted = np.clip(subtracted, a_min=0, a_max=None)
    subtracted_flat = subtracted.reshape(num_frames, -1)
    
    output_df = pd.DataFrame({
        "timestamp": timestamps,
        "raw": [" ".join(map(str, row)) for row in subtracted_flat]
    })
    
    output_df.to_csv(output_csv, index=False)
    print(f"Background-subtracted data saved to {output_csv}")
    print(f"Frames processed: {num_frames}")

if __name__ == "__main__":
    subtract_background(test_csv, background_csv, output_csv)