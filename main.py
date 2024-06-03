import pathlib
from ctypes import *
import cv2 as cv
import numpy as np


class Point(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]

def main():
    libObject = cdll.LoadLibrary("./header_outline.so");
    img_path = pathlib.Path.home() / "Desktop" / "receipt-scanner" / "dst.jpg";
    # grayscale and threshold the image
    grayscale = cv.imread(str(img_path.absolute()), cv.IMREAD_GRAYSCALE);
    ret, thresh = cv.threshold(grayscale, 127, 255, 0);
    # get starting point
    start_pt = np.unravel_index(np.argmin(thresh, axis=None), thresh.shape);
    c_start_pt = Point(*start_pt);
    rows, cols = thresh.shape;
    # flatten image before passing into C function
    flat = thresh.flatten();
    # make an array compatible with C
    float_arr = c_int * len(flat);
    data = float_arr(*flat);
    # pass data into C function
    libObject.headerAlgorithm(data, c_int(cols), c_int(rows), pointer(c_start_pt));

if( __name__ == "__main__"):
    main();