import pathlib
from ctypes import *
import cv2 as cv
import numpy as np
from invoice import Invoicer
import pandas as pd



class Point(Structure):
    _fields_ = [("x", c_int), ("y", c_int)];

class Rectangle(Structure):
    _fields_ = [("x1", c_int), ("y1", c_int), ("x2", c_int), ("y2", c_int)];

class Column(Structure):
    _fields_ = [("x1", c_int), ("x2", c_int)];

def main():
    libObject = cdll.LoadLibrary("./header_outline.so");
    img_path = pathlib.Path.home() / "Desktop" / "scan0003.jpg";
    invoice = Invoicer(str(img_path.absolute()), debug=True);
    invoice.table_outline();
    invoice.align_table();
    invoice.readText(min_size=4,width_ths=0.25);
    invoice.getCandidateHeaders();

    # grayscale and threshold the image
    grayscale = cv.cvtColor(invoice.table_only, cv.COLOR_BGR2GRAY);
    ret, thresh = cv.threshold(grayscale, 180, 255, 0);
    cv.imwrite("thresh.jpg", thresh);
    # get starting point
    start_pt = np.unravel_index(np.argmin(thresh, axis=None), thresh.shape);
    # print("Start point: \n", start_pt);
    c_start_pt = Point(start_pt[1], start_pt[0]);
    rows, cols = thresh.shape;
    # flatten image before passing into C function
    flat = thresh.flatten();
    # make an array compatible with C
    int_arr = c_int * len(flat);
    data = int_arr(*flat);
    # make line_helper array
    float_arr = c_float * 4;
    # xs, xe, m, b
    line_helper = float_arr(invoice.start_x, invoice.end_x, *invoice.helper_line);
    # draw best line of fit against a small amount of candidate headers
    # have the algorithm try to follow the path without deviating to far from
    # the line of best fit
    # pass data into C function
    libObject.headerAlgorithm.restype = c_float;
    avg_y = libObject.headerAlgorithm(c_int(cols), c_int(rows), data,  pointer(c_start_pt),line_helper );
    # cv.line(invoice.table_only, (0, int(avg_y)), (int(invoice.table_only.shape[1]), int(avg_y)), (0,0,255), 2);
    # cv.imwrite("dst.jpg", invoice.table_only);
    invoice.getHeaders(avg_y);
    libObject.columnAlgorithm.restype = Column;
    columns = [];
    # invoice.load_dict();
    # print("Column algorithm")
    for i in range(invoice.header_bbox.shape[0]):
        # print(i);
        cv.rectangle(invoice.table_only, tuple(invoice.header_bbox[i][:2].astype(np.int32)), tuple(invoice.header_bbox[i][2:].astype(np.int32)), (0,255,0), 2);
        rect = Rectangle(*invoice.header_bbox[i].astype(np.int32));
        columns.append(libObject.columnAlgorithm(c_int(cols), data , pointer(rect)));
    # rect = Rectangle(*invoice.header_bbox[12].astype(np.int32));
    # columns.append(libObject.columnAlgorithm(c_int(cols), data, pointer(rect)));
    # print("After column aglo")
    for column in columns:
        cv.line(invoice.table_only, (int(column.x1), 0), (int(column.x1), invoice.table_only.shape[0]),(0,0,255), 2);
        cv.line(invoice.table_only, (int(column.x2), 0), (int(column.x2), invoice.table_only.shape[0]),(0,0,255), 2);
    cv.imwrite("dst.jpg", invoice.table_only)
    invoice.load_dict(columns);
    df = pd.DataFrame(data=invoice.dict);
    with pd.ExcelWriter("ardent.xlsx") as writer:
        df.to_excel(writer);

if( __name__ == "__main__"):
    main();