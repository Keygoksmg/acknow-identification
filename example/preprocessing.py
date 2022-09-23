import os
import vaex
import pandas as pd

class Preprocessing:
    def __init__(self, df_acknow, df_doi_paperId, file_db_author, file_db_paper_author, file_db_paper_refPaper):
        self.df_acknow = df_acknow
        self.df_doi_paperId = df_doi_paperId
        self.file_db_author = file_db_author
        self.file_db_paper_author = file_db_paper_author
        self.file_db_paper_refPaper = file_db_paper_refPaper
        self.is_first_time = True
        
        # check db data as vaex
        self.check_vaex(file_db_author, )
        self.check_vaex(file_db_paper_author)
        self.check_vaex(file_db_paper_refPaper)

    def _csv_or_hdf5(self, file):
        # check file is .hdf5 or not(e.g. .csv)
        if file[-5:] == '.hdf5':
            return file
        else:
            return f"{file}.hdf5"

    def check_vaex(self, file):
        # check file is .hdf5 or not(e.g. .csv)
        hdf5file = self._csv_or_hdf5(file)

        if not os.path.exists(hdf5file):
            print(f'... convering {file} into vaex data \n It may takes hours ...')
            v = vaex.from_csv(file, convert=True, chunk_size=10_000_000)
            print('Converted! Now you can remove the original file from local.')
        print(f'OK!! DB data({hdf5file}) exits as vaex.')

    def read_db_as_vaex(self):
        """DB data tend to be huge. So we try to use them via `vaex`"""
        v_db_author = vaex.open(self._csv_or_hdf5(self.file_db_author))
        v_db_paper_author = vaex.open(self._csv_or_hdf5(self.file_db_paper_author))
        v_db_paper_refPaper = vaex.open(self._csv_or_hdf5(self.file_db_paper_refPaper))
        
        # column check
        assert 'AuthorId' in list(v_db_author.columns), f"v_db_author shold have at least the columns of [AuthorId, DisplayName]. Now it has {list(v_db_author.columns)}"
        assert 'DisplayName' in list(v_db_author.columns), f"v_db_author shold have at least the columns of [AuthorId, DisplayName]. Now it has {list(v_db_author.columns)}"
        
        assert 'PaperId' in list(v_db_paper_author.columns), f"v_db_paper_author shold have at least the columns of [PaperId, AuthorId]. Now it has {list(v_db_paper_author.columns)}"
        assert 'AuthorId' in list(v_db_paper_author.columns), f"v_db_paper_author shold have at least the columns of [PaperId, AuthorId]. Now it has {list(v_db_paper_author.columns)}"

        assert 'PaperId' in list(v_db_paper_refPaper.columns), f"v_db_paper_refPaper shold have at least the columns of [PaperId, Rfpid]. Now it has {list(v_db_paper_refPaper.columns)}"
        assert 'Rfpid' in list(v_db_paper_refPaper.columns), f"v_db_paper_refPaper shold have at least the columns of [PaperId, Rfpid]. Now it has {list(v_db_paper_refPaper.columns)}"
    
        return v_db_author, v_db_paper_author, v_db_paper_refPaper, 

    def adjust_df_acknow(self):
        """
        - df_acknow shold have at least the columns of [Doi, AcknowName]. (Here, AcknowName = Acknoweldged scholar name).
        - AcknowName should be separated by '_'. e.g., "Hanah_Margalit"
        """
        def _column_name_heck():
            # check for df_acknow
            assert 'Doi' in self.df_acknow.columns, f"df_acknow shold have at least the columns of [Doi, AcknowName]. Now it has {self.df_acknow.columns}"
            assert 'AcknowName' in self.df_acknow.columns, f"df_acknow shold have at least the columns of [Doi, AcknowName]. Now it has {self.df_acknow.columns}"

            # check for df_doi_paperId
            assert 'Doi' in self.df_doi_paperId.columns, f"df_doi_paperId shold have at least the columns of [Doi, PaperId]. Now it has {self.df_doi_paperId.columns}"
            assert 'PaperId' in self.df_doi_paperId.columns, f"df_doi_paperId shold have at least the columns of [Doi, PaperId]. Now it has {self.df_doi_paperId.columns}"
            

        def _adjast_acknow_name():
            """Since in MAG's author data, DisplayName have data such as 'Flavio Roces'. So adjust to this data type.
            """
            self.df_acknow['AcknowName'] = self.df_acknow['AcknowName'].apply(lambda x: " ".join(x.split('_')))

        def _doi2paperId():
            # read data
            # df_doi2paperId = pd.read_table(f'{PATH_MAG}/papers_plos.txt', sep=' ', names=['PaperId', 'Doi'])
            df_doi2paperId = self.df_doi_paperId

            # change doi to lower case
            df_doi2paperId["Doi"] = df_doi2paperId["Doi"].str.lower()

            # clear error row: Eliminate cases where multiple paper ids are assigned to a single doi.
            _df_doi2paperId = df_doi2paperId['Doi'].value_counts()
            available_ids = set(_df_doi2paperId[_df_doi2paperId.values == 1].index)
            df_doi2paperId_fixed = df_doi2paperId[df_doi2paperId['Doi'].isin(available_ids)]

            # replace the column of 'Doi' to 'PaperId'
            self.df_acknow = pd.merge(self.df_acknow, df_doi2paperId_fixed,  
                    how='inner', on='Doi')[['PaperId', 'AcknowName']]


        if self.is_first_time:
            _column_name_heck()
            _adjast_acknow_name()
            _doi2paperId()
            self.is_first_time = False
            return self.df_acknow
        else:
            print('You might have already done this process. Once is enough')
            return self.df_acknow
