import argparse
import os,sys
import math
from osgeo import gdal,ogr,osr
import subprocess
import datetime
import dem2dged_lib as dl

debug = False

parser = argparse.ArgumentParser(description="Convert a DEM to DGED UTM. The script reads a GDAL raster source and based on user input creates a set of tiles compatible with DGIWG/DGED")
parser.add_argument("input_raster", help="Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)")
parser.add_argument("output_folder", help="Output path to the generated product")
parser.add_argument("-utm_zone",dest="utm",help="zone for output utm (must be three letters e.g. '32N' or '09S'). If not stated, zone will be autodetected based on input raster)",default="autodetect")
parser.add_argument("-product_level",dest="product_level",help="For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5, GSD = 2 m)",default="5")
parser.add_argument("-xml_template",dest="xml_template",help="Template for sidecar xml file. Default to DGED_UTM_TEMPLATE.xml included in project",default="DGED_UTM_TEMPLATE.xml")
parser.add_argument("-source_type", dest="source_type", help="Source type code must be a letter according to the DGED specification (default is A = optical unedited reflective surface)", default="A")
parser.add_argument("-security_class", dest="sec_class", help="Security classification must be T, S, C, R or U (default is U)", default="U")
parser.add_argument("-product_version", dest="prod_ver", help="Product version must be a 2 digits code (default is 01)", default="01")
parser.add_argument("-verbose",action="store_true",help="Show additional output")



"""
This script converts a raster elevation data source to UTM DGED. The specification can be found here: https://www.dgiwg.org/dgiwg/htm/documents/standards_implementation_profiles.htm
The project resides on github: https://github.com/lethorable/dem2dged - please observe the license in the repository

Hvidovre, Copenhagen 2020. Thorbjoern Nielsen
"""

def resolve_level_utm(lvl):
    """
    The level determines the latitude resolution. For convenience the tile size is handled at the same time. The DGED spec offers various options.
    The smallest has been chosen here, but it is fairly easy ti adjust the array 'level_tilesize_and_spatial_resolution' to accomodate larger tiles.
    Refer to Table 8 page 25 in the DGED spec for other sizes
    """
    gst = 2
    posts = 5001
    tile_size_letter = "D"
    for l in dl.PL:
        if l[0]==lvl:
            gst = l[1]
            posts = l[2]
            tile_size_letter = l[3]
    return gst, posts, tile_size_letter

def get_recommended_srs_for_output(ext):
    """
    If the user does not input a UTM zone (eg, 30N in the -utm_zone parameter)
    the best zone is determined. The UTM zones does not perform as assumed here...
    For instance the western part of Norway and Svalbard would need extra care.
    I will leave this to the norwegians for now :-)

    Returns srs and zone.
    """
    dl.dp("%s %s %s %s " %(ext[0],ext[1],ext[2],ext[3]))
    center_x = (ext[0]+ext[2])/2
    center_y = (ext[1]+ext[3])/2
    my_srs   = ext[4]
    #Transform to wgs84 to do a simple estimate of UTM zone (called zone_ish)
    source = osr.SpatialReference()
    source.ImportFromEPSG(int(my_srs))
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    transform = osr.CoordinateTransformation(source, target)
    #Here Lat Lon if geographic and E N if projected... for some odd reason.
    point = ogr.CreateGeometryFromWkt("POINT (%s %s)" %(center_x,center_y))
    point.Transform(transform)
    dl.dp('GETX and GETY')
    dl.dp (point.GetX())
    dl.dp (point.GetY())
    zone_ish = math.floor((point.GetY() + 180)/6) + 1; #this is not always correct, - Svalbard for instance. Good enough for jazz... use the -utm_zone parameter if working in Norway
    dl.dp ("Zone_ish %s" %(zone_ish))

    if point.GetX()<0:
        NS='7' #eg 32732
    else:
        NS='6' #eg 32632
    my_srs = int("32"+NS+str(zone_ish))
    dl.dp (my_srs)
    return my_srs, zone_ish



def main(args):
    pargs = parser.parse_args(args[1:])
    dl.debug = pargs.verbose #if verbose is set, output will be printed using the dl.dp() funcion
    dl.checkos()
    #create output folder if it does not exist
    if not os.path.exists(pargs.output_folder):
        os.makedirs(pargs.output_folder)

    template = dl.read_sidecar_template(pargs.xml_template) #The template is read. Keywords are marked with {{KEYWORD}}
    my_in_ext = dl.get_extent_and_srs_of_input_raster(pargs.input_raster)
    dl.dp (my_in_ext)
    my_out_srs = 0
    utmzone = pargs.utm
    if pargs.utm == 'autodetect':
        my_out_srs, zone_ish = get_recommended_srs_for_output(my_in_ext)
        if my_out_srs < 32699:
            utmzone = str(my_out_srs - 32600) + "N"
        else:
            utmzone = str(my_out_srs - 32700) + "S"
    else:
        if pargs.utm[2].upper() == 'N': #User input should be XXB
            my_out_srs= int("326"+pargs.utm[:-1]) #UTM N starts with 326
        else:
            my_out_srs= int("327"+pargs.utm[:-1]) #UTM S starts with 327
        zone_ish = int(pargs.utm[:-1])
    gsd, posts, tile_size_letter = resolve_level_utm(pargs.product_level)
    dl.dp ("GSD for output is set to: %s" %(gsd))
    dl.dp ("There are %s posts in the output files " %(posts))
    dl.dp ("EPSG code (srs) has been set to: EPSG:%s" %(my_out_srs))
    minx, maxx, miny, maxy = dl.get_bbox_of_output(my_in_ext,my_out_srs)
    dl.dp ("bounding box for output has been calculated to %s %s %s %s " %(minx, maxx, miny, maxy))
    tiledim = (posts-1)*gsd
    dl.dp ("Tile size is %s m by %s m" %(tiledim, tiledim))

    #Determine iteration bounds
    ix_start = math.floor(minx/tiledim)
    ix_end   = math.floor(maxx/tiledim)+1
    iy_start = math.floor(miny/tiledim)
    iy_end   = math.floor(maxy/tiledim)+1
    numfiles = (ix_end-ix_start)*(iy_end-iy_start)
    numdone = 0
    for yy in range(iy_start, iy_end):
        for xx in range(ix_start, ix_end):
            numdone = numdone +1
            percentage = int(100*numdone/numfiles)

            minx = xx     * (tiledim)
            maxx = (xx+1) * (tiledim) + gsd #hanging pixel
            miny = yy     * (tiledim)
            maxy = (yy+1) * (tiledim) + gsd
#            print ("%s %s %s %s "%(minx, maxx, miny, maxy))
            basename = "DGEDL%sUt%s_%s%s_%s_%s_%s_%s" %(pargs.product_level,tile_size_letter,utmzone,int(miny),int(minx), pargs.source_type, pargs.sec_class, pargs.prod_ver)  #should this be invoked from command line?
            if pargs.product_level in ['4b', '4', '5', '6']:
                basename = "DGEDL%sUt%s_%s%s_%s_%s_%s_%s" %(pargs.product_level,tile_size_letter,utmzone,int(miny/1000),int(minx/1000), pargs.source_type, pargs.sec_class, pargs.prod_ver)
            namnam = os.path.join(pargs.output_folder,basename+'.tif')
            xmlnam = os.path.join(pargs.output_folder,basename+'.xml')

            if os.path.isfile(xmlnam):
                print("file %s already exists, continuing (consider to delete before running)" %(xmlnam))
                continue

            dl.dp(" ")
            dl.dp("-"*70)
            dl.dp("Creating elevation raster %s" %(namnam))
            cmdstr = """gdalwarp -t_srs EPSG:%s+3855 -te %s %s %s %s -dstnodata -32767 -tr %s %s -r cubic -co COMPRESS=LZW --config GTIFF_REPORT_COMPD_CS YES %s %s""" %(my_out_srs, minx, miny, maxx, maxy, gsd, gsd, pargs.input_raster, namnam )
            dl.dp (cmdstr)
            dl.run_cmd(cmdstr)

            dl.dp("Adjusting tiff header")
            cmdstr = """python gdal_edit.py --config GTIFF_REPORT_COMPD_CS YES -a_srs epsg:%s+3855 -mo AREA_OR_POINT=POINT %s""" %(my_out_srs,namnam)
            dl.dp (cmdstr)
            dl.run_cmd(cmdstr)

            dl.dp("creating sidecar metadata file")
            dl.write_sidecar_file(template,xmlnam,basename,pargs.product_level,gsd,"EPSG:"+str(my_out_srs))
            dl.dp("-"*70)
            dl.dp(" ")
            print ("%s %% done " %(percentage))
    print("All done!")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
