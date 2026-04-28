# AI Guide: CranePdM Project

This document provides context and instructions for AI assistants working on the CranePdM project.

## Project Overview
CranePdM (Crane Predictive Maintenance) is a Python-based project for monitoring and diagnosing crane components, specifically focusing on Gantry operations. It uses the Siemens S7 protocol via `snap7` to communicate with PLCs.

## Key Files
- `check_gantry_speed.py`: Script to check the Gantry Order Speed. Connects to PLC at 10.200.72.34 (Slot 2). Reads Order Speed from MW450.

## Configuration
- **Visual Studio Code**: Recommended editor.
- **Python**: Version 3.x required.
- **Dependencies**: `python-snap7`.
- **Operating System**: Windows.

## PLC Details
- **Type**: Siemens S7-300 (Simulated or Real).
- **Ip Address**: `10.200.72.34` (Default for Gantry).
- **Rack**: 0 (Default).
- **Slot**: 2 (Default for S7-300).

## Function Blocks
- **Gantry Control**:
  - **Order Speed**: `DB57.DBW8` (Type: INT - Represents commanded speed reference)
- **Feedback Speed**: `DB57.DBW10` (Type: INT - Represents actual measured speed)
- **Total Load**: `DB57.DBW48` (Type: INT - Payload Weight)
- **Twistlock (Locked/Loaded)**: `DB58.DBX185.1` (Type: BOOL - 1=Locked)
- **Twistlock (Unlocked/Empty)**: `DB58.DBX185.2` (Type: BOOL - 1=Unlocked)

#### Spreader Landing Faults
- **Land Fault_YD**: `DB59.DBX202.5` (Type: BOOL)
- **Land Fault_XT**: `DB59.DBX202.3` (Type: BOOL)
- **Land Fault_YT**: `DB59.DBX202.4` (Type: BOOL)
- **SPSS Trolley Dir Not Clear**: `DB59.DBX212.6` (Type: BOOL)
- **Fault Reset**: `M103.2` (Type: BOOL - Memory Marker)

## Objectives
1.  **Monitor Gantry Speed**:
    - **Order Speed**: DB57.DBW8 (Confirmed)
    - **Feedback Speed**: DB57.DBW10 (Confirmed)
3.  **Expand Monitoring**: Add more checks for other components as needed.

## Conventions
- Use meaningful variable names (e.g., `gantry_order_speed`, `plc_client`).
- Include Korean comments for clarity where appropriate.
- Ensure proper error handling for PLC connections.

## Data Integrity & Safety Rules
- **DO NOT Modify CSV Logs**: The file `crane_kpi_log.csv` is the project's source of truth. It must NEVER be edited, truncated, or modified directly.
- **Non-Destructive Correction**: Data normalization or scaling corrections (e.g., handling historical scale shifts) must be implemented at the **Query/Visualization level** (Grafana Flux) or by creating **new projection measurements**.
- **No Direct DB Overwrites**: Never perform bulk deletes or overwrites on the `cranepdm_kpis` bucket without explicit user approval and a verified backup strategy.
- **Audit Trail**: Any script that performs data maintenance must log its actions to a separate log file, never overwriting the primary `crane_kpi_log.csv`.
