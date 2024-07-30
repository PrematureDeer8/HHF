import pandas as pd
import pathlib
import numpy as np
from fuzzywuzzy import fuzz
import cv2 as cv
from invoice import Invoicer

class DataHandler:
    def __init__(self, dictionary, existing_file=None) -> None:
        self.new_data = pd.DataFrame(data=dictionary);
        self.ef = existing_file;
        if(existing_file is not None):
            self.ef = pathlib.Path(existing_file);
            if(not self.ef.exists()):
                raise ValueError(f"{self.ef} path does not exist!");
            # merge existing data with new data
            self.edf = pd.read_excel(existing_file, index_col=0); #use 0th column as the index column
            frames = [self.edf, self.new_data];
            self.df = pd.concat(frames, ignore_index=True);

        else:
            self.df = self.new_data;
        # for column in self.df.columns:
        #     if("date" in column.lower()):
        #         self.df.loc[:, column] = pd.to_datetime(self.df.loc[:, column]);
    # write to excel file
    def write(self, filter=None, file_name="ardent.xlsx", comparison=1, hidden_col=None):
        bool_mat = pd.Series(data=[1 for i in range(len(self.df))], dtype=bool);
        if(not comparison):
            bool_mat = ~bool_mat;
        # print(bool_mat);
        if(filter is not None):
            # filter will be a dictionary with key value pairs
            for key in filter.keys():
                if(comparison):
                    # and comparison
                    bool_mat *= eval("self.df[key] " + filter[key]);
                else:
                    # or comparison
                    bool_mat += eval("self.df[key] " + filter[key]);
                    # print(pd.DataFrame(data=(bool_mat, self.df[key])));
                # nan values wont be considered (by default)
                bool_mat *= pd.notna(self.df[key]);
        with pd.ExcelWriter(file_name, date_format="MM/DD/YYYY", engine="xlsxwriter") as writer:
            self.df[bool_mat].to_excel(writer, sheet_name='Sheet1');
            if(hidden_col is not None):
                worksheet = writer.sheets['Sheet1'];
                worksheet.set_column(hidden_col[0], hidden_col[0], hidden_col[1]);
                # worksheet.save();

    def img_info(self, bool_mat):
        for i, metadata in enumerate(self.df.loc[bool_mat, "metadata"]):
            # metadata: "['img_path', [ymin, ymax]]"
            # with eval metadata(str) turns it back into metadata(list)
            metadata = eval(metadata);
            row_num = self.df.loc[bool_mat].index[i];
            detailer = Invoicer(metadata[0], ocr=False);
            # if(not path.exists()):
            #     print(f"Image path for row {row_num} does not exist!");
            #     continue;
            detailer.table_outline(crop_amount=10);
            detailer.align_table();
            src_img = detailer.table_only;
            cropped_img = np.empty(shape=(0,src_img.shape[1],3));
            for ymin, ymax in metadata[1:]:
                cropped_img = np.append(src_img[int(ymin):int(ymax)], cropped_img, axis=0);
            cv.imwrite(f"row{row_num}.jpg", cropped_img);
    def compare(self, comparison_file_path, file_name="unpaid.xlsx", price_diff=0.05, string_diff=60, skiprows=12):
        cdf = pd.read_excel(comparison_file_path, skiprows=skiprows, usecols=lambda col: "unnamed" not in col.lower());
        # clean the cdf up a little bit
        # the total number of transactions is at the end of the close date column so get that number
        transaction_count = pd.notna(cdf["Close Date"]).sum();
        self.cdf = cdf[:transaction_count];
        for key in self.cdf.keys():
            # convert the columns in the cdf that have dates into
            # datetime objects
            if("date" in key.lower()):
                self.cdf.loc[:,key] = pd.to_datetime(self.cdf[key]);
            # better be a number when doing the comparison
            elif(key == "Invoice Number" or key == "Invoiced Amount"):
                self.cdf.loc[:, key] = pd.to_numeric(self.cdf.loc[:, key], errors='coerce');

            
        
        # try to match every row in the cdf a row in the df
        # match by close date and invoice number for now
        unmatched = [];
        for i, (date, amnt, invoice, account) in enumerate(zip(self.cdf["Close Date"], self.cdf["Invoiced Amount"], self.cdf["Invoice Number"], self.cdf["Account Name"])):
            cmp = pd.Series(data=[date, amnt, invoice, account]);
            bool1 = pd.Series(data=[1] * len(self.df), dtype=bool);
            for index, item in enumerate(cmp):
                if(pd.notna(item)):
                    match index:
                        # date
                        case 0:
                            pass;
                            # bool1 *= (item == self.df["Invoice Date"]);
                        # invoice amount
                        case 1:
                            # price or net price (have to match)
                            # or be less than the price difference
                            bool1 *= ((self.df["Net Price"] - item).abs() < price_diff) + ((self.df["Price"] - item).abs() < price_diff);
                        # invoice number
                        case 2:
                            bool1 *= (item == self.df["Invoice"]);
                        case 3:
                            bool1 *= self.df.loc[: ,"Customer"].map(lambda element: fuzz.partial_ratio(element.upper().replace(" ", ""), item.upper().replace(" ", ''))) > string_diff;
                bool1.fillna(0, inplace=True);
            bool1 = bool1.astype(dtype=bool);
            if(not bool1.sum()): 
                unmatched.append(self.cdf.loc[i]);
        # print(self.df[~matching]);
        self.unmmatched = pd.DataFrame(unmatched);
        with pd.ExcelWriter(file_name, date_format="MM/DD/YYYY") as writer:
            self.unmmatched.to_excel(writer);
    def merge_invoice(self, string_diff=75):
        # make every entry in the df is unique
        cp_fillNa = self.df.copy(deep=True);
        cp_fillNa.fillna(np.inf, inplace=True);
        bool_mat = pd.Series(data=[0]*len(cp_fillNa), dtype=bool);
        indices = set([]);
        for i in range(len(cp_fillNa)):
            if(i in indices):
                continue;
            inner_bool_mat = pd.Series([1]*len(cp_fillNa), dtype=bool);
            # for all column datatypes that are objects make them a string
            # for easy comparison
            for t, column in zip(cp_fillNa.dtypes, cp_fillNa.columns):
                if(isinstance(t, np.dtypes.ObjectDType)):
                    cp_fillNa.loc[:, column] = cp_fillNa.loc[:, column].astype(str);
                    # use fuzzy wuzzy for strings
                    str2 = cp_fillNa.loc[i, column].upper().replace(" ", "");
                    inner_bool_mat *= (cp_fillNa.loc[:, column].map(lambda element: fuzz.partial_ratio(element.upper().replace(" ", ""), str2)) > string_diff);
                else:
                    inner_bool_mat *=  cp_fillNa.loc[:, column] == cp_fillNa.loc[i, column];
            bool_mat += (cp_fillNa.loc[i] == cp_fillNa).all(axis=1);
            bool_mat.loc[i] = False;
            numpied = bool_mat.to_numpy();
            # update set to add indices
            indices |= set(list(np.flatnonzero(numpied)));
        # unique values only
        self.df = self.df.loc[~bool_mat];
                
        for invoice_id in self.df["Invoice"]:
            bool_mat = np.bool_([0] * len(self.df));
            # if both the invoice id and order number match 
            # then add the two net prices (and commission)...
            bool_mat += ((invoice_id == self.df["Invoice"])).to_numpy();
            if(bool_mat.sum() > 1):
                zero_index = self.df[bool_mat].index[0];
                for index in self.df[bool_mat].index[1:]:
                    self.df.loc[zero_index, "metadata"]
                    # we assume that the % commission  stays the same for these invoices (among other things)
                    for key in ["Price", "Net Price", "Commissions Sales", "Commission Payments"]:
                        self.df.loc[zero_index, key] += self.df.loc[index, key];
                    self.df = self.df.drop(axis=0, index=index);
        self.df.reset_index(inplace=True);

