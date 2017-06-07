# -*- coding: utf-8 -*-
"""
Created on Wed Nov 23 10:42:56 2016
in: 
AL_grid: AL_x, AL_y
DF_cells: list of polygons
@author: velhorst
"""

import numpy as np
#import matplotlib.pyplot as plt
from scipy.spatial import Voronoi#, Delaunay, voronoi_plot_2d
#from sys import exit
#import pandas as pd
#import copy

#import os

#import geopandas as gpd


#from descartes import PolygonPatch
from shapely.geometry import Point,  Polygon#, MultiPoint, MultiPolygon

from rtree import index

#plt.close('all')

def infinite_segments(vor_):
    line_segments = []
    center = vor_.points.mean(axis=0)
    for pointidx, simplex in zip(vor_.ridge_points, vor_.ridge_vertices):
        simplex = np.asarray(simplex)
        if np.any(simplex < 0):
            i = simplex[simplex >= 0][0]  # finite end Voronoi vertex

            t = vor_.points[pointidx[1]] - vor_.points[pointidx[0]]  # tangent
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])  # normal

            midpoint = vor_.points[pointidx].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n

            line_segments.append([(vor_.vertices[i, 0], vor_.vertices[i, 1]),
                                  (direction[0], direction[1])])
    return line_segments

def intersect(p0, u, q0, q1):
    v = (q1 - q0)[np.newaxis].T
    A = np.hstack([u, -v])
    b = q0 - p0
    try:
        inv_A = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        return np.nan, np.nan
    return np.dot(inv_A, b)
    
def polygons_around_point_from_voronoi(vor,edge_lines,point,points_list):
    x_condition = vor.points[:,0]==point.x
    y_condition = vor.points[:,1]==point.y
    index_in_vor = np.where((x_condition)&(y_condition))[0][0]
    vert_indexes = vor.regions[vor.point_region[index_in_vor]]
    point_tuple = ((point.x,point.y))
    polygon = polygon_from_voronoi_point(vor,edge_lines,point_tuple,points_list)
    return vert_indexes, index_in_vor, polygon

def find_edge_lines(vor,boundary):
    infinites_list  = infinite_segments(vor)
    inf_from_inside = np.array([x for x in infinites_list if boundary.contains(Point(x[0]))])
    temp_coords = np.array(boundary.exterior.coords)
    line_segments = []
    for f in inf_from_inside:
        for coord0, coord1 in zip(temp_coords, temp_coords[1:]):
            s, t = intersect(f[0], f[1][np.newaxis].T, coord0, coord1)
            if 0 < t < 1 and s > 0:
                line_segments.append([f[0], f[0] + s * f[1]])
                break
    edge_lines = np.array(line_segments)    
    return edge_lines

def polygon_from_voronoi_point(vor,edge_lines,point,points_list):
    index = points_list.index(point)
    
    vert_indexes = vor.regions[vor.point_region[index]]

    points_for_AL_polygon = []
    shadow_points_for_AL_polygon = []
    if -1 in vert_indexes: # corners and edges
        non_minus1 = np.asarray(vert_indexes) != -1
        list_of_points = list(vor.vertices[vert_indexes][non_minus1])
        for item in list_of_points:
            points_for_AL_polygon.append(item) 
        for edge_point in vor.vertices[vert_indexes][non_minus1]:
            edge_x = edge_point[0]
            edge_y = edge_point[1]
            x_condition = edge_lines[:,0,0]==edge_x
            y_condition = edge_lines[:,0,1]==edge_y

            edge_index = np.where((x_condition)&(y_condition))[0]

            if (len(edge_index) == 1): #edge point
                vert_point_inf = edge_lines[edge_index,1][0]
                points_for_AL_polygon.append(vert_point_inf)
                
            if (len(edge_index) == 2) & (len(vert_indexes) == 2): #corner point
                list_of_points = list(edge_lines[edge_index,1])
                for item in list_of_points:
                    points_for_AL_polygon.append(item)
                c = edge_lines[edge_index,1].mean(axis=0)
                extra_corner = c + (c-edge_point)
                points_for_AL_polygon.append(extra_corner)
                
            if (len(edge_index) == 2) & (len(vert_indexes) == 3): # edge next to corner
                list_of_points = list(edge_lines[edge_index,1])
                for item in list_of_points:
                    shadow_points_for_AL_polygon.append(item)
        
    if len(shadow_points_for_AL_polygon) > 0: # add only one point at edge next to corner
        shadow_points = np.asanyarray(shadow_points_for_AL_polygon)
        distance = np.sqrt((shadow_points[:,0]-point[0])**2+(shadow_points[:,1]-point[1])**2)
        closest_index = np.where(distance==np.sort(distance)[0])[0]
        points_for_AL_polygon.append(shadow_points_for_AL_polygon[closest_index[0]])
    
    if not -1 in vert_indexes: # center points
        vert_points = vor.vertices[vert_indexes]
        for item in vert_points:
            points_for_AL_polygon.append(item)

    #sort clockwise
    vs = np.asanyarray(points_for_AL_polygon)
    c = vs.mean(axis=0)
    angles = np.arctan2(vs[:,1] - c[1], vs[:,0] - c[0])
    points_for_AL_polygon_sorted = vs[np.argsort(angles)]
    
    polygon = Polygon(points_for_AL_polygon_sorted) 
    return polygon
    
def boundary_around_grid(mesh_x,mesh_y):
    grid_x = mesh_x[0,:]
    grid_y = mesh_y[:,0]
    # necessary for finite boundary for voronoi cells of outer grid cells
    xs = grid_x[0]+(grid_x[0]-grid_x[1])/2
    xe = grid_x[-1]+(grid_x[-1]-grid_x[-2])/2
    ys = grid_y[0]+(grid_y[0]-grid_y[1])/2
    ye = grid_y[-1]+(grid_y[-1]-grid_y[-2])/2
    
    boundary = Polygon([[xs, ys], [xe,ys], [xe,ye], [xs,ye]])
    return boundary

def polygons_aggegration_matrix(all_poly_1,all_poly_2):
    # in: two sets of shapely polygons
    # out: a (mxn) matrix of shape (len(all_poly_1),len(all_poly_2)) 
    # containing relative weights usable for conversion 
    # of values spaced on grid 2 towards values on grid 1
    # e.g. val1 = np.dot(relative_weights_matrix, val2)
    # Assumption: order of points and polygons is consisent, 
    # index might be not so trivial
    
    #create empty matrices
    matrix_shape = (len(all_poly_1),len(all_poly_2))
    weights_matrix = np.zeros(matrix_shape)
    areas_polys_1 = np.zeros(matrix_shape)
    #loop through polygons, filling the weight matrix
    for ind_1, poly_1 in enumerate(all_poly_1):
        for ind_2, poly_2 in enumerate(all_poly_2):
            weights_matrix[ind_1,ind_2] = poly_1.intersection(poly_2).area
            areas_polys_1[ind_1,ind_2] = poly_1.area
    relative_weight_matrix = weights_matrix / areas_polys_1
    return relative_weight_matrix, areas_polys_1, weights_matrix 
        
def aggregation_interpolation_area_correction(all_poly_1,all_poly_2):
    # in:  two sets of shapely polygons
    # out: 1d array of length len(all_poly_1)
    # containing correction factors as addition to 
    # the matrix of polygons_aggegration_matrix.
    # e.g. val2 = np.dot(relative_weights_matrix, val1*correction)
    # Assumption: order of points and polygons is consisent, 
    # index might be not so trivial
    
    from shapely.ops import cascaded_union
    from shapely.geometry import MultiPolygon
    
    poly_multi_2 = cascaded_union(MultiPolygon(all_poly_2))
    area_1_filled = []
    for ix,poly in enumerate(all_poly_1):
        area_poly = poly.area
        intersection = poly.intersection(poly_multi_2)
        area_covered = intersection.area
        filled_percentage = area_covered/area_poly
        area_1_filled.append(filled_percentage)
        
    area_fill_array = np.asarray(area_1_filled)
    correction = np.zeros_like(area_fill_array)
    correction[area_fill_array!=0] = 1./area_fill_array[area_fill_array!=0]

    return correction

def polygons_from_mesh(mesh_x,mesh_y,boundary_poly='none'):
    # in: two mesh grids, containing x and y coordinates respectively
    # out: list of shapely polygons
    # assumes the direction meshes coincide with the x- and y axis  
    x = mesh_x.ravel()
    y = mesh_y.ravel()
    points = zip(x,y)
    vor = Voronoi(points)
    if boundary_poly =='none':
        boundary = boundary_around_grid(mesh_x,mesh_y)
    else:
        boundary = boundary_poly
    edge_lines = find_edge_lines(vor,boundary)
    #list all polygons
    all_poly = []
    for index, point in enumerate(points):
        polygon = polygon_from_voronoi_point(vor,edge_lines,point,points)
        all_poly.append(polygon)
    return all_poly

def polygons_aggegration_matrix_fast(all_poly_1,all_poly_2):
    # in: two sets of shapely polygons, 
    # out: a (mxn) matrix of shape (len(all_poly_1),len(all_poly_2)) 
    # containing relative weights usable for conversion 
    # of values spaced on grid 2 towards values on grid 1
    # e.g. val1 = np.dot(relative_weights_matrix, val2)
    # Assumption: order of points and polygons is consisent, 
    # index might be not so trivial
     
    idx2 = index.Index()
    for pos, poly in enumerate(all_poly_2):
        idx2.insert(pos,poly.bounds)
    
    #create empty matrices
    matrix_shape = (len(all_poly_1),len(all_poly_2))
    weights_matrix = np.zeros(matrix_shape)
    ##areas_polys_1 = np.ones(matrix_shape)
    #loop through polygons, filling the weight matrix
    for ind_1, poly_1 in enumerate(all_poly_1):
        for ind_2 in idx2.intersection(poly_1.bounds):
            poly_2 = all_poly_2[ind_2]
            weights_matrix[ind_1,ind_2] = poly_1.intersection(poly_2).area / poly_1.area
            ##areas_polys_1[ind_1,ind_2] = poly_1.area
    #relative_weight_matrix = weights_matrix## / areas_polys_1
    return weights_matrix #relative_weight_matrix##, areas_polys_1, weights_matrix 
