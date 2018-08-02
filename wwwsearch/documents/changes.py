# -*- coding: utf-8 -*-
from .models import File,Collection
from documents import file_utils
#from ownsearch.hashScan import FileSpecTable as filetable
#from ownsearch.hashScan import hashfile256 as hexfile
#from ownsearch.hashScan import pathHash
from ownsearch import solrJson
import logging,os
log = logging.getLogger('ownsearch.docs.changes')

class ChangesError(Exception):
    pass

class Scanner:
    def __init__(self,collection,test=False):
        if not isinstance(collection, Collection):
            raise ChangesError('Not a valid collection')
        self.collection=collection
        self.test=test
        self.unchanged_files,self.changed_files,self.moved_files,self.new_files,self.deleted_files=[],[],[],[],[]
        self.missing_files,self.new_files_hash={},{}
        self.scan_error=False
        self.process()

    
    def process(self):
        self.scan()
        self.find_on_disk()
        self.scan_new_files()
        self.new_or_missing()
        self.count_changes()
        log.info('NEWFILES>>>>>{}'.format(self.new_files))
        log.info('DELETEDFILES>>>>>>>{}'.format(self.deleted_files))
        log.info('MOVED>>>>:{}'.format(self.moved_files))
        print('NOCHANGE>>>',self.unchanged_files)
        log.info('CHANGEDFILES>>>>>>{}'.format(self.changed_files))
          
    def scan(self):
        """1. scan all files in collection"""
        
        self.files_on_disk=file_utils.filespecs(self.collection.path) #get dict of specs of files in disk folder(and subfolders)
        self.files_in_database=File.objects.filter(collection=self.collection)
        

    def find_on_disk(self):
        """2. loop through files in the database"""
        for database_file in self.files_in_database:
            if database_file.filepath in self.files_on_disk:
                self.find_unchanged(database_file)
            else: #file has been deleted or moved
                self.missing_files[database_file.filepath]=database_file.hash_contents

    def find_unchanged(self,database_file):
        """2a. For a database file found on disk - add to changed or unchanged list/dict"""
        file_meta=self.files_on_disk.pop(database_file.filepath)
        
        latest_lastmodified=solrJson.timestamp2aware(file_meta.last_modified) #gets last modified info as stamp, makes GMT time object
        latestfilesize=file_meta.length
        if database_file.last_modified==latest_lastmodified and latestfilesize==database_file.filesize:
            #print(path+' hasnt changed')
            self.unchanged_files.append(database_file.filepath)
        else:
            #print(path+' still there but has changed')
            self.changed_files.append(database_file.filepath)
            log.debug('Changed file: \nStored date: {} New date {}\n Stored filesize: {} New filesize: {}'.format(database_file.last_modified,latest_lastmodified,database_file.filesize,latestfilesize))

    def scan_new_files(self):
        """3. make index of remaining files found on disk, using contents hash)"""
        for newpath in self.files_on_disk:
            if not self.files_on_disk[newpath].folder:
                newhash=file_utils.get_contents_hash(newpath)
                if newhash in self.new_files_hash:
                    self.new_files_hash[newhash].append(newpath)
                else:
                    self.new_files_hash[newhash]=[newpath]
            else:
                #print('New folder found: {}'.format(newpath))
                self.new_files.append(newpath)

    def new_or_missing(self):        
        """4. now work out which new files have been moved """
        for missingfilepath in self.missing_files:
            missinghash=self.missing_files[missingfilepath]
            
            newpaths=self.new_files_hash.get(missinghash)
            if newpaths:
                #take one of the new files from list (no particular logic on which is moved / new)
                newpath=newpaths.pop()
                #put back the reduced list
                self.new_files_hash[missinghash]=newpaths
                #print(os.path.basename(missingfilepath)+' has moved to '+os.path.dirname(newpath))
                self.moved_files.append([newpath,missingfilepath])
            else: #remaining files have been deleted
                self.deleted_files.append(missingfilepath)
      
      #remaining files in newfilehash are new 
        for newhash in self.new_files_hash:
            newpaths=self.new_files_hash[newhash]
            for newpath in newpaths:
                self.new_files.append(newpath)
                
    def update_database(self):
        """update file database with changes"""
        filelist=File.objects.filter(collection=self.collection)
        if self.new_files:
            for path in self.new_files:
                if os.path.exists(path)==True: #check file exists
                    #now create new entry in File database
                    newfile=File(collection=self.collection)
                    updatefiledata(newfile,path,makehash=True)
                    newfile.indexedSuccess=False #NEEDS TO BE INDEXED IN SOLR
                    newfile.save()
                else:
                    log.error(('ERROR: ',path,' does not exist'))

        if self.moved_files:
            #print((len(self.moved_files),' to move'))
            for newpath,oldpath in self.moved_files:
                #print(newpath,oldpath)
    
                #get the old file and then update it
                file=filelist.get(filepath=oldpath)
                updatefiledata(file,newpath) #check all metadata;except contentsHash
                #if the file has been already indexed, flag to correct solr index meta
                if file.indexedSuccess:
                    file.indexUpdateMeta=True  #flag to correct solrindex
                    #print('update meta')
                file.save()
                
        if self.changed_files:
            log.debug('{} changed file(s) '.format(len(self.changed_files)))
            for filepath in self.changed_files:
                log.debug('Changed file: {}'.format(filepath))
                file=filelist.get(filepath=filepath)
                updatesuccess=updatefiledata(file,filepath)
    
                #check if contents have changed and solr index needs changing
                oldhash=file.hash_contents
                newhash=file_utils.get_contents_hash(filepath)
                if newhash!=oldhash:
                    #contents change, flag for index
                    file.indexedSuccess=False
                    file.hash_contents=newhash
    #                file.indexUpdateMeta=True  #flag to correct solrindex
                #NB the solrid field is not cleared = the index checks it exists and deletes the old doc
                #else-if the file has been already indexed, flag to correct solr index meta
                elif file.indexedSuccess==True:
                    file.indexUpdateMeta=True  #flag to correct solrindex
                #else no change in contents - no need to flag for index
                file.save()

    def count_changes(self):
        self.new_files_count=len(self.new_files)
        self.deleted_files_count=len(self.deleted_files)
        self.moved_files_count=len(self.moved_files)
        self.unchanged_files_count=len(self.unchanged_files)
        self.changed_files_count=len(self.changed_files)
        self.scanned_files=self.new_files_count+self.deleted_files_count+self.moved_files_count+self.unchanged_files_count+self.changed_files_count


def updatefiledata(file,path,makehash=False):
    """calculate all the metadata and update database; default don't make hash"""
    if True:
        file.filepath=path #
        file.hash_filename=file_utils.pathHash(path) #get the HASH OF PATH
        filename=os.path.basename(path)
        file.filename=filename
        shortName, fileExt = os.path.splitext(filename)
        file.fileext=fileExt    
        modTime = os.path.getmtime(path) #last modified time
        file.last_modified=solrJson.timestamp2aware(modTime)
        if os.path.isdir(path):
            file.is_folder=True
        else:
            file.is_folder=False
            if makehash:
                hash=file_utils.get_contents_hash(path) #GET THE HASH OF FULL CONTENTS
                file.hash_contents=hash
        file.filesize=os.path.getsize(path) #get file length
        file.save()
        return True
#    except Exception as e:
#        print(('Failed to update file database data for ',path))
#        print(('Error in updatefiledata(): ',str(e)))
#        raise ChangesError("Failed to update file database")


def countchanges(changes):
    return [len(changes['newfiles']),len(changes['deletedfiles']),len(changes['movedfiles']),len(changes['unchanged']),len(changes['changedfiles'])]


