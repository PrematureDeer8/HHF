import pathlib
from ctypes import *
import cv2 as cv
import numpy as np
from invoice import Invoicer
from DataHandler import DataHandler
import pandas as pd
import argparse


class Point(Structure):
    _fields_ = [("x", c_int), ("y", c_int)];

class Rectangle(Structure):
    _fields_ = [("x1", c_int), ("y1", c_int), ("x2", c_int), ("y2", c_int)];

class Column(Structure):
    _fields_ = [("x1", c_int), ("x2", c_int)];

def main():
    parser = argparse.ArgumentParser(
        prog="HHF",
        description="Convert your image files (JPEG, PNG) to EXCEL FILES!",

    );
    parser.add_argument("document_path", type=str,
                        help="file or folder path for image(s)");
    parser.add_argument("--excel_file", type=str,
                        help="Existing excel file that you want to append to",
                        default=None);
    parser.add_argument("--so_file", type=str,
                        help="Shared Object file for C code!",
                        default="./header_outline.so");
    
    args = parser.parse_args();
    # validate path
    for attribute in vars(args):
        if(getattr(args, attribute) is None or (not("path" in attribute) and not("file" in attribute))):
            continue;
        fp = pathlib.Path(getattr(args, attribute));
        if(not fp.exists()):
            fp = pathlib.Path.home() / fp;
            if(not fp.exists()):
                raise ValueError(f"File path ({fp}) does not exists!");
        if(attribute == "document_path"):
            if(fp.is_file()):
                iterator = [fp];
            else:
                iterator = fp.iterdir();

    libObject = cdll.LoadLibrary(args.so_file);
    print(iterator);
    start = 1;
    if(args.excel_file is None):
        start = 0;
        args.excel_file = "output.xlsx";
    for count, img_path in enumerate(iterator, start):
        if(img_path.suffix != ".jpg" and img_path.suffix != ".png"):
            continue;
        print(img_path);
        invoice = Invoicer(str(img_path.absolute()), debug=True);
        invoice.table_outline(crop_amount=0);
        invoice.align_table();
        invoice.readText(min_size=4,width_ths=0.25);
        invoice.getCandidateHeaders();

        # grayscale and threshold the image
        grayscale = cv.cvtColor(invoice.table_only, cv.COLOR_BGR2GRAY);
        # blur before thresholding
        blur = cv.GaussianBlur(grayscale, (7,3),0);
        ret, thresh = cv.threshold(blur, 180, 255, 0);
        cv.imwrite("thresh.jpg", thresh);
        # get starting point
        flat = thresh.flatten();
        # zero_only = flat == 0;
        # indices = np.arange(len(flat));
        start_pt = min(np.argwhere(thresh == 0), key=lambda index: index.sum());
        print(start_pt);
        c_start_pt = Point(start_pt[1], start_pt[0]);
        rows, cols = thresh.shape;
        # flatten image before passing into C function
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
        cv.line(invoice.table_only, (0, int(avg_y)), (int(invoice.table_only.shape[1]), int(avg_y)), (0,0,255), 2);
        cv.imwrite("dst.jpg", invoice.table_only);
        invoice.getHeaders(avg_y);
        libObject.columnAlgorithm.restype = Column;
        columns = [];
        # invoice.load_dict();
        # print("Column algorithm")
        for i in range(invoice.header_bbox.shape[0]):
            # print(i);
            cv.rectangle(invoice.table_only, tuple(invoice.header_bbox[i][:2].astype(np.int32)), tuple(invoice.header_bbox[i][2:].astype(np.int32)), (0,255,0), 2);
            y_ctr = invoice.header_bbox[i,1::2].sum()/2;
            rect = Rectangle(invoice.header_bbox[i][0].astype(np.int32), int(y_ctr),invoice.header_bbox[i][2].astype(np.int32), int(y_ctr));
            # make sure this not a duplicate column (they should happen consecutively)
            column = libObject.columnAlgorithm(c_int(cols), data , pointer(rect));
            if(i == 0 or (abs(column.x1 - columns[-1].x1) > 5 or abs(column.x2 - columns[-1].x2) > 5)):
                columns.append(column);
            else:
                invoice.keyheaders[i - 1] += invoice.keyheaders[i];
                invoice.keyheaders[i] = None;

        for i in range(invoice.keyheaders.count(None)):
            invoice.keyheaders.remove(None);
            # print(columns[-1].x1, columns[-1].x2);
        for column in columns:
            cv.line(invoice.table_only, (int(column.x1), 0), (int(column.x1), invoice.table_only.shape[0]),(0,0,255), 2);
            cv.line(invoice.table_only, (int(column.x2), 0), (int(column.x2), invoice.table_only.shape[0]),(0,0,255), 2);
        cv.imwrite("dst.jpg", invoice.table_only)
        # print(invoice.header_labels);
        invoice.load_dict(columns);
        # print(invoice.dict);
        if(count):
            data_handle = DataHandler(invoice.dict, args.excel_file);
        else:
            data_handle = DataHandler(invoice.dict);
        data_handle.df.loc[:, "Commission Payments"] = pd.to_numeric(data_handle.df.loc[:, "Commission Payments"]);
        data_handle.write(file_name=args.excel_file,filter={"Recieved": "== 'YES'", "Commission Payments": "!= 0"}, comparison=0, hidden_col=[list(data_handle.df.columns.values).index("metadata") + 1,0]);
        # print(data_handle.df.columns);
if( __name__ == "__main__"):
    main();