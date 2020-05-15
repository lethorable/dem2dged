# dem2dged

Conversion of elevation data from any GDAL raster source to DGED tiles
## What is it?

This is a small tool to convert a raster elevation dataset to a set of DGED tiles. At present only UTM tiles are supported.

UTM: There are some limitations. The DGED spec is quite elaborate and allows for a lot of options. These are narrowed down in this implementation. For instance the no-data value is fixed, the tile size has been pre-chosen to the smallest size. If there are features you need for your project, let me know. Tiles are generated with the dem2dged_utm.py script.

GEO: So far not supported.

THIS PROJECT IS VERY VERY BETA! USE AT OWN RISK

## Running the description

### positional arguments:

input_raster: Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)

output_folder: Output path to the generated product

### optional arguments:
  -utm_zone: zone for output utm (must be three letters e.g. '32N' or '09S'). If not stated, zone will be autodetected based on input raster)

  -product_level: For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5, GSD = 2 m)

  -xml_template: Template for sidecar xml file. Default to DGED_TEMPLATE.xml included in project

  -verbose: Show additional output



## Installation

Install anaconda and create an environment:

conda create --name DGED --channel conda-forge gdal git

activate the environment. That's it

Run the conversion tool with the included example with the command:

python dem2dged_utm.py -product_level 4 test.tif delete

This will create a folder "delete" with a set of tiles.

## Acknowledgement

The included template.xml is based on the DGED sample package from DGIWG (technically part of the spec).
The included test.tif is from the Danish Elevation Model (DHM) and part of the public basic data programme.
