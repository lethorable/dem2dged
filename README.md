# dem2dged
Conversion of elevation data from any GDAL raster source to DGED tiles

## Installation

Install anaconda and create an environment:

conda create --name DGED --channel conda-forge gdal git

activate the environment. That's it

Run the conversion tool with the included example with the command:

python dem2dged_utm.py -product_level 4 test.tif delete

This will create a folder "delete" with a set of tiles. 
