# acknow-identification


This is the script implemented in the [article](https://www.nature.com/articles/s41597-022-01585-y). This is the code to identify acknowledged individuals who are registerd in Academic database (Microsoft Academic Graph is in the article).

The codes were implemented by python3.9, but possiblly executable with other versions.

# Required dataset
This scripts require the follwoing dataset. 
All of them are .csv or table data. 

- ```df_acknow```: the input dataset.
	- This data shold have at least the columns of [Doi, AcknowName]. (Here, AcknowName = Acknoweldged scholar name).
	- AcknowName should be separated by '_'. e.g., "Hanah_Margalit"


- ```db_author```: DB data regarding authors.
	- This data shold have at least the columns of [AuthorId, DisplayName].

- ```db_paper_author```: DB data regarding paper and its authors.
	- This data shold have at least the columns of [PaperId, AuthorId].

- ```db_paper_refPaper```: DB data regarding cited papers.
	- This data shold have at least the columns of [PaperId, Rfpid]. Rfpid is the Id that is cited by PaperId. Therefore, Rfpid is part of PaperId. 

- ```df_doi_paperId```: DB data that map from doi to DB's paperId.
	- This data should have at least the columns of [Doi, PaperId].


Regarding DB dat, we used [mag data](https://www.microsoft.com/en-us/research/project/microsoft-academic-graph/).


# Files 
The main scripts consists of 2 files: Preprocessing.py & Detector.py.

## Preprocessing
Preprocessing check the data format beforehand, for the smooth analysis. Specifically, it will see 1) whether necessary column/data exist in required dataset, 2) the possibility of the interesting acknowledged names can be identified with specified DB data. 

Current scripts require 4 datasets(e.g. Authors, Paper_Author, and Paper_RefPaper.) of bibliometric DB, such as MAG, on local.  However, you may need to modify that large-size data in order to implement these scripts. Therefore, I briefly note the process of handling the large dataset. In particular, I use the module of vaex to deal with this problem, so please check it.

## Detector
Detector implement core argorthm (see [article](https://www.nature.com/articles/s41597-022-01585-y)). 

 AuthorId fully depends on which DB you use. In the article, MAG(Microsoft Academic Graph) is used.
    We only requires DOI and list(set) of acknowledged scholar names.
    By inserting those 2 infomration into the DB, we will get author's ID, possible scholarly IDs having the acknoweldged scholar names.
    Then, going through the algorithm proposed in the aritcle, we identify the acknowledged scholar ID.
    This method require the hypothesis that using DB(in this case MAG) has solved sophisticated name disambiguation problem about the authors names, and idea that acknoweldged scholars have academic records in the DB.
    Conversely, acknowledged individual whose records do not exist in DB cannot be detected. Theoretically, acknowledged scholars who have not collaboarted with acknowledging authors nor being cited in the acknowledging artcle also cannot be indentified. 

# Demo
To show how to use those 2 files and what exact kind of dataset is required, there are example code in notebook and .py files. Both of them have the exactly same usage, so please play whichever you want.
After executing the one of the demo files, result data will be save as csv (e.g. example_results.csv).
