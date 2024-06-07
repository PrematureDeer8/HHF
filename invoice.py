import easyocr
import cv2 as cv
import argparse
import pathlib
import numpy as np
import string

class Invoicer:
    def __init__(self, image_file, debug=False):
        self.reader = easyocr.Reader(['en']);
        self.imfp = pathlib.Path(image_file);
        self.debug = debug;
        if(not self.imfp.exists()):
            raise ValueError(f"{self.imfp} does not exists!");
        self.img = cv.imread(str(self.imfp.absolute()));
        
    def table_outline(self, crop_amount=75, threshold=150):
        self.crop = self.img[crop_amount: -crop_amount, crop_amount:-crop_amount, :].copy();
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
        sort_tr = np.array(sorted(self.table_contours, key=lambda points: points[1]/(points[0] + 1e-6)))
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
    def readText(self, min_size=5, height_ths=1.0, width_ths=0.5, decoder="greedy"):
        self.text_info = self.reader.readtext(self.table_only, min_size=min_size, decoder=decoder, height_ths=height_ths, width_ths=width_ths, canvas_size=max(self.table_only.shape));
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
        self.non_header_bbox = np.array(list(filter(lambda bbox: bbox[1] > header_y, iter(self.bbox))));
        self.header_labels = np.empty(shape=(self.header_bbox.shape[0]), dtype=f"<U{self.longest_str_detection}");
        for i, header in enumerate(self.header_bbox):
            header_img = cv.rectangle(header_img, tuple((header[:2] - header[2:]/2).astype(np.int32)), tuple((header[:2] + header[2:]/2).astype(np.int32)), (0,0,255), 1);
            # find the corresponding labels to the candidate bounding box
            self.header_labels[i] = self.labels[(header == self.bbox).all(axis=1)].squeeze();
        if(self.debug):
            cv.imwrite("headers.jpg", header_img);
        self.dict = {};
        # organize our labels
        self.keys = [];
        bbox_header = [];
        header_bbox = self.header_bbox.copy();
        header_labels = self.header_labels.copy();
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
            for string in header_labels[bool1 * bool2]:
                key += string;
            bboxs = header_bbox[(bool1 * bool2)];
            x_min = (bboxs[..., 0] - bboxs[...,2] * 0.5).min();
            x_max = (bboxs[..., 0] + bboxs[...,2] * 0.5).max();
            y_min = (bboxs[..., 1] - bboxs[...,3] * 0.5).min();
            y_max = (bboxs[..., 1] + bboxs[...,3] * 0.5).max();

            bbox_header.append([x_min, y_min, x_max, y_max]);
            header_bbox = header_bbox[~(bool1 * bool2)];
            header_labels = header_labels[~(bool1 * bool2)];
            self.dict[key] = [];
            self.keys.append(key);
        self.header_bbox = np.array(bbox_header);
    def load_dict(self, columns):

        # print(vertical_x);
        for bbox in self.non_header_bbox:
            distance = np.abs(self.vertical_x - bbox[0]);
            print(distance);
            index = distance.argmin();
            key = self.keys[index];
            info = str(self.labels[(self.bbox == bbox).all(axis=1)].squeeze());
            self.dict[key].append(info);

# cv.circle()