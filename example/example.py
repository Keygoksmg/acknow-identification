import vaex 
import os
import time
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from preprocessing import Preprocessing
from detector import Detector

def run_preprocess(pre):
    print('\n Start Preprocessing ...')
    df_acknow = pre.adjust_df_acknow()
    v_db_author, v_db_paper_author, v_db_paper_refPaper = pre.read_db_as_vaex()

    # check
    if df_acknow.empty: 
        print('=== Acknow data(Doi or/and AcknowName) does not exist in DB data ===')
        return pd.DataFrame.from_dict({'PaperId': [], 'AcknowName':[]}), v_db_author, v_db_paper_author, v_db_paper_refPaper
    
    return df_acknow, v_db_author, v_db_paper_author, v_db_paper_refPaper
    
def run_detecor(detector, df_doi_paperId, stats=False):
    print('\n Start Detector')
    # get possible acknow Ids and dataframe
    df_acknow_possibleIds_grouped, possible_acknow_ids = detector.possible_acknoweldged_candidates_id()

    # check2
    if len(possible_acknow_ids) == 0:
        print('Possible scholar ID containing ANY AcknowName in the input data could not be found in DB')
        return

    # Collaboration approach
    df_acknow_with_collab_identified = detector.collaboration_approach(possible_acknow_ids, df_acknow_possibleIds_grouped)

    # Citation approach
    df_authorIds_citedAuthorIds_identified = detector.citation_approach(df_acknow_possibleIds_grouped)

    # Combine both approaches
    df_acknowId = detector.merge_two_approach(df_acknow_with_collab_identified, df_authorIds_citedAuthorIds_identified)

    # Formatting
    df_acknowId = detector.format_result(df_acknowId, df_doi_paperId)

    # save
    if detector.save_file != '':
        df_acknowId.to_csv(detector.save_file, index=False)
    
    # stats
    if stats:
        print(detector.stats(detector.df_acknow, df_acknowId))
        
    return df_acknowId

def _split_dataframe(df, chunk_size = 10000): 
    chunks = list()
    num_chunks = len(df) // chunk_size + 1
    for i in range(num_chunks):
        chunks.append(df[i*chunk_size:(i+1)*chunk_size])
    return chunks

def main():
    # ============ PATH ============
    # Path should be absolute path.
    PATH_ROW_ACKNOW = os.environ.get('DATA_ROWACK')
    PATH_MAG = os.environ.get('DATA_MAG')
    FILES = ['compbiology', 'biology', 'medicine', 'genetics', 'ntds', 'pathogenes', 'plosone', 'srep']


    # ============ DB (MAG) ============
    """To check the necessary data structure of DB data, 
    example csv data of DB are in the same directory 'exampleDB(mag)'. 

    .exampleDB(mag)
    ├── example_db_author.csv
    ├── example_db_paper_author.csv
    ├── example_db_paper_refPaper.csv
    └── example_df_doi_paperId.csv
    """
    print('Start reading dataset ...')
    # DB data (it should be csv or .hdf5 file)
    FILE_DB_AUTHOR = f'{PATH_MAG}/Authors/Authors.csv'
    FILE_DB_PAPER_AUTHOR = f'{PATH_MAG}/PaperAuthorAffiliations/PaperAuthorAffiliations.csv'
    FILE_DB_PAPER_REFPAPER = f'{PATH_MAG}/PaperReferences/PaperReferences.csv.hdf5'
    # doi to paperID
    df_magpaper_id_doi_plos = pd.read_table(f'{PATH_MAG}/papers_plos.txt', sep=' ', names=['PaperId', 'Doi'])
    df_magpaper_id_doi_srep = pd.read_table(f'{PATH_MAG}/papers_srep.txt', sep=' ', names=['PaperId', 'Doi'])
    df_doi_paperId = pd.concat([df_magpaper_id_doi_plos, df_magpaper_id_doi_srep])


    # ============ Acknowledgment data ============
    """To check the necessary data structure of acknowledgement data, 
    example csv data of input df_acknow is in the same directory of 'exampleAcknow'. 

    .exampleAcknow
    └── example_df_acknow.csv
    """
    # Read acknow data & concat all dfs
    # you can simple read like  df_acknow = pd.read_csv('path')
    dfs = {}
    dfs_all = pd.DataFrame()
    for file in FILES:
        print(f"read file: {file}")
        dfs[file] = pd.read_csv(f'{PATH_ROW_ACKNOW}/{file}.csv', low_memory=False)[['paperId', 'author', 'acknow']]
        dfs_all = pd.concat([dfs_all, dfs[file]])
    # rename columns
    dfs_all_renamed = dfs_all.rename({'paperId': 'Doi', 'acknow':'AcknowName'}, axis=1)

    # data to use
    df_split = _split_dataframe(dfs_all_renamed) # split into small
    acknowdata_used = df_split[0]
    print('\n End reading datasets. \n')

    # ============ PREPROCESSING ============
    # preprocessing the acknow and DB data 
    pre = Preprocessing(acknowdata_used, df_doi_paperId, FILE_DB_AUTHOR, FILE_DB_PAPER_AUTHOR, FILE_DB_PAPER_REFPAPER)
    df_acknow, v_db_author, v_db_paper_author, v_db_paper_refPaper = run_preprocess(pre)


    # ============ DETECTOR ============
    # Initialize with the necessary data
    detector = Detector(df_acknow, v_db_author, v_db_paper_author, v_db_paper_refPaper, save_file='example_results.csv')
    df_acknowId = run_detecor(detector, df_doi_paperId, stats=True)

    print('Done.')


if __name__ == "__main__":
    main()