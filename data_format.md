# Preparation for DB data
Current scripts require 3 datasets of DB, such as MAG on local. (e.g. Authors, Paper_Author, and Paper_RefPaper.) However, you may need to modify that large-size data in order to implement these scripts. Therefore, I briefly note the process of handling the large dataset.

What I have done is the following things:
1. divide a large file into small chunks.
2. modify and format each of those small datasets to satisfy the requirements of the script.
3. Using [vaex](https://vaex.readthedocs.io/en/latest/index.html), concatenate them and export as one .hdf5 file.

This process may take hours and require local storage, but you only need to do this once in the beginning.
In my personal computer(M1 mac, RAM 16G), it takes approximately 40 min to do this process for 44G MAG data(PaperReferences.txt), which is to convert the original MAG data(PaperReferences.txt) to a .hdf5 file.

## Script
I note some commands and scripts to run the above process.
1. divide a large file into small chunks. </br>
split the large data : ```split -C 1G large_size_file``` </br>
For mac, to use ```-C``` param, you need to install coreutils, like ```brew install coreutils```. Then, use ```gsplit``` instead of ```split```. i.e. ```gsplit -C 1G large_size_file``` </br>
I am not sure what size separation would be the best, but I chose 1G in this case.

2. modify and format each of those small datasets to satisfy the requirements of the script.
I did this and the following part in python. I show the case of MAG data(PaperReferences.txt).

```python
import glob
from tqdm.contrib import tenumerate

PATH_DIR_CHUNK_FILES = '' # please set your file path where you save the chunk files.

# get all files
files = glob.glob(f'{PATH_DIR_CHUNK_FILES}/*')

for i, file in tenumerate(files):
    print(i, file)
    df_chunk = pd.read_table(file, sep='\t', names=['PaperId', 'Rfpid'])
    
    # if necessary, write nesessary modification of dataframe
     
    # check
    assert df_chunk.isnull().values.sum() == 0, f'=== {file} has null =='
    assert df_chunk.isna().values.sum() == 0, f'=== {file} has nan =='
    assert 'PaperId' in df_chunk.columns and 'Rfpid' in df_chunk.columns, f"{file} column error. It has {df_chunk.columns}" # check (please change the details to satisfy the scripts requirement)
    
    # export as csv
    df_chunk.to_csv(f'{PATH_DIR_CHUNK_FILES}/{i}.csv', index=False)
```


3. Using [vaex](https://vaex.readthedocs.io/en/latest/index.html), concatinate them and export as one .hdf5 file.

```python
import vaex
from tqdm.contrib import tenumerate

PATH_DIR_CHUNK_FILES = '' # please set your file path where you save the chunk files.

# get chunk csv files
csv_chunks = glob.glob(f'{PATH_DIR_CHUNK_FILES}/*.csv')

# concatinate csvs and make a df as vaex
v_paper_ref = vaex.open_many(csv_chunks)

# export as .hdf5 file
v_pref.export_hdf5(f'{PATH_DIR_CHUNK_FILES}/PaperReferences.csv.hdf5')
```