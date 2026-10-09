# Laporan Time-Split (Point 2 - AGENTS.md 13)

Fit: < 2026-07-01 (Apr-Jun), Test: >= 2026-07-01 (Jul-Sep).
Threshold dikalibrasi di fit window, dipakai mentah di test.

Threshold fit-window (kuantil): {'monitor': 25.1, 'needs_review': 54.5, 'high_risk': 73.4}

## FIT (Apr-Jun)

| tipe | n | review+high | % |
|---|---|---|---|
| heavy | 14086 | 0 | 0.0% |
| mixed | 1927 | 13 | 0.7% |
| normal | 143427 | 2 | 0.0% |
| normal_collective | 2003 | 1 | 0.0% |
| normal_hard | 4021 | 1 | 0.0% |
| normal_hard_random | 4010 | 0 | 0.0% |
| remote | 9665 | 4 | 0.0% |
| risky | 2067 | 1745 | 84.4% |
| risky_noisy | 5941 | 587 | 9.9% |
| risky_routine | 1983 | 1178 | 59.4% |
| risky_silent | 2054 | 100 | 4.9% |
| risky_silent_shared | 2025 | 234 | 11.6% |

## TEST (Jul-Sep)

| tipe | n | review+high | % |
|---|---|---|---|
| heavy | 14086 | 0 | 0.0% |
| mixed | 1925 | 11 | 0.6% |
| normal | 143472 | 3 | 0.0% |
| normal_collective | 2006 | 0 | 0.0% |
| normal_hard | 4021 | 12 | 0.3% |
| normal_hard_random | 4013 | 0 | 0.0% |
| remote | 9690 | 1 | 0.0% |
| risky | 3489 | 3135 | 89.9% |
| risky_noisy | 5941 | 595 | 10.0% |
| risky_routine | 1984 | 1162 | 58.6% |
| risky_silent | 2054 | 113 | 5.5% |
| risky_silent_shared | 2025 | 274 | 13.5% |
