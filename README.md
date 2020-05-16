# dem2dged

Conversion of elevation data from any GDAL raster source to DGED tiles
## What is it?

DGED (Defense Gridded Elevation Data) is a product implementation profile from [DGIWG](https://www.dgiwg.org/dgiwg/) (Defense Geospatial Information Working Group). In layman's words it is an instruction on how to package elevation data for military - and civlian - purposes (I will refer to DGED as "the spec" for convenience below). DGED sets forth rules on existing formats, ie GMLJP2, NSIF and GeoTIFF - the options are narrowed down thus allowing a more smooth import/export of data. This is a small tool to convert a raster elevation dataset to a set of DGED tiles. At present only UTM and GeoTiff tiles are supported.

UTM: There are some limitations. The DGED spec is quite elaborate and allows for a lot of options. These are further narrowed down in this implementation. For instance the no-data value is fixed, the tile size has been pre-chosen to the smallest size. If there are features you need for your project, let me know. Tiles are generated with the dem2dged_utm.py script.

GEO: So far not supported.

THIS PROJECT IS VERY VERY BETA! USE AT OWN RISK

## Running the script

The script is executed from python 3:

```
python dem2dged_utm.py -product_level 4 test.tif product_folder
```

The line above will autodetect a suitable UTM projection and generate a set of geotiff files and accompanying xml metadata files.


### Positional arguments:

input_raster: Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)

output_folder: Output path to the generated product

### Optional arguments:
  -utm_zone: zone for output utm (must be three letters e.g. '32N' or '09S'). If not stated, zone will be autodetected based on input raster)

  -product_level: For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5, GSD = 2 m)

  -xml_template: Template for sidecar xml file. Default to DGED_TEMPLATE.xml included in project

  -verbose: Show additional output

### Example

```
python dem2dged_utm.py -product_level 4b -utm_zone 32N -xml_template custom_template.xml test.tif product_folder -verbose
```
The above example will create a series of UTM Level 4b files in UTM 32N (epsg:32632). A custom template is being used instead of the included one. All files are dumped in a folder named "product_folder" and the -verbose flag ensures all relevant debug info is echoed to the terminal.


## Installation

Install anaconda and create an environment:

```
conda create --name DGED --channel conda-forge gdal git
```

activate the environment:
```
conda activate DGED
```

That's it

Run the conversion tool with the included example with the command:

```
python dem2dged_utm.py -product_level 4 test.tif dged_output
```

This will create a folder "dged_output" with a set of tiles.

## Acknowledgement

This work is based on the DGED Product Implementation Profile which can be downloaded [here](https://www.dgiwg.org/dgiwg/htm/documents/standards_implementation_profiles.htm)

The included template.xml is based on the DGED sample package from DGIWG (technically part of the spec).

The included test.tif is from the Danish Elevation Model (DHM) and part of the public basic data programme. Data can be downloaded from [Kortforsyningen](https://download.kortforsyningen.dk)
