import os,sys
import math
from osgeo import gdal,ogr,osr
import subprocess
import datetime

#*--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--*
#Following arrays are for converting to GEO

#Derived from table 3, page 12
#                        zone, lat_min, lat_max, lat_spacing, long_spacing
zone_lon_spacing =[]    # last column is "long_spacing" - a multiplication factor
zone_lon_spacing.append ((-6,-90, -85, 1, 10 ))
zone_lon_spacing.append ((-5,-85, -80, 1, 5  ))
zone_lon_spacing.append ((-4,-80, -70, 1, 3  ))
zone_lon_spacing.append ((-3,-70, -60, 1, 2  ))
zone_lon_spacing.append ((-2,-60, -50, 1, 1.5))
zone_lon_spacing.append ((-1,-50, -0 , 1, 1  ))
zone_lon_spacing.append (( 1,  0,  50, 1, 1  ))
zone_lon_spacing.append (( 2, 50,  60, 1, 1.5))
zone_lon_spacing.append (( 3, 60,  70, 1, 2  ))
zone_lon_spacing.append (( 4, 70,  80, 1, 3  ))
zone_lon_spacing.append (( 5, 80,  85, 1, 5  ))
zone_lon_spacing.append (( 6, 85,  90, 1, 10 ))

#Derived from table 7 page 24
# level, tile_size (minutes), lat_res, tile size letter                #corresponds to...
level_tilesize_and_spatial_resolution = []
level_tilesize_and_spatial_resolution.append (("0",  60,  30, "A"))    # 1000 m
level_tilesize_and_spatial_resolution.append (("1",  60,  3, "A"))     # 100 m
level_tilesize_and_spatial_resolution.append (("2",  60,  1, "A"))     # 30 m
level_tilesize_and_spatial_resolution.append (("3",  60,  0.4, "A"))   # 12 m
level_tilesize_and_spatial_resolution.append (("4b", 15,  0.15, "C"))  # 5 m
level_tilesize_and_spatial_resolution.append (("4",  15,  0.12, "C"))  # 4 m
level_tilesize_and_spatial_resolution.append (("5",  6,   0.06, "D"))  # 2 m
level_tilesize_and_spatial_resolution.append (("6",  3,   0.03, "E"))  # 1 m
level_tilesize_and_spatial_resolution.append (("7",  1.5, 0.015, "F")) # 0.5 m
level_tilesize_and_spatial_resolution.append (("8",  1,   0.0075, "G")) # 0.25 m
level_tilesize_and_spatial_resolution.append (("9",  1,   0.00375, "G")) # 0.125 m

#*--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--*
#Following array is for converting to utm
#Derived from Table 8 page 25
#Array with parameters for the various levels. As for number of posts per tile, the lowest choice is used
#Order is...  level name, GSD, number of posts, tile size letter
PL = []
PL.append(('4b',5,5001, "C"))
PL.append(('4',4,6251, "C"))
PL.append(('5',2,5001, "D"))
PL.append(('6',1,5001, "E"))
PL.append(('7',0.5,5001, "F"))
PL.append(('8',0.25,5001, "G"))
PL.append(('9',0.125,10001, "G"))

#*--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--**--*--*--*--*
#Following functions are common for both UTM And GEO conversion


debug = False


def dp(st):
    """
    Print a string, but only if verbose is set to True
    """
    if debug:
        print(st)

def read_sidecar_template(template_fnam): #UNCHANGED
    """
    The template for sidecar xml is read. Keywords are marked with {{KEYWORD}}
    """
    with open(template_fnam) as f:
        template = f.read()
    return template

def write_sidecar_file(template, fnam, basename, level, gsd, epsg): #UNCHANGED
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

def get_extent_and_srs_of_input_raster(rasras): #UNCHANGED
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


def get_bbox_of_output(ext, srs): #UNCHANGED
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

def checkos():
    """
    During testing some inconsistencies between Anaconda's GDAL and various OS's were encountered. Therefore a test for debug purposes
    """
    my_os = sys.platform
    dp ("*"*20)
    if ((my_os == 'darwin') or ('linux' in my_os)): #either mac or linux
        dp ("OS detected...: %s ... all should be work fine" %(my_os))
    else:
        dp ("OS is detected to %s - using 'python gdal_edit.py' in call. " %(my_os))
        dp ("WARNING! AS OF 20200516 THE ANACONDA DIST OF GDAL FOR WINDOWS DOES NOT INCLUDE GDAL_EDIT")
        dp ("A COPY OF GDAL_EDIT.PY IS INCLUDED IN THIS PROJECT. OTHER PROBLEMS MAY PERSIST!")
        print("Running on a windows machine - check to see if AREA_OR_POINT=Point in output (gdalinfo)")
    dp ("*"*20)

def run_cmd(cmdstr):
    """
    Wrapper around subprocess.call, only so output is suppressed when not running in verbose mode.
    """
    if debug:
        subprocess.call(cmdstr, shell=True)
    else:
        subprocess.call(cmdstr, shell=True,  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main(args):
    #nothing here
    a=1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
