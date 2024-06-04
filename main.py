import pathlib
from ctypes import *
import cv2 as cv
import numpy as np
from invoice import Invoicer


class Point(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]

def main():
    libObject = cdll.LoadLibrary("./header_outline.so");
    img_path = pathlib.Path.home() / "Desktop" / "receipt-scanner" / "scan.jpg";
    invoice = Invoicer(str(img_path.absolute()));
    invoice.table_outline();
    invoice.align_table();
    invoice.readText();
    invoice.getHeaders();

    # grayscale and threshold the image
    grayscale = cv.cvtColor(invoice.table_only, cv.COLOR_BGR2GRAY);
    ret, thresh = cv.threshold(grayscale, 180, 255, 0);
    cv.imwrite("thresh.jpg", thresh);
    # get starting point
    start_pt = np.unravel_index(np.argmin(thresh, axis=None), thresh.shape);
    c_start_pt = Point(*start_pt);
    rows, cols = thresh.shape;
    # flatten image before passing into C function
    flat = thresh.flatten();
    # make an array compatible with C
    int_arr = c_int * len(flat);
    data = int_arr(*flat);
    # make line_helper array
    float_arr = c_float * 4;
    # xs, xe, m, b
    line_helper = float_arr(invoice.start_x, invoice.end_x, *invoice.helper_line)
    # draw best line of fit against a small amount of candidate headers
    # have the algorithm try to follow the path without deviating to far from
    # the line of best fit
    # pass data into C function
    print(libObject.headerAlgorithm( c_int(cols), c_int(rows), data,  pointer(c_start_pt),line_helper ));

if( __name__ == "__main__"):
    main();