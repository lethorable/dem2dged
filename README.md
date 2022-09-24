# dem2dged

Conversion of elevation data from any GDAL raster source to DGED tiles

## What is it?

This is a tool to convert a raster elevation dataset to a set of DGED GeoTIFF tiles.

DGED (Defense Gridded Elevation Data) is a product implementation profile from [DGIWG](https://www.dgiwg.org) (Defense Geospatial Information Working Group). In layman's terms it is an instruction on how to package elevation data for military purposes (I will refer to DGED as "the spec" for convenience below). The DGED spec can be downloaded [here](https://www.dgiwg.org/dgiwg-standards/250). **It is highly recommended to read the spec before using these scripts.**

DGED sets forth rules on existing formats, ie GMLJP2, NSIF and GeoTIFF - the options are narrowed down thus allowing a more smooth import/export of data between systems. DGED will replace DTED as the main media for elevation data exchange.

Though the DGED spec is already a narrow representation of the possibilities within GeoTiff, GMLJP2 and NSIF it is still quite elaborate and allows for a lot of options. These are further narrowed down in this implementation. For instance the no-data value is fixed, the tile size has been pre-chosen to the smallest size within a product level and certain values are hardcoded. If there are features you need for your project, let me know.

**_THIS PROJECT IS VERY MUCH BETA! USE AT OWN RISK - ABSOLUTELY NO WARRANTY_**
At present it has only been tested on mac(osx) and linux(ubuntu) and not in a production environment. The author takes no responsibility for any damage caused by using these scripts. Refer to the included license.

## Running the script

The scripts works on any GDAL raster source, small or large as long as it has a valid EPSG code defined. The output tiles are sliced into the smallest tile size defined by the spec. If slicing up a large file (e.g. a nationwide vrt) fails due to computer restart, network connection etc. simply just delete the last generated DGED tile and run the script again - it should continue where it left off.

The scripts are executed from python 3:

```
UTM:
python dem2dged_utm.py <input elevation file> <output folder> <optional arguments>

GEO:
python dem2dged_geo.py <input elevation file> <output folder> <optional arguments>
```
Using the dem2dged_utm.py command above will autodetect a suitable UTM projection and generate a set of geotiff files and accompanying xml metadata files in UTM. Using dem2dged_geo will generate a set of geotiff files in wgs84 (EPSG:4326)

### Positional arguments:

`input_raster`: Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)

`output_folder`: Output path to the generated product

### Optional arguments:

`-product_level`: For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5 resulting in a GSD of respectively 2m (UTM) and 0.06 arcsec lat (GEO))

`-xml_template`: Template for sidecar xml file. Default to DGED_GEO_TEMPLATE.xml and DGED_UTM_TEMPLATE.xml included in project

`-source_type`: Source type code must be a letter according to the DGED specification (default is A = optical unedited reflective surface)

`-security_class`: Security classification must be T, S, C, R or U (default is U)

`-product_version`: Product version must be a 2 digits code (default is 01)

`-verbose`: Show additional output

For dem2dged_utm.py specifically:

`-utm_zone`: zone for output utm (must be three letters e.g. '32N' or '09S'). If not stated, zone will be autodetected based on input raster)


### Examples

```
python dem2dged_utm.py -product_level 4b -utm_zone 32N -xml_template custom_utm_template.xml test.tif product_folder -verbose
```

The above example will create a series of UTM Level 4b files in UTM 32N (epsg:32632). A custom template is being used instead of the included one. All files are dumped in a folder named "product_folder" and the -verbose flag ensures all relevant debug info is echoed to the terminal.

```
python dem2dged_geo.py -product_level 6 -xml_template custom_geo_template.xml test.tif product_folder -verbose
```

Here a set of DGED tiles in the GEO format is created. Level 6 is used and the xml is generated from a custom template.

## Installation

Install [Anaconda](https://www.anaconda.com/products/individual) (select the 64 bit with python 3.7). Install and start an anaconda prompt.

Create an environment:

```
conda create --name DGED --channel conda-forge gdal git
```

Activate the environment:
```
conda activate DGED
```

Clone the repo using git:
```
git clone https://github.com/lethorable/dem2dged.git
```

That's it. Now you should have the repository installed in the folder "dem2dged".

Run the conversion tools with the included example with the command:

```
python dem2dged_utm.py test.tif dged_output

or

python dem2dged_geo.py test.tif dged_output
```

This will create a subfolder "dged_output" with a set of tiles.

## Acknowledgement

This work is based on the DGED Product Implementation Profile which can be downloaded [here](https://www.dgiwg.org/dgiwg-standards/250)

The included templates (xml) is based on the DGED sample package from DGIWG (technically part of the spec).

The included test.tif is from the Danish Elevation Model (DHM) and part of the public basic data programme. Data can be downloaded from [Kortforsyningen](https://download.kortforsyningen.dk)

## Known issues

Anaconda/GDAL for windows does not seem to ship with a working copy of gdal_edit. A copy is provided in this project. Test the output with gdalinfo and make sure that `AREA_OR_POINT=Point`.

When generating UTM DGED files for Norway and in particular Svalbard the UTM definition includes some regions in a different zone than the recommended. For these regions don't try to auto detect (default) but use the `-utm_zone` parameter to assign the desired zone.

## The fine print

You are welcome to use and contribute to this work observing the included license.

Hvidovre, Copenhagen 2020 - Thorbjørn Nielsen.
For inquiries, questions etc please reach out at...

t h o r b j o r n  (at) g m a i l (dot) c o m
