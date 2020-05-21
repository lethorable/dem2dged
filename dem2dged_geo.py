import argparse
import os,sys
import math
from osgeo import gdal,ogr,osr
import subprocess
import datetime
import dem2dged_lib as dl

parser = argparse.ArgumentParser(description="Convert a DEM to DGED GEO. The script reads a GDAL raster source and based on user input creates a set of tiles compatible with DGIWG/DGED")
parser.add_argument("input_raster", help="Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)")
parser.add_argument("output_folder", help="Output path to the generated product")
parser.add_argument("-product_level",dest="product_level",help="For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5, GSD ~ 2 m)",default="5")
parser.add_argument("-xml_template",dest="xml_template",help="Template for sidecar xml file. Default to DGED_GEO_TEMPLATE.xml included in project",default="DGED_GEO_TEMPLATE.xml")
parser.add_argument("-verbose",action="store_true",help="Show additional output")

"""
This script converts a raster elevation data source to GEO DGED. The specification can be found here: https://www.dgiwg.org/dgiwg/htm/documents/standards_implementation_profiles.htm
The project resides on github: https://github.com/lethorable/dem2dged - please observe the license in the repository

Hvidovre, Copenhagen 2020. Thorbjoern Nielsen
"""


def resolve_lon_multiplication(minx):
    """
    Longitude post distance is a function of latitude. Table 3, page 12 gives the relation.
    """
    multi = 1
    aktmin = -99999
    for l in dl.zone_lon_spacing:
        if minx >=l[1]:
            aktmin = l[1]
            multi = l[4]
    return multi

def resolve_level_geo(lvl):
    """
    The level determines the latitude resolution. For convenience the tile size is handled at the same time. The DGED spec offers various options.
    The smallest has been chosen here, but it is fairly easy ti adjust the array 'level_tilesize_and_spatial_resolution' to accomodate larger tiles.
    Refer to Table 7 page 24 in the DGED spec for other sizes
    """
    tile_size = 60 #level 2
    geo_res = 1
    for l in dl.level_tilesize_and_spatial_resolution:
        if l[0]==lvl:
            tile_size = l[1] /(60) #unit in table is minutes of arc
            geo_res = l[2] / (60*60) #here it's seconds
    return tile_size, geo_res

def main(args):
    my_out_srs = 4326 #we will hardcode this here - constant for this product
    pargs = parser.parse_args(args[1:])
    dl.debug = pargs.verbose #if verbose is set, output will be printed using the dl.dp() funcion

    #create output folder if it does not exist
    if not os.path.exists(pargs.output_folder):
        os.makedirs(pargs.output_folder)

    template = dl.read_sidecar_template(pargs.xml_template) #The template is read. Keywords are marked with {{KEYWORD}}

    my_in_ext = dl.get_extent_and_srs_of_input_raster(pargs.input_raster)

    minx, maxx, miny, maxy = dl.get_bbox_of_output(my_in_ext,my_out_srs)

    dl.dp ("bounding box for output has been calculated to %s %s %s %s " %(minx, maxx, miny, maxy)) #Returns N, E

    tiledim, latres = resolve_level_geo(pargs.product_level)
    dl.dp ("tile dimension %s " %tiledim)
    dl.dp ("longitude resolution %s" %latres)

    #Determine iteration bounds. We need to take extra care (compared to UTM) as the input dataset may cross a critical latitude
    ilon_start = math.floor(miny/tiledim)
    ilon_end   = math.floor(maxy/tiledim)+1
    ilat_start = math.floor(minx/tiledim)
    ilat_end   = math.floor(maxx/tiledim)+1

    numdone = 0
    numfiles = (ilon_end-ilon_start)*(ilat_end-ilat_start)
    for yy in range(ilat_start, ilat_end):
        for xx in range(ilon_start, ilon_end):
            numdone = numdone +1
            percentage = int(100*numdone/numfiles)
            minlat = yy    * (tiledim)
            lonres = resolve_lon_multiplication(minlat) * latres
            maxlat = (yy+1) * (tiledim) + latres

            maxlon = (xx+1) * (tiledim) + lonres#hanging pixel
            minlon = xx      * (tiledim)

            dl.dp ("%s %s %s %s "%(minlon, maxlon, minlat, maxlat))
            basename = "DGEDL%sG_%s_%s" %(pargs.product_level,int(minlon*100000),int(minlat*100000)) #should this be invoked from command line?
            namnam = os.path.join(pargs.output_folder,basename+'.tif')
            xmlnam = os.path.join(pargs.output_folder,basename+'.xml')

            if os.path.isfile(xmlnam):
                print("file %s already exists, continuing (consider to delete before running)" %(xmlnam)) #maybe an option - overwrite or continue? As it is now it allows to continue of the process breaks.
                continue

            dl.dp(" ")
            dl.dp("-"*70)
            dl.dp("Creating elevation raster %s" %(namnam))
            cmdstr = """gdalwarp -t_srs EPSG:%s+3855 -te %s %s %s %s -dstnodata -32767 -tr %s %s -r cubic -co COMPRESS=LZW --config GTIFF_REPORT_COMPD_CS YES %s %s""" %(my_out_srs, minlon, minlat, maxlon, maxlat, lonres, latres, pargs.input_raster, namnam )
            dl.dp (cmdstr)
            dl.run_cmd(cmdstr)
            dl.dp("Adjusting tiff header")
            cmdstr = """python gdal_edit.py --config GTIFF_REPORT_COMPD_CS YES -a_srs epsg:%s+3855 -mo AREA_OR_POINT=POINT %s""" %(my_out_srs,namnam)
            dl.dp (cmdstr)
            dl.run_cmd(cmdstr)
            dl.dp("creating sidecar metadata file")
            dl.write_sidecar_file(template, xmlnam,basename,pargs.product_level,lonres,"EPSG:"+str(my_out_srs)) #lonres input as dummy - not used for GEO
            dl.dp("-"*70)
            dl.dp(" ")
            print ("%s %% done " %(percentage))
    print("All done!")

if __name__ == "__main__":
    sys.exit(main(sys.argv))
