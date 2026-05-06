#!/bin/bash

cd ~/Desktop/spesa\ jack

streamlit run dashboard.py --server.headless true &

sleep 5

open -a "Google Chrome" http://localhost:8501