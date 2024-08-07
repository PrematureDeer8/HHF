import cv2 as cv
import pandas as pd
import pathlib
import numpy as np
import string
from dateutil import parser
from datetime import datetime
from fuzzywuzzy import fuzz
from scipy.optimize import linear_sum_assignment

class Invoicer:
    def __init__(self, image_file, debug=False, ocr=True):
        if(ocr):
            import easyocr
            self.reader = easyocr.Reader(['en']);
        self.imfp = pathlib.Path(image_file);
        self.debug = debug;
        if(not self.imfp.exists()):
            raise ValueError(f"{self.imfp} does not exists!");
        self.img = cv.imread(str(self.imfp.absolute()));
        self.dict = {"Order": [],
                     "Order Date": [],
                     "Invoice": [],
                     "Invoice Date": [],
                     "Customer Po": [],
                     "Subinventory": [],
                     "Type": [],
                     "Customer": [],
                     "Sales Representative": [],
                     "City": [],
                     "State": [],
                     "Price": [],
                     "Payment Term": [],
                     "Cash Disc": [],
                     "Net Price": [],
                     "Line" : [],
                     "% Rebates": [],
                     "$ Rebates": [],
                     "% Commissions Sales": [],
                     "Commissions Sales": [],
                     "Recieved": [],
                     "Commission Payments": []
                     };
        self.keys = list(self.dict.keys());
        
    def table_outline(self, crop_amount=75, threshold=150):
        if(crop_amount):
            self.crop = self.img[crop_amount: -crop_amount, crop_amount:-crop_amount, :].copy();
        else:
            self.crop = self.img.copy();
        grayscale = cv.cvtColor(self.crop, cv.COLOR_BGR2GRAY);
        ret, thresh = cv.threshold(grayscale, threshold, 255, 0);
        cond1 = thresh == 0;
        cond2 = thresh == 255;
        invert = thresh.copy();
        invert[cond1] = 255;
        invert[cond2] = 0;
        # find contours
        contours, hierarchy = cv.findContours(invert, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE);
        rectangles = [];
        for cnt in contours:
            x,y,w,h = cv.boundingRect(cnt);
            rectangles.append((x,y,w,h));
        # get the max area rectangle
        table_rectangle = max(rectangles, key=lambda rectangle: rectangle[2] * rectangle[3]);
        # shift the contours by the crop amount
        self.table_contours = contours[rectangles.index(table_rectangle)].squeeze() - table_rectangle[:2];
        self.table_only = grayscale[table_rectangle[1]: table_rectangle[1] + table_rectangle[3],table_rectangle[0]:table_rectangle[0] + table_rectangle[2]].copy();
        self.table_only = cv.cvtColor(self.table_only, cv.COLOR_GRAY2RGB);

        # cv.drawContours(crop, contours, -1, (0,255,0), 2);
        if(self.debug):
            cv.imwrite("table.jpg", self.table_only);
    
    def align_table(self, sort_cutoff=30):
        # sort from top left corner to bottom right corner
        #[m, b]
        self.line_equations = np.zeros((3,2));
        sort_tb = np.array(sorted(self.table_contours, key= lambda points: points[0] + points[1]));
        sort_tr = np.array(sorted(self.table_contours, key=lambda points: (points[1] + 1)/pow(points[0] + 1e-6, 2)))
        self.points = np.zeros(shape=(4,2)).astype(np.int32);
        # taking the mean of the edge points
        # since the max and min both give the edge of the cropped 
        # table only image
        self.points[0] = sort_tb[:sort_cutoff].mean(axis=0).astype(np.int32); #top left corner
        # self.points[1] = sort_tb[-sort_cutoff:].mean(axis=0).astype(np.int32); #bottom right corner
        self.points[1] = sort_tr[:sort_cutoff].mean(axis=0).astype(np.int32); # top right corner

        # m = -rise/run
        # b = -m * x1 + y1
        diff = self.points[1] - self.points[0];
        m = diff[1]/diff[0];
        self.line_equations[0] = (m, -m * self.points[0][0] + self.points[0][1]);
        
        # m = self.table_only.shape[0]/self.table_only.shape[1];
        m = 0; #should be flat line
        self.line_equations[2] = (m, -m * self.points[0][0] + self.points[0][1]);

        true_angle = np.arctan(m);
        angle = np.arctan(self.line_equations[0][0]);
        angle_diff = true_angle - angle;
        
        rows, cols = self.table_only.shape[:2];
        M = cv.getRotationMatrix2D(((cols-1)/2.0, (rows-1)/2.0), -angle_diff * (180 / np.pi), 1);
        self.table_only = cv.warpAffine(self.table_only, M, (cols, rows),borderMode=cv.BORDER_CONSTANT, borderValue=(255,255,255));
        if(self.debug):
            cv.imwrite("dst.jpg", self.table_only);
            

    def has_ascii_letter(word):
        for letter in word:
            if(letter in string.ascii_letters):
                return True;
        return False;

    # count how many times a word is in a list
    def word_occurrence(word, word_list, length=4):
        counter = 0;
        for element in word_list:
            if(len(word) < length):
                break;
            if(word in element):
                counter+=1;
        return counter -1;
    def readText(self, min_size=5, height_ths=1.0, width_ths=0.5, decoder="greedy", block_list=r"[]|{_",threshold=0.8):
        self.text_info = self.reader.readtext(self.table_only, blocklist=block_list, min_size=min_size, decoder=decoder, height_ths=height_ths,\
                                             width_ths=width_ths, canvas_size=max(self.table_only.shape), threshold=threshold, add_margin=0.03,\
                                             );
        self.longest_str_detection = len(max(self.text_info, key=lambda info: len(info[1]))[1]);
        if(self.debug):
            annotated = self.table_only.copy();
        self.bbox = np.zeros(shape=(len(self.text_info),4));
        self.labels = np.empty(shape=(len(self.text_info)), dtype=f"<U{self.longest_str_detection}");
        for r, detection in enumerate(self.text_info):
            if(self.debug):
                annotated = cv.rectangle(annotated, tuple(np.array(detection[0][0]).astype(np.int32)), tuple(np.array(detection[0][2]).astype(np.int32)), (0,255,0), 1);
            self.labels[r] = detection[1];
            # annotated = cv.putText(annotated, detection[1],  tuple((np.array(detection[0][0]) - 5).astype(np.int32)), 
            #                     cv.FONT_HERSHEY_SIMPLEX,  0.5, (0,0,0), 2, cv.LINE_AA);
            # width and height
            wh = np.array(detection[0][2]) - np.array(detection[0][0]);
            # center box points
            ctr = np.array(detection[0][0]) + wh * 0.5;
            self.bbox[r][:2] = ctr;
            self.bbox[r][2:] = wh;
        if(self.debug):
            cv.imwrite("annotated.jpg", annotated);
    
    def getCandidateHeaders(self, num_of_candidates=30):
        h, w = self.table_only.shape[:2];
        # sort = np.array(sorted(self.bbox, key= lambda bbox: min(bbox[:2].min(), np.absolute(bbox[:2] - np.array([w,h])).min())));
        sort = np.array(sorted(self.bbox, key=lambda bbox: bbox[1]));
        self.candidates_bbox = sort[:num_of_candidates];
        candidate_img = self.table_only.copy();
        self.candidate_labels = np.empty(shape=(num_of_candidates), dtype=f"<U{self.longest_str_detection}");
        for i, candidate in enumerate(self.candidates_bbox):
            candidate_img = cv.rectangle(candidate_img, tuple((candidate[:2] - candidate[2:]/2).astype(np.int32)), tuple((candidate[:2] + candidate[2:]/2).astype(np.int32)), (0,0,255), 1);
            # find the corresponding labels to the candidate bounding box
            self.candidate_labels[i] = self.labels[(candidate == self.bbox).all(axis=1)].squeeze();

        self.helper_line = np.polyfit(self.candidates_bbox[...,0], self.candidates_bbox[...,1],1);
        self.start_x = self.candidates_bbox[..., 0].min();
        self.end_x = self.candidates_bbox[..., 0].max();
        if(self.debug):
            cv.imwrite("candidate.jpg", candidate_img);
    def getHeaders(self, header_y):
        header_img = self.table_only.copy();
        self.header_bbox = np.array(list(filter(lambda bbox: bbox[1] < header_y, iter(self.bbox))));
        self.header_bbox = np.array(sorted(self.header_bbox, key=lambda bbox: bbox[0])); # order headers from left to right
        self.non_header_bbox = np.array(list(filter(lambda bbox: bbox[1] > header_y, iter(self.bbox))));
        self.non_header_bbox = np.array(sorted(self.non_header_bbox, key= lambda bbox: bbox[1])); # sort by height and left to tright
        self.header_labels = np.empty(shape=(self.header_bbox.shape[0]), dtype=f"<U{self.longest_str_detection}");
        for i, header in enumerate(self.header_bbox):
            header_img = cv.rectangle(header_img, tuple((header[:2] - header[2:]/2).astype(np.int32)), tuple((header[:2] + header[2:]/2).astype(np.int32)), (0,0,255), 1);
            # find the corresponding labels to the candidate bounding box
            self.header_labels[i] = self.labels[(header == self.bbox).all(axis=1)].squeeze();
        if(self.debug):
            cv.imwrite("headers.jpg", header_img);
        # organize our labels
        bbox_header = [];
        header_bbox = self.header_bbox.copy();
        header_labels = self.header_labels.copy();
        self.keyheaders = [];
        # organize the headers into their respective keys
        while(header_bbox.shape[0]): 
            # draw a vertical line
            # then see if the vertical line intersect with 
            # a header box
            x = header_bbox[0][0];
            # header_bbox = np.delete(header_bbox, i, axis=0);
            bool1 = x < (header_bbox[...,0] + header_bbox[..., 2] * 0.5);
            bool2 = x > (header_bbox[...,0] - header_bbox[..., 2] * 0.5);
            key = "";
            # sort by height
            for string, _ in sorted(zip(header_labels[bool1 * bool2], header_bbox[(bool1 * bool2)]), key=lambda a: a[1][1]):
                key += string;
            self.keyheaders.append(key);
            bboxs = header_bbox[(bool1 * bool2)];
            x_min = (bboxs[..., 0] - bboxs[...,2] * 0.5).min();
            x_max = (bboxs[..., 0] + bboxs[...,2] * 0.5).max();
            y_min = (bboxs[..., 1] - bboxs[...,3] * 0.5).min();
            y_max = (bboxs[..., 1] + bboxs[...,3] * 0.5).max();

            bbox_header.append([x_min, y_min, x_max, y_max]);
            header_bbox = header_bbox[~(bool1 * bool2)];
            header_labels = header_labels[~(bool1 * bool2)];
        self.header_bbox = np.array(bbox_header);
    def load_dict(self, columns, thresh_v=15):
        bias = 2.2;
        change = True;
        count = 1;
        row = 0;
        str_info = {
        #    "order": [[]] * len(self.keys), do not use this because changing one value affects all the others
        #    "length": [[]] * len(self.keys)
            "order": [ []  for i in range(len(self.keys))],
            "length": [ []  for i in range(len(self.keys))]
        };
        hung_mat = [];
        print(self.keyheaders)
        if(len(self.keyheaders) != len(self.keys)):
            for headerkey in self.keyheaders:
                mapped = map(lambda str1, str2: fuzz.ratio(str1.replace(" ","").upper(), str2.replace(" ", "").upper()), self.keys, [headerkey] * len(self.keys));
                hung_mat.append(list(mapped));
            
            # add a row of zeros to make a s
            hung_mat = 100 - np.array(hung_mat);
            r_ind, c_ind = linear_sum_assignment(hung_mat);
            # print(r_ind, c_ind);
            self.dict = {};
            for c in c_ind:
                self.dict[self.keys[c]] = [];
            self.keys = list(self.dict.keys());

        # row crop
        # row_crop = [np.inf, 0];
        row_crop = np.array([[np.inf, 0]]);
        # print(self.labels);
        for bbox in self.non_header_bbox:
            if(change):
                # take the first value of each row to be the mean
                mean = bbox[1];
                change = False;
            variance = (bbox[1] - mean)**2 / (count);
            if(variance > thresh_v):
                change = True;
                count = 0;
                row += 1;
                row_crop = np.append(row_crop, [[np.inf, 0]], axis=0);
            row_crop[row][0] = round(min(row_crop[row][0], bbox[1] - 0.5 * bbox[3]));
            row_crop[row][1] = round(max(row_crop[row][1], bbox[1] + 0.5 * bbox[3]));
            # print(variance);
            info = str(self.labels[(self.bbox == bbox).all(axis=1)].squeeze());
            # print(info);
            list_info = [];
            for i, column in enumerate(columns):
                if(bbox[0] >= column.x1 and bbox[0] < column.x2):
                    back_column = False;
                    end_x = bbox[0] + bbox[2] * 0.5;
                    start_x = bbox[0] - bbox[2] * 0.5;
                    str_density = len(info)/bbox[2]; #density of string length/ box width
                    # check if the the bbox goes over into the other column
                    if((end_x - bias) > column.x2):
                        str_col_len = abs(start_x - column.x2) * str_density; #string length in the column
                        # put into the column over (presumably it will just be one column over)
                        list_info = [info[:round(str_col_len)], info[round(str_col_len):]];
                    elif((start_x + bias) < column.x1):
                        str_col_len = abs(end_x - column.x1) * str_density;
                        str_col_len = len(info) - str_col_len; 
                        list_info = [info[round(str_col_len):], info[:round(str_col_len)]];
                        back_column = True;
                    if(len(list_info) == 0):
                        # print(info);
                        list_info = info.split(maxsplit=0);
                    # print(list_info);
                    # print(bbox);
                    # print(column.x1, column.x2)
                    for j, string in enumerate(list_info):
                        if(back_column):
                            key = self.keys[i - j];
                        else:
                            key = self.keys[i + j];
                        
                        if(variance < thresh_v and len(self.dict[key]) > row):
                            np_order = np.array(str_info["order"][self.keys.index(key)][row]);
                            np_length = np.array(str_info["length"][self.keys.index(key)][row]);
                            bbox_x = bbox[0];
                            if(j):
                                if(back_column):
                                    bbox_x = (bbox[0] - pow(str_density, -1) * len(string));
                                else:
                                    bbox_x = (bbox[0] + pow(str_density, -1) * len(string));
                            bool_mat = np_order < bbox_x;
                            b_str = np_length[bool_mat].sum();
                            self.dict[key][row] = self.dict[key][row][:b_str] + string + self.dict[key][row][b_str:];
                            str_info["order"][self.keys.index(key)][row].insert(bool_mat.sum(), bbox_x);
                            str_info["length"][self.keys.index(key)][row].insert(bool_mat.sum(), len(string));
                        else:
                            diff = abs(len(self.dict[key]) - row);
                            for i in range(diff):
                                self.dict[key].append(None);
                                str_info["order"][self.keys.index(key)].append([]);
                                str_info["length"][self.keys.index(key)].append([]);
                            self.dict[key].append(string);
                            if(j):
                                if(back_column):
                                    str_info["order"][self.keys.index(key)].append([bbox[0] - pow(str_density, -1) * len(string)]);
                                else:
                                    str_info["order"][self.keys.index(key)].append([bbox[0] + pow(str_density, -1) * len(string)]);
                            else:
                                str_info["order"][self.keys.index(key)].append([bbox[0]]);
                            str_info["length"][self.keys.index(key)].append([len(string)]); 
                    break;
            count += 1;
        # make sure all arrays are the same length
        max_length = len(self.dict[max(self.dict, key=lambda key: len(self.dict[key]))]);
        for k, key in enumerate(self.dict.keys()):
            # clean up some of the data
            if("date".upper() not in key.upper()):
                for i, entry in enumerate(self.dict[key]):
                    if(entry == None):
                        continue;
                    self.dict[key][i] = (entry.replace("/", "")).replace("\\", "");
            else:
                # have the dates be date objects
                for i, entry in enumerate(self.dict[key]):
                    try:
                        # print(self.dict[key])
                        self.dict[key][i] = parser.parse(self.dict[key][i], dayfirst=False, yearfirst=False).date();
                    except parser.ParserError:
                        # try to parse the date manually (we know)
                        # the order should be %m/%d/%Y
                        # the ocr probably messed up parsing the slashes ('/')
                        # so just get the numbers instead and the order should just be %m/%d/%Y
                        new_date_str = '';
                        for letter in self.dict[key][i]:
                            if(letter.isnumeric()):
                                new_date_str += letter;
                        try:
                            self.dict[key][i] = datetime.strptime(new_date_str, "%m%d%Y").date();
                        except ValueError:
                            self.dict[key][i] = None;
            # Dollar amounts
            if(key == "Price"   or key == "Net Price"  or key == "Commissions Sales" \
               or key == 'Commission Payments' or key == '$ Rebates'):
                # convert any entries into their respective numerical values
                for i, entry in enumerate(self.dict[key]):
                    if(entry == None):
                        self.dict[key][i] = 0;
                        continue;
                    num = 0;
                    after_dec = 0;
                    digit_count = 0;
                    switch = True;
                    negative = 1;
                    for j in range(len(entry) - 1, -1, -1):
                        letter = entry[j];
                        if(letter == "(" or letter == ")" or letter == "-"):
                            negative = -1;
                        elif(letter.isdigit()):
                            num += pow(10, digit_count) * float(letter);
                            if(switch):
                                after_dec += 1;
                            digit_count += 1;
                        else:
                            switch = False;
                    self.dict[key][i] = num / pow(10, after_dec) * negative;
            elif(key == "Order" or key == "Invoice"):
                for i, entry in enumerate(self.dict[key]):
                    try:
                        # this is potentially dangerous
                        if(self.dict[key][i] is not None):
                            self.dict[key][i] = int(self.dict[key][i]);
                        else:
                            print(self.dict[key]);
                            print(f"None value for key: {key} at index {i}");
                            # self.dict[key][i] = 0;
                    except ValueError:
                        print(f"Could not cast {self.dict[key][i]} to integer type!");
                        print(f"Reverting to only casting numbers!");
                        numeric_only = '';
                        for letter in self.dict[key][i]:
                            if(letter.isnumeric()):
                                numeric_only += letter;
                        self.dict[key][i] = int(self.dict[key][i]);
            elif(key == "Recieved"):
                for i, entry in enumerate(self.dict[key]):
                    if(isinstance(self.dict[key], str)):
                        self.dict[key][i] = entry.upper();
                        
            diff = max_length - len(self.dict[key]);
            if(diff):
                for i in range(diff):
                    self.dict[key].append(None);
        # dont remove last row if it is not a total 
        # print(self.dict);
        self.dict["metadata"] = [[str(self.imfp.absolute()), list(row)] for row in row_crop];
        count_notna = pd.Series(data=[self.dict[key][max_length - 1] for key in self.dict.keys()]).count();
        if(not round(count_notna / len(self.dict.keys()))):
            for key in self.dict.keys(): 
                self.dict[key].pop();

        # print(str_info["order"][self.keys.index("City")]);
        
