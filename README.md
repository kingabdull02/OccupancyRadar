# OccupancyRadar – Radar-Based People Counting

Real-time people-counting using a 24GHz radar sensor and machine learning.

## How it works

- ESP32 microcontroller collects radar data as Range-Doppler matrix frames
- Background subtraction filters out static objects
- 24 features extracted per frame for classification
- XGBoost classifier predicts number of people present
- Data logged to CSV for training and evaluation

## Tech Stack

- Python
- XGBoost
- ESP32 (24GHz radar sensor)
- CSV logging
