import arcpy
import os

inputDepthRasters = [f.strip("'") for f in arcpy.GetParameterAsText(0).split(";")] #(set of rasters)
inputProfileRoute = arcpy.GetParameterAsText(1) # line datalayer of route with m values
resolution = arcpy.GetParameterAsText(2) # resolution for generating points on route
arcpy.env.workspace = outputGeodatabase = arcpy.GetParameterAsText(3)
# exaggeration of profile based on vertical and horizontal resolution
Horizontal_Scale = float(arcpy.GetParameterAsText(4))
Vertical_Scale = float(arcpy.GetParameterAsText(5))
exaggeration = Horizontal_Scale/Vertical_Scale
spatial_ref = arcpy.Describe(inputProfileRoute).spatialReference
tempData = []
outputName = ""


# checks if raster is the correct type with one band
def checkRasterBandCount(inputRaster):
    rasterLayer = arcpy.Describe(inputRaster)
    if rasterLayer.bandCount > 1:
        arcpy.AddMessage("Error: Invalid raster dataset. This dataset - " + str(inputRaster) + " - cannot be processed.")
        return False
    return True

def cleanUp(list):
    for dataset in list:
        arcpy.Delete_management(dataset)

def addKP(dataset):
    arcpy.management.GeneratePointsAlongLines(inputProfileRoute, dataset, Point_Placement='DISTANCE',
                                              Distance=resolution, Include_End_Points=True)
    arcpy.management.AddField(dataset, "Easting", "DOUBLE")
    arcpy.management.AddField(dataset, "Northing", "DOUBLE")
    arcpy.management.CalculateField(dataset, "Easting", "!SHAPE.CENTROID.X!", "PYTHON_9.3")
    arcpy.management.CalculateField(dataset, "Northing", "!SHAPE.CENTROID.Y!", "PYTHON_9.3")
    global outputName
    outputName = outputName + "_KP"
    eventTable = arcpy.lr.LocateFeaturesAlongRoutes(dataset, inputProfileRoute, "LINE_NAME", resolution,
                                                    outputName, "RID POINT KP_M", route_locations=True,
                                                    distance_field=True, zero_length_events=True, in_fields=True,
                                                    m_direction_offsetting=True)
    temp_layer = "Temp"
    arcpy.management.MakeXYEventLayer(eventTable, 'Easting', 'Northing', temp_layer, spatial_ref)
    KPEventsPoints = arcpy.CopyFeatures_management(temp_layer, outputName + "_Events")
    arcpy.management.DeleteField(KPEventsPoints, ["Distance", "ORIG_FID"])
    tempData.append(KPEventsPoints)
    tempData.append(eventTable)
    tempData.append(temp_layer)
    tempData.append(dataset)
    return KPEventsPoints

def addDepth(table, inputRaster):
    arcpy.CheckOutExtension("Spatial")
    KPDepthTable = arcpy.sa.ExtractValuesToPoints(table, inputRaster, outputName + "_Depth")
    tempData.append(KPDepthTable)
    return KPDepthTable

def exaggerate(points):
    exaggerationDepthFieldName = ""
    if str(exaggeration).endswith('.0'):
        exaggerationDepthFieldName = "Depth_m_Ex" + str(int(exaggeration))
    else:
        exaggerationDepthFieldName = "Depth_m_Ex" + str(exaggeration).replace(".", "_")
    arcpy.management.AddField(points, exaggerationDepthFieldName, "DOUBLE")
    expression = "-abs(float(!RASTERVALU!)*" + str(exaggeration) + ")"
    arcpy.management.CalculateField(points, exaggerationDepthFieldName, expression, "PYTHON_9.3")
    global outputName
    outputName = outputName + "_" + exaggerationDepthFieldName
    arcpy.conversion.TableToTable(points, outputGeodatabase, outputName)
    with arcpy.da.UpdateCursor(outputName, exaggerationDepthFieldName) as cursor:
        for row in cursor:
            if not row[0]:
                row[0] = 1000
                cursor.updateRow(row)
    tempData.append(outputName)
    return outputName, exaggerationDepthFieldName


def createProfile(table, depthField, inputRaster):
    pointLayer = "pointLayer"
    arcpy.management.MakeXYEventLayer(table, 'KP_M', depthField, pointLayer, spatial_ref)
    inFeatures = arcpy.CopyFeatures_management(pointLayer, table + "_Points")
    dataset = arcpy.PointsToLine_management(inFeatures, table + "_Polyline", "Line_Name", Sort_Field="KP_M")
    arcpy.management.AddField(dataset, "Horizon_Scale", "DOUBLE")
    arcpy.management.AddField(dataset, "Vert_Scale", "DOUBLE")
    arcpy.management.AddField(dataset, "Resolution", "TEXT")
    arcpy.management.AddField(dataset, "Raster", "TEXT")
    arcpy.management.CalculateField(dataset, "Horizon_Scale", Horizontal_Scale, "PYTHON_9.3")
    arcpy.management.CalculateField(dataset, "Vert_Scale", Vertical_Scale, "PYTHON_9.3")
    arcpy.management.CalculateField(dataset, "Resolution", "\"" + str(resolution) + "\"", "PYTHON_9.3")
    arcpy.management.CalculateField(dataset, "Raster", "\"" + str(os.path.basename(inputRaster)) + "\"", "PYTHON_9.3")
    tempData.append(inFeatures)
    tempData.append(pointLayer)


def createName():
    global outputName
    if 'Meters' in resolution:
        outputName = os.path.basename(raster)[:11] + "_Profile_" + resolution.replace(" Meters", "m")
    else:
        outputName = os.path.basename(raster)[:11] + "_Profile_" + resolution.replace(" Centimeters", "cm")
    return outputName


for raster in inputDepthRasters:
    # skips to the next raster if this one does not have the correct number of layers (is not the right type of raster)
    if not checkRasterBandCount(raster):
        continue
    table, fieldName = exaggerate(addDepth(addKP(createName()), raster))
    createProfile(table, fieldName, raster)
    cleanUp(tempData)
