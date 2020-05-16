import argparse
import os,sys
import math
from osgeo import gdal,ogr,osr
import subprocess
import datetime

debug = False

parser = argparse.ArgumentParser(description="Convert a DEM to DGED. The script reads a GDAL raster source and based on user input creates a set of tiles compatible with DGIWG/DGED")
parser.add_argument("input_raster", help="Elevation raster. Must be valid gdal source (geotiff, vrt, etc.)")
parser.add_argument("output_folder", help="Output path to the generated product")
parser.add_argument("-utm_zone",dest="utm",help="zone for output utm (must be three letters e.g. '32N' or '09S'). If not stated, zone will be autodetected based on input raster)",default="autodetect")
parser.add_argument("-product_level",dest="product_level",help="For UTM output must be 4b, 4, 5, 6, 7, 8 or 9 (default is level 5, GSD = 2 m)",default="5")
parser.add_argument("-xml_template",dest="xml_template",help="Template for sidecar xml file. Default to DGED_TEMPLATE.xml included in project",default="DGED_TEMPLATE.xml")
parser.add_argument("-gdal_bin",dest="gdal_bin",help="Path to GDAL executables if they are not in system path",default="auto")

parser.add_argument("-verbose",action="store_true",help="Show additional output")

"""
This script converts a raster elevation data source to UTM DGED. The specification can be found here: https://www.dgiwg.org/dgiwg/htm/documents/standards_implementation_profiles.htm
It is very much a work in progress and something I have done in my spare time and as such there are no guarantees.
Feel free to use it in any way desired.

Hvidovre, Copenhagen 2020. Thorbjoern Nielsen
"""




#Array with parameters for the various levels. As for number of posts per tile, the lowest choice is used
#Order is...  level name, GSD, number of posts

PL = []
PL.append(('4b',5,5001))
PL.append(('4',4,6251))
PL.append(('5',2,5001))
PL.append(('6',1,5001))
PL.append(('7',0.5,5001))
PL.append(('8',0.25,5001))
PL.append(('9',0.125,10001))

debug = False

def dp(st):
    if debug:
        print(st)

def resolve_level(lvl):
    gsd = 2
    posts = 5001
    for l in PL:
        if l[0]==lvl:
            gst = l[1]
            posts = l[2]
    return gst, posts

def get_extent_and_srs_of_input_raster(rasras):
    """
    The extent and srs of the input raster is determined using osr.
    If the input is in lat/lon the output is flipped from LAT LON LAT LON to LON LAT LON LAT
    to compensate for inconsistency between the WKT POINT type and GetGeoTransform
    """
    src = gdal.Open(rasras)
    ulx, xres, xskew, uly, yskew, yres  = src.GetGeoTransform()
    lrx = ulx + (src.RasterXSize * xres)
    lry = uly + (src.RasterYSize * yres)
    proj_osgeo = osr.SpatialReference(wkt=src.GetProjection())
    srs=proj_osgeo.GetAttrValue('AUTHORITY',1)
    #inconsistency in coordinate order between GetGeoTransform and E/N vs Lat/Lon handling in WKT. (I assume). Fix here is to switch from Lon lat to lat lon
    if (proj_osgeo.IsGeographic()):
        return uly, ulx, lry, lrx, srs
    else:
        return ulx, uly, lrx, lry, srs


def get_recommended_srs_for_output(ext):
    """
    If the user does not input a UTM zone (eg, 30N in the -utm_zone parameter)
    the best zone is determined. The UTM zones does not perform as assumed here...
    For instance the western part of Norway and Svalbard would need extra care.
    I will leave this to the norwegians for now :-)

    Returns srs and zone.
    """
    dp("%s %s %s %s " %(ext[0],ext[1],ext[2],ext[3]))
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
    dp('GETX and GETY')
    dp (point.GetX())
    dp (point.GetY())
    zone_ish = math.floor((point.GetY() + 180)/6) + 1; #this is not always correct, - Svalbard for instance. Good enough for jazz...
    dp ("Zone_ish %s" %(zone_ish))

    if point.GetX()<0:
        NS='7' #eg 32732
    else:
        NS='6' #eg 32632
    my_srs = int("32"+NS+str(zone_ish))
    dp (my_srs)
    return my_srs, zone_ish

def get_bbox_of_output(ext, srs):
    """
    The corners of the input raster is transformed to the output system to
    create a bounding box. The bounding box is returned
    """
    source = osr.SpatialReference()
    source.ImportFromEPSG(int(ext[4]))
    target = osr.SpatialReference()
    target.ImportFromEPSG(srs)
    transform = osr.CoordinateTransformation(source, target)
    A = []
    A.append (ogr.CreateGeometryFromWkt("POINT (%s %s)" %(ext[0],ext[3]))) #ll
    A.append (ogr.CreateGeometryFromWkt("POINT (%s %s)" %(ext[0],ext[1]))) #ul
    A.append (ogr.CreateGeometryFromWkt("POINT (%s %s)" %(ext[2],ext[1]))) #ur
    A.append (ogr.CreateGeometryFromWkt("POINT (%s %s)" %(ext[2],ext[3]))) #lr
    B=[]
    for p in A:
        p.Transform(transform)
        B.append((p.GetX(),p.GetY()))
    minx = min(B[0][0],B[2][0])
    maxx = max(B[0][0],B[2][0])
    miny = min(B[0][1],B[2][1])
    maxy = max(B[0][1],B[2][1])
    return minx, maxx, miny, maxy

def read_sidecar_template(template_fnam):
    """
    The template for sidecar xml is read. Keywords are marked with {{KEYWORD}}
    """
    global template
    with open(template_fnam) as f:
        template = f.read()

def write_sidecar_file(fnam, basename, level, gsd, epsg):
    """
    The sidecar xml file is written. Keywords marked with {{KEYWORD}}
    are replaced in the output.
    """
    today = datetime.date.today()
    dp (today)
    with open(fnam, "wt") as f:
        xfile = template.replace('{{BASENAME}}',basename)
        xfile =    xfile.replace('{{LEVEL}}',level)
        xfile =    xfile.replace('{{GSD}}',str(gsd))
        xfile =    xfile.replace('{{DATE}}',str(today))
        xfile =    xfile.replace('{{EPSG}}',epsg)
        f.write(xfile)

def run_cmd(cmdstr):
    """
    Wrapper around subprocess.call, only so output is suppressed when not running in verbose mode.
    """
    if debug:
        subprocess.call(cmdstr, shell=True)
    else:
        subprocess.call(cmdstr, shell=True,  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(args):
    pargs = parser.parse_args(args[1:])
    global debug
    global my_os
    debug = pargs.verbose #if verbose is set, output will be printed using the dp() funcion

    my_os = sys.platform
    print ("my_os: %s" %(my_os))
    if ((my_os == 'darwin') or ('linux' in my_os)): #either mac or linux
        gdal_edit_string = 'gdal_edit.py'
        gdalwarp_string = 'gdalwarp'
        dp ("OS is detected to %s - using gdal_edit.py" %(my_os))
    else:
        gdal_edit_string = 'python gdal_edit.py'
        gdalwarp_string = 'gdalwarp'
        dp ("OS is detected to %s - using 'python gdal_edit.py' in call. " %(my_os))
        dp ("WARNING! AS OF 20200516 THE ANACONDA DIST OF GDAL FOR WINDOWS DOES NOT INCLUDE GDAL_EDIT")
        dp ("A COPY OF GDAL_EDIT.PY IS INCLUDED IN THIS PROJECT. COPY TO THE ROOT AND ALL SHOULD BE")
        dp ("WORKING OUT FINE")

#    gdal_edit_string = 'gdal_edit.py'
#    gdalwarp_string = 'gdalwarp'

#    if pargs.gdal_bin !='auto':
#        gdalwarp_string = os.path.join(pargs.gdal_bin,gdalwarp_string)
#        gdal_edit_string = os.path.join(pargs.gdal_bin,gdal_edit_string)
#    dp("following executables are called... ")
#    dp (gdal_edit_string)
#    dp (gdalwarp_string)

    if not os.path.exists(pargs.output_folder):
        os.makedirs(pargs.output_folder)


    read_sidecar_template(pargs.xml_template) #The template is read. Keywords are marked with {{KEYWORD}}

    my_in_ext = get_extent_and_srs_of_input_raster(pargs.input_raster)
    dp (my_in_ext)

    my_out_srs = 0
    if pargs.utm == 'autodetect':
        my_out_srs, zone_ish = get_recommended_srs_for_output(my_in_ext)
    else:
        if pargs.utm[2].upper() == 'N': #User input should be XXB
            my_out_srs= int("326"+pargs.utm[:-1]) #UTM N starts with 326
        else:
            my_out_srs= int("327"+pargs.utm[:-1]) #UTM S starts with 327
        zone_ish = int(pargs.utm[:-1])
    gsd, posts = resolve_level(pargs.product_level)
    dp ("GSD for output is set to: %s" %(gsd))
    dp ("There are %s posts in the output files " %(posts))
    dp ("EPSG code (srs) has been set to: EPSG:%s" %(my_out_srs))

    minx, maxx, miny, maxy = get_bbox_of_output(my_in_ext,my_out_srs)

    dp ("bounding box for output has been calculated to %s %s %s %s " %(minx, maxx, miny, maxy))

    tiledim = (posts-1)*gsd

    dp ("Tile size is %s m by %s m" %(tiledim, tiledim))

    ix_start = math.floor(minx/tiledim)
    ix_end   = math.floor(maxx/tiledim)+1
    iy_start = math.floor(miny/tiledim)
    iy_end   = math.floor(maxy/tiledim)+1

    numfiles = (ix_end-ix_start)*(iy_end-iy_start)

    numdone = 0
    for yy in range(iy_start, iy_end):
        for xx in range(ix_start, ix_end):
            numdone = numdone +1
            percentage = 100*numdone/numfiles

            minx = xx     * (tiledim)
            maxx = (xx+1) * (tiledim) + gsd #hanging pixel
            miny = yy     * (tiledim)
            maxy = (yy+1) * (tiledim) + gsd
#            print ("%s %s %s %s "%(minx, maxx, miny, maxy))
            basename = "DGEDL%sU_%s_%s" %(pargs.product_level,int(minx),int(miny))
            namnam = os.path.join(pargs.output_folder,basename+'.tif')
            xmlnam = os.path.join(pargs.output_folder,basename+'.xml')

            if os.path.isfile(xmlnam):
                print("file %s already exists, continuing (consider to delete before running)" %(xmlnam))
                continue

            dp(" ")
            dp("----------------------------------------------")
            dp("Creating elevation raster %s" %(namnam))
            cmdstr = """%s -t_srs EPSG:%s+3855 -te %s %s %s %s -dstnodata -32767 -tr %s %s -r cubic -co COMPRESS=LZW --config GTIFF_REPORT_COMPD_CS YES %s %s""" %(gdalwarp_string, my_out_srs, minx, miny, maxx, maxy, gsd, gsd, pargs.input_raster, namnam )
            dp (cmdstr)
            run_cmd(cmdstr)

            dp("Adjusting tiff header")
            cmdstr = """%s --config GTIFF_REPORT_COMPD_CS YES -a_srs epsg:%s+3855 -mo AREA_OR_POINT=POINT %s""" %(gdal_edit_string,my_out_srs,namnam)
            dp (cmdstr)
            run_cmd(cmdstr)

            dp("creating sidecar metadata file")
            write_sidecar_file(xmlnam,basename,pargs.product_level,gsd,"EPSG:"+str(my_out_srs))
            dp("----------------------------------------------")
            dp(" ")
            print ("%s %% done " %(percentage))
    print("All done!")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
