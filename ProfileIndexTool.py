import arcpy
import math, os

chartIndexLayer = arcpy.GetParameterAsText(0)
inputDepthRaster = arcpy.GetParameterAsText(1)
inputProfileRoute = arcpy.GetParameterAsText(2)
# search radius is required for the LocateFeaturesAlongRoutes tool and is variable per project
searchRadius = arcpy.GetParameterAsText(3)
arcpy.env.workspace = arcpy.GetParameterAsText(4)
outputFileName = arcpy.GetParameterAsText(5)
exaggeration = float(arcpy.GetParameterAsText(6))/float(arcpy.GetParameterAsText(7))
spatial_ref = arcpy.Describe(chartIndexLayer).spatialReference
exaggerationDepthFieldName = "Depth_m_Ex" + str(int(exaggeration))


def findClosestPoints(line, points):
    closest_points = []
    with arcpy.da.SearchCursor(points, ("OID@", "SHAPE@X", "SHAPE@Y")) as centroids:
        for centroid in centroids:
            closest_point = []
            # Standard programming use of large arbitrary number as seed for smallest_distance
            smallest_distance = 9999
            with arcpy.da.SearchCursor(line, ("SHAPE@X", "SHAPE@Y"), spatial_reference=spatial_ref,
                                       explode_to_points=True) as line_points:
                for point in line_points:
                    distance = math.hypot(float(point[0]) - float(centroid[1]), float(point[1]) - float(centroid[2]))
                    if distance < smallest_distance:
                        smallest_distance = distance
                        closest_point = (centroid[0], point)
            closest_points.append(closest_point)
    return closest_points

def findDepth(centroids, route, depthRaster):
    closestPoints = findClosestPoints(route, centroids)
    arcpy.management.AddField(centroids, "Depth_m", "DOUBLE")
    arcpy.management.AddField(centroids, exaggerationDepthFieldName, "DOUBLE")
    with arcpy.da.UpdateCursor(centroids, ("OID@", "Depth_m", exaggerationDepthFieldName)) as cursor:
        for row in cursor:
            for point in closestPoints:
                if row[0] == point[0]:
                    result = arcpy.GetCellValue_management(depthRaster, str(point[1][0]) + " " + str(point[1][1]))
                    CellValue = float(result.getOutput(0).replace(',','.'))
                    row[1] = -abs(CellValue)
                    row[2] = -abs(CellValue) * exaggeration
                    cursor.updateRow(row)
    return centroids

def createCentroids(extentPolygons):
    # Tool LocateFeaturesAlongRoutes requires a feature class as input
    arcpy.management.AddField(extentPolygons, "Easting", "DOUBLE")
    arcpy.management.AddField(extentPolygons, "Northing", "DOUBLE")

    arcpy.management.CalculateField(extentPolygons, "Easting", "!SHAPE.CENTROID.X!", "PYTHON_9.3")
    arcpy.management.CalculateField(extentPolygons, "Northing", "!SHAPE.CENTROID.Y!", "PYTHON_9.3")

    new_table_view = "temp_table"
    arcpy.management.MakeTableView(extentPolygons, new_table_view)

    temp_layer = "Temp"
    arcpy.management.MakeXYEventLayer(new_table_view, 'Easting', 'Northing', temp_layer, spatial_ref)
    if arcpy.Exists("Centroids"):
        arcpy.Delete_management("Centroids")
    centroids = arcpy.CopyFeatures_management(temp_layer, "Centroids")
    return centroids

def addKP(ddp):
    if arcpy.Exists("DDP_KP"):
        arcpy.Delete_management("DDP_KP")
    KP_Table = arcpy.lr.LocateFeaturesAlongRoutes(ddp, inputProfileRoute, "LINE_NAME", searchRadius, "DDP_KP",
                                                  "RID POINT KP_M")
    arcpy.management.AddField(KP_Table, "Y", "DOUBLE")
    arcpy.management.CalculateField(KP_Table, "Y", "!" + exaggerationDepthFieldName + "!", "PYTHON_9.3")
    addBarPoints(KP_Table)
    temp_layer1 = "Temp1"
    arcpy.management.MakeXYEventLayer(KP_Table, 'KP_M', "Y", temp_layer1, spatial_ref)
    if arcpy.Exists(outputFileName):
        arcpy.Delete_management(outputFileName)
    outputDataset = arcpy.CopyFeatures_management(temp_layer1, outputFileName)
    arcpy.management.AddField(outputDataset, "RouteFeature", "TEXT")
    arcpy.management.CalculateField(outputDataset, "RouteFeature", "\"" + str(os.path.basename(inputProfileRoute))
                                    + "\"", "PYTHON_9.3")

def addBarPoints(table):
    arcpy.management.AddField(table, "Type", "TEXT")
    with arcpy.da.UpdateCursor(table, "Type") as cursor:
        for row in cursor:
            row[0] = "Profile"
            cursor.updateRow(row)
    barPoints = arcpy.management.Copy(table, "BarPoints")
    with arcpy.da.UpdateCursor(table, "Type") as cursor:
        for row in cursor:
            row[0] = "Bar"
            cursor.updateRow(row)
    arcpy.management.CalculateField(barPoints, "Y", 0, "PYTHON_9.3")
    arcpy.management.Append(barPoints, table)


def cleanUp():
    arcpy.Delete_management("Centroids")
    arcpy.Delete_management("DDP_KP")
    arcpy.Delete_management("BarPoints")

def init():
    addKP(findDepth(createCentroids(chartIndexLayer), inputProfileRoute, inputDepthRaster))
    cleanUp()

init()




