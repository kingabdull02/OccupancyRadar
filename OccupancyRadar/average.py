import numpy as np
import pandas as pd

input_csv = "data/BackgroundTest2.csv"
output_csv = "data/avg_background2.csv"

def compute_background_average(input_csv, output_csv):
    data = pd.read_csv(input_csv, sep=",")
    
    values = data["raw"].apply(lambda x: [int(v) for v in str(x).split()]).tolist()
    values = np.array(values)
    
    num_frames = values.shape[0]
    num_bins = 20 * 16
    
    if values.shape[1] != num_bins:
        raise ValueError(f"Expected 320 values per frame, got {values.shape[1]}")
    
    rd_maps = values.reshape(num_frames, 20, 16)
    avg_background = np.mean(rd_maps, axis=0)
    
    pd.DataFrame(avg_background).to_csv(output_csv, header=False, index=False)
    print(f"Average background saved to {output_csv}")

if __name__ == "__main__":
    compute_background_average(input_csv, output_csv)
