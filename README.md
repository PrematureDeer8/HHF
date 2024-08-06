# Background

This project was implemented for a small company in order to perform document analysis. The goal of the project was to digitize mailed invoices of the company's commissions
into excel spreadsheets. Then functionality was implemented to compare the newly digitized mailed invoices with what the company had on record to make sure no commission payment was missed.

# Technical Details

HHF works by taking an input image or a directory of images. The image must have a printed table with column labels, so no functionality is supported for tables with row headers. An 
example of a sample image:
![HHFSampleData](https://github.com/user-attachments/assets/4278e6fa-243d-4c2c-8e1d-2a940666d92f)

### Preprocessing

Before conducting ocr on the sample image, some preprocessing must be done. In order to crop just the part of the image where the table is located the contours of the image are taken using opencv. The opencv method returns only the contours external to the object. So no contours found within the object are reported. Each set of contours corresponds to an object located in the image. Assuming that the sample image has relatively little noise, the object with the biggest contour area would be the table itself. So we return the contour map with the maximum area. (Notice how this disregards multiple tables on one image, so only limit one table per image!). With the contours of the table found, we need to return the corresponding cropped image. To do this opencv provides us with a method to create a rectangle of best fit for a contour map. With the rectangle of best fit when can crop the table in the image. Continuing with our sample image we would get: 


![table](https://github.com/user-attachments/assets/d32da0ba-1c39-4601-984f-3f33da4a90bf)


The last part of the preprocessing step is making sure the table is actually aligned. Meaning that the table isn't rotated in any way. To do this the we use the contours map. The contour map is a array of coordinate points. Each coordinate point corresponds to a place on the outer edge of the table, a part of the outline essentially. The program sorts for contours closest to the top right corner of the table and the top left corner of the table. Then the best 30 of each contours closest to the top right and top left corners are averaged to create a top right and top left corner point. With the top left and top right corner we recreate the top part of the outline of the table by creating a line between those two points. To calculate the angle of the line we simply calculate the slope of the line then arctangent the slope to get the angle of the table. With the angle of the table opencv provides a method to rotate the image such that the table becomes aligned. Since the sample image is already aligned this has no affect.

### OCR

Now with the preprocessing complete, the OCR part of the program can be done. The OCR model used was [EasyOCR](https://github.com/JaidedAI/EasyOCR/tree/master/easyocr). Depending on your image dimensions, the size of your words, and other factors, you will probably need to tweak the hyper-parameters that were implemented for this project to suit your images. When developing, there were numerous tweaks of the hyper-parameters to get [EasyOCR](https://github.com/JaidedAI/EasyOCR/tree/master/easyocr) to read all the words (or almost all!). OCRing our sample image we get: 


![annotated](https://github.com/user-attachments/assets/fa361b58-2a4a-4de5-a62e-42d0a809fa2f)


### Data Organization

With the OCR complete, we have to organize the data. The program will first try to find column headers for the data. In order to do this we need to approximate how many text detections compose the column headers. Just by counting the number of columns, there are 23 (this was done manually). Therefore the number of text detection is around that number and so the parameter to approximate the number of text detections was set to 30. Its important to note that this parameter should always underestimate the true number of text detections that compose the column headers. With the parameter set, we sort the text detections by height and pick the first 30. Here is the sample image on the first 30: 


![candidate](https://github.com/user-attachments/assets/67b9da5a-47dc-4061-a7e9-bc39607214bc)


Now that we have our first 30 candidates, we draw a line of best fit across the center points of all the candidate boxes.
