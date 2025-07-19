# ForeFlight Content Pack Generator

This document describes the functionality of the `foreflight.py` script.

## Overview

The `foreflight.py` script supports multiple commands:

1. **`airports`** (default): Creates ForeFlight content packs from the euro_aip database
2. **`approach`**: Creates custom approach packs from Excel definition files

## Commands

### Airports Command (Default)

Creates ForeFlight content packs from the euro_aip database.

```bash
# Create airports pack (default)
python example/foreflight.py pack_name

# Explicitly specify airports command
python example/foreflight.py pack_name -c airports

# With options
python example/foreflight.py pack_name -c airports -n -e 180
```

### Approach Command

Creates custom approach packs from Excel definition files.

```bash
# Create approach pack from Excel file
python example/foreflight.py pack_name -c approach

# Specify custom Excel file
python example/foreflight.py pack_name -c approach -x custom_file.xlsx

# Describe waypoints
python example/foreflight.py pack_name -c approach --describe "LFPO,RWY09,FINAL09"

# Increment version
python example/foreflight.py pack_name -c approach -n
```

### Excel File Format

The Excel file must contain two sheets:

#### `navdata` Sheet
Contains waypoint definitions with the following columns:

| Column | Description | Required |
|--------|-------------|----------|
| `Name` | Waypoint identifier | Yes |
| `Latitude` | Initial latitude (decimal degrees) | Yes |
| `Longitude` | Initial longitude (decimal degrees) | Yes |
| `Reference` | Reference waypoint name (empty for base points) | No |
| `Bearing` | Bearing from reference (degrees) | No |
| `Distance` | Distance from reference (nautical miles) | No |
| `Include` | Include in output (1=yes, 0=no) | Yes |
| `Description` | Waypoint description | No |

#### `byop` Sheet (Build Your Own Procedure)
Contains procedure definitions:

| Column | Description |
|--------|-------------|
| `Procedure` | Procedure name |
| `Type` | Procedure type (approach, departure, arrival) |
| `Runway` | Associated runway |
| `Description` | Procedure description |

### Example

```python
# Create example Excel file
python example/approach_pack_example.py

# Generate approach pack
python example/foreflight.py example_approach -c approach
```

This will create:
- `example_approach/` directory
- `example_approach/manifest.json` - ForeFlight manifest
- `example_approach/navdata/example_approach.csv` - Waypoint data
- `example_approach_updated.xlsx` - Updated Excel with calculated coordinates

### Coordinate Calculation

The system uses the `NavPoint` model for all coordinate calculations:

- **Great Circle Calculations**: Uses Haversine formula for accurate navigation
- **Relative Positioning**: Calculates waypoints from reference points using bearing/distance
- **Coordinate Formats**: Supports decimal degrees, DMS, and DM formats
- **Validation**: Checks calculated coordinates against provided values

### Output Files

1. **Content Pack Directory**: Contains all files needed for ForeFlight import
2. **Updated Excel**: Original file with calculated coordinates and additional format columns
3. **CSV File**: Waypoint data in ForeFlight format
4. **Manifest**: ForeFlight content pack metadata

### Integration with NavPoint Model

The approach pack functionality leverages the existing `NavPoint` model:

- Uses `point_from_bearing_distance()` for coordinate calculations
- Uses `haversine_distance()` for validation and distance calculations
- Uses `to_dms()` and `to_dm()` for coordinate format conversion
- Uses `to_csv()` for output formatting

### Error Handling

- Validates Excel file existence and format
- Checks for required sheets and columns
- Warns about calculation discrepancies
- Reports failed coordinate calculations
- Graceful handling of missing reference waypoints

### Dependencies

Additional dependencies for approach pack mode:
- `pandas` - Excel file processing
- `openpyxl` - Excel file reading/writing

Install with:
```bash
pip install pandas openpyxl
```

## Extending with More Commands

The command structure is designed to be easily extensible. To add a new command:

1. **Add the command choice** in the argument parser:
   ```python
   parser.add_argument('-c', '--command', choices=['airports', 'approach', 'newcommand'], 
                      default='airports', help='Command to execute (default: airports)')
   ```

2. **Add command logic** in the `run()` method:
   ```python
   def run(self):
       if self.args.command == 'approach':
           self.build_approach_content_pack()
           self.describe_waypoints()
       elif self.args.command == 'newcommand':
           self.build_new_command_pack()
       else:
           self.build_database_content_pack()
   ```

3. **Implement the new method**:
   ```python
   def build_new_command_pack(self):
       """Build a new type of content pack."""
       # Implementation here
       pass
   ```

This structure allows for clean separation of different content pack types while maintaining a unified interface. 