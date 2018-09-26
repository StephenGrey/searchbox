# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from builtins import str #backwards to 2.X
import logging, requests, json, shutil, os, re
from ownsearch import solrJson
log = logging.getLogger('ownsearch.solr_indexes')
from requests.exceptions import ConnectionError

try:
    from configs import config
    SOLR_URL=config['Solr']['url']
except:
    SOLR_URL=''

class SolrServer:
    def __init__(self,url=SOLR_URL):
        self.url=url
        
    def status_check(self):
        """make checks on solr server"""
        #print (self.url)
        try:
            ses=solrJson.SolrSession()
            res=ses.get(self.url+'admin/cores?action=STATUS')
            if res.status_code == 404:
                log.warning('404: Bad solr URL')
                self.server_up=False
            elif res.status_code == 401:
                log.warning('401: Requires authentication')
                self.server_up=False
                raise solrJson.SolrAuthenticationError
            else:
                jres=res.json()
                self.header=jres.get("responseHeader",None)
                if self.header.get('status')==0:
                    self.server_up=True
                    self.init=jres.get("initFailures",None)
                    self.status=jres.get("status",None)
                    self.getcores()
                    self.getsolrdir()
                    self.check_default_indexes()
                else:
                    self.server_up=False
        except ConnectionError:
            self.server_up=False
            raise solrJson.SolrConnectionError
        except json.JSONDecodeError:
            print('json error')
            print(res)
            self.server_up=False
            self.status=None
    
    def getcores(self):
        self.cores=[]
        for corename in self.status:
            self.cores.append(corename)
        self.core_count=len(self.cores)
                    
    def getsolrdir(self):
        self.solrdir=''
        self.solrdir_multivalued=False
        if self.cores:
            self.empty=False
            for corename in self.cores:
                this_solrdir,dirname=os.path.split(self.status[corename]['instanceDir'])
                if self.solrdir:
                    if self.solrdir != this_solrdir:
                        self.solrdir_multivalued=True
                self.solrdir=this_solrdir
        else:
            self.empty=True

    def check_default_indexes(self):
        """check if \'coreexample\' and \'tests_only\' index are up"""
        defaultstatus=self.core_status('coreexample')
        self.default_index_up=False
        if defaultstatus:
            if defaultstatus.get('name')=='coreexample' and defaultstatus['index'].get('current')==True:
                mycore=solrJson.SolrCore('coreexample')
                if mycore.ping():
                    log.info('Solr server and "coreexample" index operating and installed')
                    self.default_index_up=True
        test_index_status=self.status.get('tests_only')
        self.test_index_up=False
        if test_index_status:
            if test_index_status.get('name')=='tests_only' and test_index_status['index'].get('current')==True:
                mycore=solrJson.SolrCore('tests_only')
                if mycore.ping():
                    log.info('\"tests_only\" index operating and installed')
                    self.test_index_up=True

    def check_or_make_test_index(self):
        """if no tests only server, make it"""
        if not self.test_index_up:
            self.make_new_index('tests_only')
#            log.critical('Creating \"tests only\" index on Solr server..')
#            copy_index_schema(self.solrdir, oldname='coreexample',newname='tests_only') #default: copy coreexample to tests_only
#            create_index(os.path.join(self.solrdir,'tests_only'))
    
    def make_new_index(self,indexname,modelindex='coreexample'):
        log.critical('Creating \"{}\" index on Solr server..'.format(indexname))
        copy_index_schema(self.solrdir, oldname=modelindex,newname=indexname)
        create_index(os.path.join(self.solrdir,indexname))

            
    def core_status(self,indexname):
        return self.status.get(indexname)
        
    def index_up(self,indexname):
        defaultstatus=self.core_status(indexname)
        if defaultstatus:
            if defaultstatus.get('name')==indexname and defaultstatus['index'].get('current')==True:
                    mycore=solrJson.SolrCore(indexname)
                    if mycore.ping():
                        #print('Solr server and "coreexample" index operating and installed')
                        return True

    

def copy_index_schema(solrpath,oldname='coreexample',newname='tests_only'):
    assert os.path.exists(solrpath)
    assert os.path.isdir(solrpath)
    oldpath=os.path.join(solrpath,oldname)
    assert os.path.isdir(oldpath)
    newconfpath=os.path.join(solrpath,newname,'conf')
    oldconfpath=os.path.join(oldpath,'conf')
    
    print('Copying {} to {}'.format(oldconfpath,newconfpath))
    try:
        shutil.copytree(oldconfpath,newconfpath)
        log.critical('Copied new index \'{}\''.format(newname))
    except FileExistsError:
        log.info('\'{}\' already exists... skipping copy of index'.format(newname))
    
    log.debug('Checking \'core.properties\'')
    if check_corename(os.path.join(solrpath,newname)):
        log.debug('...\'core.properties\' already set to \'{}\''.format(newname))
    
def check_corename(instanceDir):
    assert os.path.isdir(instanceDir)
    solrdir,corename=os.path.split(instanceDir)
    namefile=os.path.join(instanceDir,'core.properties')
    if os.path.exists(namefile):
        with open(namefile,'r') as f:
            data = f.readlines()
            for line in data:
                r=re.match("name=(.*)$", line)
                if r:
                    if r[1]==corename:
                        return True
        return False

def create_index(instanceDir):
    try:
        solrdir,corename=os.path.split(instanceDir)
        assert os.path.exists(solrdir)
        create_url='{}admin/cores?action=CREATE&name={}'.format(SOLR_URL,corename)
        #print(create_url)
        res=solrJson.resGet(create_url)
        jres=res.json()
        header=jres.get("responseHeader")
        if header:
            status=header.get("status")
            if status==0:
                #print('Index created')
                return 0
            else:
                try:
                    message=jres['error']['msg']
                except:
                    message='unknown error'
                log.error('Error: {}'.format(message))
                return status
        return True
    except solrJson.Solr404:
        print('404 Error: wrong solrURL or the solr server is down')
        return 404

