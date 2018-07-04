# -*- coding: utf-8 -*-
from __future__ import unicode_literals
try:
    from urllib.parse import unquote_plus
except ImportError:
    from urllib import unquote_plus
import os
from .forms import TagForm

class Page(object):
    def __init__(self,searchterm=''):
        self.searchterm=searchterm
    
    def safe_searchterm(self):
        self.searchterm_urlsafe=self.searchterm
        self.searchterm=unquote_plus(self.searchterm)

    def add_filters(self):
        self.filters={self.tag1field:self.tag1,self.tag2field:self.tag2,self.tag3field:self.tag3}
        self.filters.pop('','') #remove blank filters
        if self.tag1 or self.tag2 or self.tag3:
            self.tagfilters=True
        else:
            self.tagfilters=False
            
    @property
    def path_tags(self):
        return directory_tags(self.docpath,isfile=True)
    

class SearchPage(Page):
    def __init__(self,searchurl='',page_number=0,searchterm='',direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3=''):
        super(SearchPage,self).__init__(searchterm=searchterm)
        self.page_number=page_number
        self.direction=direction
        self.pagemax=pagemax
        self.sorttype=sorttype
        self.tag1field=tag1field
        self.tag1=tag1
        self.tag2field=tag2field
        self.tag2=tag2
        self.tag3field=tag3field
        self.tag3=tag3
        self.resultlist=[]
        self.searchurl=searchurl
        super(SearchPage,self).safe_searchterm()
        super(SearchPage,self).add_filters()
        
    def clear_(self):
        self.facets=[]
        self.facets2=[]
        self.facets3=[]
        self.tag1=''
        self.results=[]
        self.backpage,self.nextpage='',''
        self.resultcount=0
        self.pagemax=''

    def nextpages(self, results_per_page):
        pagemax=int(self.resultcount/results_per_page)+1
        if self.page_number>1:
            self.backpage=self.page_number-1
        else:
            self.backpage=''
        if self.page_number<pagemax:
            self.nextpage=self.page_number+1
        else:
            self.nextpage=''
 
    
class ContentPage(Page):
    def __init__(self,doc_id='',searchterm='',tagedit='False'):
        super(ContentPage,self).__init__(searchterm=searchterm)
        self.doc_id=doc_id
        self.tagedit=tagedit
    
    def process_result(self,result):
        self.result=result
        self.docsize=result.data.get('solrdocsize')

        #deal with dups with multi-value paths
        self.docpaths=result.data.get('docpath')
        try:
            self.docpath=self.docpaths[0]
        except:
            self.docpath=None
        self.rawtext=result.data.get('rawtext')
        self.docname=result.docname
        self.hashcontents=result.data.get('hashcontents')
        self.highlight=result.data.get('highlight','')
        self.datetext=result.datetext 
        self.data_ID=result.data.get('SBdata_ID','') #pulling ref to doc if stored in local database
        #if multivalued, take the first one
        if isinstance(self.data_ID,list):
            page.data_ID=data_ID[0]
        self.tags1=self.result.data.get('tags1',[False])[0]
        if self.tags1=='':
            self.tags1=False
        self.html=self.result.data.get('preview_html','')
        self.preview_url=self.result.data.get('preview_url','')
        self.mimetype=self.result.data.get('extract_base_type','')
#        self.next_id=result.data.get('hashcontents')
#        self.before_id=result.data.get('hashcontents')
    
    def tagform(self):
        self.initialtags=self.result.data.get(self.mycore.usertags1field,'')
        if not isinstance(self.initialtags,list):
            self.initialtags=[self.initialtags]
        self.tagstring=','.join(map(str, self.initialtags))
        return TagForm(self.tagstring)
       

def directory_tags(path,isfile=False):
    """make subfolder tags from full filepath"""
    #print('Path: {}'.format(path))
    a,b=os.path.split(path)
    if isfile:
        tags=[]
    else:
        tags=[(path,a,b)]
    path=a
    while True:
        a,b=os.path.split(path)

        if b=='/' or b=='' or b=='\\':
            #print('break')
            
            break
        tags.append((path,a,b))
        path=a
        #print(a,b)
    tags=tags[::-1]
    return tags

        
    
    
    
        