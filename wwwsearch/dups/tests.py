# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

import os
from documents.test_indexing import IndexTester
from documents import file_utils
from documents.models import File,Collection,Source,Index


# Create your tests here.
class Dups(IndexTester):
    def setUp(self):
        
        self.makebase()
        self.dups2_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..','tests','testdocs','dups_tree'))

        
    def test_indexmaker(self):
        index_collections=Collection.objects.all()
        #print(f'DOCSTORE: {self.docstore}')
        i=file_utils.Index_Maker(self.testdups_path,index_collections,rootpath=self.docstore)
        #print(i)
        _ind=[x for x in file_utils.Index_Maker(self.testdups_path,index_collections,rootpath=self.docstore)._index if x =='<li class="du">\n\n<span class="sb_file" id="" filename="" indexed="no"  fails="" solrid="" style="color:red;">HilaryEmailC05793347.pdf</span>\n\n\n\n\n\n</li>' ]
        #options IndexMaker(path,index_collections,specs=None,masterindex=None, rootpath=DOCSTORE, hidden_files=False,max_depth=1,check_index=True,next_url=''
        self.assertEquals(_ind[0],'<li class="du">\n\n<span class="sb_file" id="" filename="" indexed="no"  fails="" solrid="" style="color:red;">HilaryEmailC05793347.pdf</span>\n\n\n\n\n\n</li>')
        
    def remove_bfindex(self):
        try:
            os.remove(os.path.join(self.testdups_path,'.kfilespecs.p'))
        except FileNotFoundError:
            pass
        
    def test_dupindex(self):
        index_collections=Collection.objects.all()
        _ind=[x for x in file_utils.Dups_Index_Maker(self.testdups_path,index_collections,rootpath=self.docstore)._index]
        sel=[x for x in _ind if "dups\HilaryEmailC05793347.pdf" in x] 
        self.assertTrue("dups\HilaryEmailC05793347.pdf" in sel[0] )


    def test_filetree(self):
    	   x=file_utils.file_tree(self.testdups_path)
    	   tree=[f for f in x]
    	   self.assertTrue(os.path.join(self.testdups_path,'HilaryEmailC05793347.pdf')in tree )
    	   self.assertEquals(len(tree),3)
        
    def test_bigfileindex(self):
        self.remove_bfindex() #remove the stored index
        
        specs=file_utils.BigFileIndex(self.testdups_path)
        _spec=specs.files[os.path.join(self.testdups_path,'HilaryEmailC05793347.pdf')]
        
        self.assertEquals(_spec['contents_hash'],'6d50ecaf0fb1fc3d59fd83f8e9ef962cf91eb14e547b2231e18abb12f6cfa809')
        
        #only 2 files and a folder inside
        self.assertEquals(len(specs.files),4)
        

    def test_checkdups(self):
        #specs=file_utils.SqlFileIndex(self.testdups_path)
        specs=file_utils.BigFileIndex(self.testdups_path)
        specs.hash_scan()
        _d=file_utils.check_local_dups(self.testdups_path,scan_index=specs)
        
        self.assertEquals(len([d.dups for d in _d if d.local_dup]),3)
        
        
        _d=file_utils.check_local_orphans(self.testdups_path,scan_index=specs)
        self.assertTrue(len([d.__dict__ for d in _d])==0)
    
    def test_master_dups(self):
        _master_spec=file_utils.BigFileIndex(self.testdups_path)
        _master_spec.hash_scan()
        
        _d=file_utils.check_master_dups(self.testdups_path,master_index=_master_spec)
        self.assertEquals(len([d for d in _d]),3)
        
        
    def test_sql_dups(self):
        specs=file_utils.SqlFolderIndex(self.testdups_path)
        #print(specs)
        
    
    def test_stored_dups(self):
        _folder=os.path.join(self.dups2_path)
        self.assertTrue(os.path.exists(_folder))
#        self.assertRaises(file_utils.DoesNotExist,file_utils.StoredBigFileIndex,_folder)
        
        _i=file_utils.BigFileIndex(_folder,label='tempmaster')
        _i.hash_scan()
        self.assertTrue(len(_i.files),9)
        #print(_i.__dict__)
        
        _si=file_utils.StoredBigFileIndex(_folder,label='tempmaster')
        
        _si.scan_or_rescan()
        _si.files.load()
        #print(_si.files)
        self.assertTrue(len(_si.files),9)
    
    


