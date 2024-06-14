import pandas as pd
import pathlib

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
    # write to excel file
    def write(self, filter=None, file_name="ardent.xlsx", comparison=0):
        bool_mat = pd.Series(data=[1 for i in range(len(self.df))], dtype=bool);
        if(filter is not None):
            # filter will be a dictionary with key value pairs
            for key in filter.keys():
                if(comparison):
                    # and comparison
                    bool_mat *= eval("self.df[key]" + filter[key]);
                else:
                    # or comparison
                    bool_mat += eval("self.df[key]" + filter[key]);
        
        with pd.ExcelWriter(file_name) as writer:
            self.df[bool_mat].to_excel(writer);
    def compare(self, comparison_file_path):
        cdf = pd.read_excel(comparison_file_path, skiprows=12, usecols=lambda col: "unnamed" not in col);
        # clean the cdf up a little bit
        # the total number of transactions is at the end of the close date column so get that number
        transaction_count = pd.notna(cdf["Close Date"]).sum() - 1;
        cdf = cdf[:transaction_count];
        