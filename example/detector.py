import pandas as pd
import vaex
import time
import numpy as np

class Detector:
    """
    This class implements core argorthm (see [article](https://www.nature.com/articles/s41597-022-01585-y)). 

    AuthorId entirely depends on which DB you use. In the article, MAG(Microsoft Academic Graph) is used.
    We only require DOI and acknowledged scholar names.

    By inserting them into the DB, we will get possible scholarly IDs having the acknowledged scholar names.
    Then, going through the algorithm proposed in the article, we identify the acknowledged scholar ID.
    This method requires the hypothesis that DB(in this case MAG) has solved name disambiguation problems 
    about the author's names with a well-developed algorithm and idea that acknowledged scholars have academic records in the DB.

    Conversely, acknowledged individuals whose records do not exist in DB cannot be detected (e.g., parents and private friends).
    As another limitation, acknowledged scholars who have not collaborated with acknowledging authors or have not been cited in the article also cannot be identified.  
    """

    def __init__(self, df_acknow, db_author, db_paper_author, db_paper_refPaper, save_file='', log=False):
        # acknowledgement data 
        self.df_acknow = df_acknow # [PaperId, AcknowName]
        assert not self.df_acknow.empty, "df_acknow is empty. Check Preprocessing."

        # 3 types of DB data
        self.vaex_author = db_author # vaex column contains at least [AuthorId, DisplayNames] # author's DisplayNames should be Capital in inital Alphabet and separated by splace. e.g., Flavio Roces
        self.vaex_paper_author = db_paper_author # vaex column contains at least [PaperId, AuthorId]
        self.vaex_paper_refPaper = db_paper_refPaper# vaex column contains at least [PaperId, Rfpid] *rfpid = referece paperId that is cited by paperId

        self.save_file = save_file

    def possible_acknoweldged_candidates_id(self):
        print('Start possible scholar Id search')
        time_sta = time.time()
        """
        This class finds possible scholar ID only by names.
        We only search by exact name matching between the given data and DB.
        For example, if we have the name "Keigo Kusumegi," we look for the scholar IDs that contain this name.

        REQUIRE:
            self.df_acknow, self.vaex_author
        RETURN:
            dataframe such as | AcknowName: str | PossibleAcknowIds: set of int |
        """
        # list of acknowledged scholar names
        acknow_names = list(set(self.df_acknow['AcknowName'].tolist()))
        
        # df_author
        df_acknow_possibleIds = self.vaex_author[self.vaex_author['DisplayName'].isin(acknow_names)][['AuthorId', 'DisplayName']].to_pandas_df()

        # In case self.vaex_paper_author comes from MAG and contains value of "OriginalAuthor" which is the same as 'DisplayName', we will search potential ID from this data as well.
        if 'OriginalAuthor' in list(self.vaex_paper_author.columns):
            df_acknow_possibleIds2 = self.vaex_paper_author[(self.vaex_paper_author['OriginalAuthor'] \
                .isin(acknow_names))][['AuthorId', 'OriginalAuthor']] \
                .to_pandas_df() \
                .rename({'OriginalAuthor': 'DisplayName'}, axis=1)

            # merge them
            df_acknow_possibleIds = pd.concat([df_acknow_possibleIds, df_acknow_possibleIds2]).drop_duplicates()
        
        # possible acknowledged scholars Ids
        possible_acknow_ids = list(df_acknow_possibleIds['AuthorId'].unique())

        # group by DisplayName
        df_acknow_possibleIds_grouped = df_acknow_possibleIds.groupby('DisplayName')['AuthorId'].apply(set) \
            .reset_index() \
            .rename({'AuthorId': 'PossibleAcknowId'}, axis=1)
        
        print('End possible_acknoweldged_candidates_id (Time in this part: {:.2f}s)'.format(time.time() - time_sta))
        return df_acknow_possibleIds_grouped, possible_acknow_ids


    def collaboration_approach(self, possible_acknow_ids, df_acknow_possibleIds_grouped):
        """
        The goal is to create authors' and collaborators' ID datasets. such as {authorId: [collaboraterIds]}.

        sub  STEP 1. find target authorsIds
        sub  STEP 2. author: [published_paperIds]
        sub  STEP 3. published_paperId: [collaboratorIds]  *collaboratorIds==authorsIds
        sub  STEP 4. merging 2. & 3., create author: [collaboratorIds]
        """
        print('Start collaboration_approach')
        time_sta = time.time()
        # create dataframe of author and collaboratos
        def _find_target_authorIds():
            # get necessary `authorIds` of papers that send acknowledgements
            target_paperIds = list(self.df_acknow['PaperId'].unique())
            df_paper_acknow_neccesary = self.vaex_paper_author[self.vaex_paper_author.PaperId.isin(target_paperIds)].to_pandas_df()

            print('    - sub step1 : _find_target_authorIds. (Time: {:.2f}s)'.format(time.time() - time_sta))
            return list(df_paper_acknow_neccesary['AuthorId'].unique()), df_paper_acknow_neccesary.groupby('PaperId')['AuthorId'].apply(list).reset_index() # [PaperId, [AuthorId]]

        def _published_paperIds_of_target_authors(target_authorIds: list):            
            # targe_authorIdsのpublishした論文たち
            _df_paper_acknow_neccesary = self.vaex_paper_author[self.vaex_paper_author.AuthorId.isin(target_authorIds)].to_pandas_df()
            df_pub_paperIds_of_target_authors = _df_paper_acknow_neccesary.groupby('AuthorId')['PaperId'].apply(list).reset_index() \
                .rename({'PaperId': 'PublishedPaperId'}, axis=1)

            print('    - sub step2: _published_paperIds_of_target_authors. (Time: {:.2f}s)'.format(time.time() - time_sta))
            return df_pub_paperIds_of_target_authors # {authors(AuthorId), [published_paperIds(PaperId)]}

        def _collaborators_of_paperId(df_pub_paperIds_of_target_authors, possible_acknow_ids: list):
            """{published_paperId: [collaboratorIds]}を作っていく。
            しかし,target_authorsがpublishした論文の共著者たちを全て調べていくと,膨大な数のcollaboratorが見つかる。
            そこで,今回興味があるのは,target_authorsのcollaboratorかつAcknowNameに当てはまる人である. よってこの条件で限定してデータ量を減らす。
            """
            # published paperId by target_authors
            pub_paperIds = list(df_pub_paperIds_of_target_authors.explode('PublishedPaperId')['PublishedPaperId'].unique())
            
            # all collaborators of target_authors
            print('      -- get all collaborators of target_authors')
            _vaex_paper_acknow_neccesary = self.vaex_paper_author[self.vaex_paper_author.PaperId.isin(pub_paperIds)]

            # confine collaborators by using possible acknowledged scholars Ids(=acknow_candidate_ids)
            print('      -- confine collaborators by using possible acknowledged scholars Ids(=acknow_candidate_ids) ')
            _df_paper_acknow_neccesary = _vaex_paper_acknow_neccesary[_vaex_paper_acknow_neccesary['AuthorId'].isin(possible_acknow_ids)].to_pandas_df()
    
            # rename and groupby
            df_collabIds_of_pub_paperIds = _df_paper_acknow_neccesary.groupby('PaperId')['AuthorId'].apply(list).reset_index() \
                .rename({'AuthorId': 'CollaboratedAuthorId'}, axis=1)

            print('    - sub step3: _collaborators_of_paperId. (Time: {:.2f}s)'.format(time.time() - time_sta))
            return df_collabIds_of_pub_paperIds # {published_paperId(PaperId), [collaboratorIds(AuthorId)]]}

        def _merge_to_create_author_collabIds(df_pub_paperIds_of_target_authors, df_collabIds_of_pub_paperIds):
            # explode authors: [published_paperIds]
            df_pub_paperIds_of_target_authors_exploded = df_pub_paperIds_of_target_authors.explode('PublishedPaperId')
            
            # Merge using `published_paperId` and `PaperId`
            df_merged = pd.merge(df_pub_paperIds_of_target_authors_exploded, df_collabIds_of_pub_paperIds,  
                  how='inner', left_on='PublishedPaperId', right_on='PaperId')[['AuthorId', 'CollaboratedAuthorId']]

            print('    - sub step4: _merge_to_create_author_collabIds. (Time: {:.2f}s)'.format(time.time() - time_sta))
            return df_merged.explode("CollaboratedAuthorId").groupby('AuthorId')['CollaboratedAuthorId'].apply(set).reset_index()

        """Step1. create dataframe of author and collaboratos"""
        target_authorIds, df_target_paper_authorIds = _find_target_authorIds() # 1. 謝辞を送ってる人たちのId
        df_pub_paperIds_of_target_authors = _published_paperIds_of_target_authors(target_authorIds) # 2. authors: [published_paperIds]
        df_collabIds_of_pub_paperIds = _collaborators_of_paperId(df_pub_paperIds_of_target_authors, possible_acknow_ids) # 3. published_paperId: [collaboratorIds]  *collaboratorIds==authorsIds
        if df_collabIds_of_pub_paperIds.empty:
            print('There is not possible collaboration between acknowledging and acknowledged scholars')
            return pd.DataFrame(columns=['PaperId', 'AcknowName', 'CommonScholarId'])
        
        df_author_collaborators = _merge_to_create_author_collabIds(df_pub_paperIds_of_target_authors, df_collabIds_of_pub_paperIds) # 4. mergeing 2. & 3., create author: [collaboratorIds]

        print('  - Done: Step1.')
        """Step2. DataFrame: [PaperId, AcknowName, Author, [AuthorIds(=from name search)], [collaboratorIds]] を作る"""
        # add df_collabIds_of_pub_paperIds: {published_paperIds(PaperId), [collaboratorIds(AuthorId)]] to self.df_acknow: [PaperId, AcknowName]) and explode AuthorId
        # df_acknow_with_authorIds = pd.merge(self.df_acknow, df_collabIds_of_pub_paperIds, how='inner', on='PaperId')[['PaperId', 'AcknowName', 'AuthorId']]
        df_acknow_with_authorId_exploded = pd.merge(self.df_acknow, df_target_paper_authorIds, how='inner', on='PaperId').explode('AuthorId') # ['PaperId', 'AcknowName', 'AuthorId']

        # add [collaboratorIds]を追加する
        df_acknow_with_collab = pd.merge(df_acknow_with_authorId_exploded, df_author_collaborators,  
              how='inner', on='AuthorId') # ['PaperId', 'AcknowName', 'AuthorId', '[collaboratorIds]']

        # AuthorIds(=from name search)
        df_acknow_with_collab_authorIds = pd.merge(df_acknow_with_collab, df_acknow_possibleIds_grouped, \
            how='inner', left_on ='AcknowName',right_on='DisplayName') # [PaperId, AcknowName, [AuthorIds(=from name search)]]
        
        print('  - Done: Step2. (Time: {:.2f}s)'.format(time.time() - time_sta))

        """Step3. find intersected scholar ID between PossibledAcknowId and CollaboratedAuthorId as the identified scholar"""
        df_acknow_with_collab_authorIds['CommonScholarId'] = df_acknow_with_collab_authorIds.apply(lambda row : row['PossibleAcknowId'] & row['CollaboratedAuthorId'], axis=1)
        df_acknow_with_collab_detected = df_acknow_with_collab_authorIds[df_acknow_with_collab_authorIds['CommonScholarId'] != set()][['PaperId', 'AcknowName', 'CommonScholarId']]
        df_acknow_with_collab_identified = df_acknow_with_collab_detected[df_acknow_with_collab_detected['CommonScholarId'].apply(len) == 1]
        # change set to int
        df_acknow_with_collab_identified['CommonScholarId'] = df_acknow_with_collab_identified['CommonScholarId'].apply(lambda x: list(x)[0])

        print('  - Done: Step3. (Time: {:.2f}s)'.format(time.time() - time_sta))
        return df_acknow_with_collab_identified


    def citation_approach(self, df_acknow_possibleIds_grouped):
        """各論文がだれを引用しているのかを示すDataFrameを作る。Create dataframe: [PaperId, [ReferencedAuthorIds]]"""
        print('Start citation_approach')
        time_sta = time.time()
        # find target papers.
        target_paperIds = self.df_acknow['PaperId'].tolist()

        # referenced paperIds cited by target_papers
        df_ref_papers = self.vaex_paper_refPaper[self.vaex_paper_refPaper['PaperId'].isin(target_paperIds)].to_pandas_df() # [PaperId, Rfpid(=PaperId but cited)]

        # Authors of referenced papers
        ref_paperIds = list(df_ref_papers['Rfpid'].unique())
        df_author_of_ref_paper = self.vaex_paper_author[self.vaex_paper_author['PaperId'].isin(ref_paperIds)].to_pandas_df() # [AuthorId, PaperId]
        df_author_of_ref_paper_grouped = df_author_of_ref_paper.groupby('PaperId')['AuthorId'].apply(list).reset_index().rename({'AuthorId': 'ReferencedAuthorId', 'PaperId':'ReferencedPaperId'}, axis=1)

        # merge them
        _df_paper_citedAuthorIds = pd.merge(df_ref_papers, df_author_of_ref_paper_grouped, \
            how='inner',left_on ='Rfpid',right_on='ReferencedPaperId')
        df_paper_citedAuthors = _df_paper_citedAuthorIds.explode('ReferencedAuthorId').groupby('PaperId')['ReferencedAuthorId'].apply(set).reset_index()
        # df_paper_citedAuthors: [PaperId, [ReferencedAuthorId]]

        print('  - Done: Step1. (Time: {:.2f}s)'.format(time.time() - time_sta))

        """ Step2. create dataframe of [PaperId, AcknowName, [AuthorIds(=from name search)], [ReferencedAuthorId]] """
        df_authorIds = pd.merge(self.df_acknow, df_acknow_possibleIds_grouped, \
            how='inner',left_on ='AcknowName',right_on='DisplayName') # [PaperId, AcknowName, [AuthorIds(=from name search)]]
        
        df_authorIds_citedAuthorIds = pd.merge(df_authorIds, df_paper_citedAuthors, \
            how='inner', on='PaperId') # [PaperId, AcknowName, [AuthorIds(=from name search)], [ReferencedAuthorIds]]
        
        print('  - Done: Step2. (Time: {:.2f}s)'.format(time.time() - time_sta))

        """Step3. find intersected scholar ID between AuthorIds and ReferencedAuthorIds as the identified scholar"""
        df_authorIds_citedAuthorIds['CommonScholarId'] = df_authorIds_citedAuthorIds.apply(lambda row : row['PossibleAcknowId'] & row['ReferencedAuthorId'], axis=1)
        df_authorIds_citedAuthorIds_detected = df_authorIds_citedAuthorIds[df_authorIds_citedAuthorIds['CommonScholarId'] != set()][['PaperId', 'AcknowName', 'CommonScholarId']]
        df_authorIds_citedAuthorIds_identified = df_authorIds_citedAuthorIds_detected[df_authorIds_citedAuthorIds_detected['CommonScholarId'].apply(len) == 1]
        # change set to int
        df_authorIds_citedAuthorIds_identified['CommonScholarId'] = df_authorIds_citedAuthorIds_identified['CommonScholarId'].apply(lambda x: list(x)[0])

        return df_authorIds_citedAuthorIds_identified


    def merge_two_approach(self, df_acknow_with_collab_identified, df_authorIds_citedAuthorIds_identified):
        print('Merging collab. and citation approach results ...')
        # merge them
        df_acknow_with_collab_identified = df_acknow_with_collab_identified.rename({'CommonScholarId': 'CommonScholarId_by_colla'}, axis=1)
        df_authorIds_citedAuthorIds_identified = df_authorIds_citedAuthorIds_identified.rename({'CommonScholarId': 'CommonScholarId_by_ref'}, axis=1)
        
        df_merged_collab_ref = pd.merge(df_acknow_with_collab_identified, df_authorIds_citedAuthorIds_identified,  
                how='outer', on=['PaperId', 'AcknowName'])
        # drop duplicated row
        df_merged_collab_ref = df_merged_collab_ref.drop_duplicates(subset=['PaperId', 'AcknowName'])

        """divide into 3 types of results: `only colab`, `only citation`, and `both`"""
        # Acknoweldged scholars identified only by collaboration approach
        df_acknowId_from_d1Collab = df_merged_collab_ref[df_merged_collab_ref['CommonScholarId_by_ref'].isnull()]
        # Acknoweldged scholars identified only by citation approach
        df_acknowId_from_ref = df_merged_collab_ref[df_merged_collab_ref['CommonScholarId_by_colla'].isnull()]
        # Acknoweldged scholars identified by both collaboration and citation approach
        df_acknowId_from_both = df_merged_collab_ref[df_merged_collab_ref['CommonScholarId_by_colla'] == df_merged_collab_ref['CommonScholarId_by_ref']]

        # IDs of acknowledged scholars
        df_acknowId = pd.concat([df_acknowId_from_d1Collab, df_acknowId_from_ref, df_acknowId_from_both])

        # make new acknowId col
        df_acknowId['AcknowId'] = [ int(row['CommonScholarId_by_colla']) if np.isnan(row['CommonScholarId_by_ref']) else int(row['CommonScholarId_by_ref']) for i, row in df_acknowId.iterrows()]
        df_acknowId['AcknowId'] = df_acknowId['AcknowId'].astype(int)

        return df_acknowId


    def format_result(self, df_acknowId, df_doi_paperId):
        print('Format the resutls')
        def _repair_doi(df_acknowId, df_doi_paperId):
            df_acknowId = pd.merge(df_acknowId, df_doi_paperId, how='inner', on='PaperId')
        
        def _add_approach(df_acknowId):
            df_acknowId.fillna(False)
            df_acknowId['CollaborationApproach'] = df_acknowId['CommonScholarId_by_colla'].apply(lambda x: False if np.isnan(x) else True)
            df_acknowId['CitationApproach'] = df_acknowId['CommonScholarId_by_ref'].apply(lambda x: False if np.isnan(x) else True)
            df_acknowId.drop(columns=['CommonScholarId_by_colla', 'CommonScholarId_by_ref'])

        _repair_doi(df_acknowId, df_doi_paperId)
        _add_approach(df_acknowId)
        return df_acknowId


    def stats(self, df_acknow, df_result):
        results = {
        "Num of input scholars names": df_acknow['AcknowName'].nunique(),
        "Num of input papers": df_acknow['PaperId'].nunique(),
        "Num of identified acknowledged scholars": df_result['AcknowId'].nunique(),
        "Num of papers with identified acknowledged scholars": df_result['PaperId'].nunique(),
        "Proportion of identified scholars per input names": "{:.4f}".format(df_result['AcknowId'].nunique()/ df_acknow['AcknowName'].nunique()),
        "Num identified scholars by Collab. approach": len(df_result[(df_result['CollaborationApproach'] == True) & (df_result['CitationApproach'] == False)]),
        "Num identified scholars by Reference approach": len(df_result[(df_result['CollaborationApproach'] == False) & (df_result['CitationApproach'] == True)]),
        "Num identified scholars by Both approach": len(df_result[(df_result['CollaborationApproach'] == True) & (df_result['CitationApproach'] == True)]),
        "Overall computational time": 1
        }
        return results