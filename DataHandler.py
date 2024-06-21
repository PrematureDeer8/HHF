import pandas as pd
import pathlib
import numpy as np

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
        # make sure commission payments are NaN
        self.df["Commission Payments"] = pd.to_numeric(self.df["Commission Payments"]);
    # write to excel file
    def write(self, filter=None, file_name="ardent.xlsx", comparison=1):
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
        with pd.ExcelWriter(file_name, date_format="MM/DD/YYYY") as writer:
            self.df[bool_mat].to_excel(writer);
    def compare(self, comparison_file_path, file_name="unpaid.xlsx", price_diff=0.05):
        cdf = pd.read_excel(comparison_file_path, skiprows=12, usecols=lambda col: "unnamed" not in col.lower());
        # clean the cdf up a little bit
        # the total number of transactions is at the end of the close date column so get that number
        transaction_count = pd.notna(cdf["Close Date"]).sum() - 1;
        self.cdf = cdf[:transaction_count];
        for key in self.cdf.keys():
            # convert the columns in the cdf that have dates into
            # datetime objects
            if("date" in key.lower()):
                self.cdf[key] = pd.to_datetime(self.cdf[key]);
        
        # try to match every row in the cdf a row in the df
        # match by close date and invoice number for now
        unmatched = [];
        for i, (date, amnt, invoice) in enumerate(zip(self.cdf["Close Date"], self.cdf["Invoiced Amount"], self.cdf["Invoice Number"])):
            cmp = pd.Series(data=[date, amnt, invoice]);
            bool1 = pd.Series(data=[1] * len(self.df), dtype=bool);
            for index, item in enumerate(cmp):
                if(pd.notna(item)):
                    match index:
                        # date
                        case 0:
                            bool1 *= (item == self.df["Invoice Date"]);
                        # invoice amount
                        case 1:
                            # price or net price (have to match)
                            # or be less than the price difference
                            bool1 *= ((self.df["Net Price"] - item).abs() < price_diff) + ((self.df["Price"] - item).abs() < price_diff);
                        # invoice number
                        case 2:
                            bool1 *= (item == self.df["Invoice"]);
                bool1.fillna(0, inplace=True);
            bool1 = bool1.astype(dtype=bool);
            if(not bool1.sum()): 
                unmatched.append(self.cdf.loc[i]);
        # print(self.df[~matching]);
        self.unmmatched = pd.DataFrame(unmatched);
        with pd.ExcelWriter(file_name, date_format="MM/DD/YYYY") as writer:
            self.unmmatched.to_excel(writer);
    def merge_invoice(self):
        for invoice_id in self.df["Invoice"]:
            bool_mat = np.bool_([0] * len(self.df));
            # if both the invoice id and order number match 
            # then add the two net prices (and commission)...
            bool_mat += ((invoice_id == self.df["Invoice"])).to_numpy();
            if(bool_mat.sum() > 1):
                zero_index = self.df[bool_mat].index[0];
                for index in self.df[bool_mat].index[1:]:
                    # we assume that the % commission  stays the same for these invoices (among other things)
                    for key in ["Price", "Net Price", "$ Commissions Sales", "Commission Payments"]:
                        self.df.loc[zero_index, key] += self.df.loc[index, key];
                    self.df.drop(axis=0, index=index, inplace=True);
        self.df.reset_index(inplace=True);


