# -*- coding: utf-8 -*-
import os, logging,hashlib,re,datetime,unicodedata
from pathlib import Path
from collections import defaultdict

try:
    from django.http import HttpResponse
except:
    #usable outside Django
    pass
    
try:
    from django.template import loader
    from documents.models import File
    from usersettings import userconfig as config
    BASEDIR=config['Models']['collectionbasepath'] #get base path of the docstore
    log = logging.getLogger('ownsearch.docs.file_utils')    
except:
    #make usable outside the project
    BASEDIR=''
    pass


class DoesNotExist(Exception):
    pass

class Not_A_Directory(Exception):
    pass

class FileSpecs:
    def __init__(self,path,folder=False):
        self.path=path
        self.name=os.path.basename(path)
        self.shortname, self.ext = os.path.splitext(self.name)
        if folder:
            if not os.path.isdir(self.path):
                raise Not_A_Directory
        self.folder=os.path.isdir(self.path)
                
        
    @property
    def length(self):
        if self.exists:
            return os.path.getsize(self.path) #get file length
        else:
            raise DoesNotExist

    @property
    def last_modified(self):
        if self.exists:
            return os.path.getmtime(self.path) #last modified time
        else:
            raise DoesNotExist

    @property
    def date_from_path(self):
        """find a date in US format in filename"""
        m=re.match('.*(\d{4})[-_](\d{2})[-_](\d{2})',self.name)
        try:
            if m:
                year=int(m[1])
                if year<2019 and year>1900:
                    month=int(m[2])
                    day=int(m[3])
                    date=datetime.datetime(year=year,month=month,day=day)
                    return date
        except Exception as e:
            pass
        m=re.match('.*(\d{2})[-_](\d{2})[-_](\d{2})',self.name)
        try:
            if m:
                year=int(m[1])
                print(year)
                if year>50:
                    year+=50
                else:
                    year+=2000
                if year<2050 and year>1950:
                    month=int(m[2])
                    day=int(m[3])
                    date=datetime.datetime(year=year,month=month,day=day)
                    return date
        except Exception as e:
            pass
        return None
    
    @property
    def pathhash(self):
        path=Path(self.path).as_posix()  #convert windows paths to unix paths for consistency across platforms
        m=hashlib.md5()
        m.update(path.encode('utf-8')) #encoding avoids unicode error for unicode paths
        return m.hexdigest()
        
    @property
    def contents_hash(self):
        return get_contents_hash(self.path)

    @property
    def exists(self):
        return os.path.exists(self.path)
        
    def __repr__(self):
        return "File: {}".format(self.path)


def filespecs(parent_folder): #  
    """return filespecs dict keyed to path"""
    filespecs={}
    for dirName, subdirs, fileList in os.walk(parent_folder): #go through every subfolder in a folder
        for filename in fileList: #now through every file in the folder/subfolder
            path = os.path.join(dirName, filename)
            filespecs[path]=FileSpecs(path)
        for folder in subdirs:
            path= os.path.join(dirName,folder)
            filespecs[path]=FileSpecs(path,folder=True)
    return filespecs


#DOWNLOADS / SERVE FILE

def make_download(file_path):
    return make_file(file_path,'application/force-download')
    
def make_file(file_path,content_type):    
    if not os.path.exists(file_path):
        raise DoesNotExist
    cleanfilename=slugify(os.path.basename(file_path))
    with open(file_path, 'rb') as thisfile:
            #response=HttpResponse(thisfile.read(), )
            response=HttpResponse(thisfile.read(), content_type=content_type)
            response['Content-Disposition'] = 'inline; filename=' + cleanfilename
    return response


#HASH FILE FUNCTIONS

def parent_hashes(filepaths):
    "list of hashes of parent paths of files"""
    if isinstance(filepaths, list):
        pathhashes=[]
        for path in filepaths:
            pathhashes.append(parent_hash(path))
        return pathhashes
    else:
        return [parent_hash(filepaths)]

def parent_hash(filepath):
    """hash of a file's parent directory"""
    parent,filename=os.path.split(filepath)
    return pathHash(parent)
        
def pathHash(path):
    path=Path(path).as_posix()  #convert windows paths to unix paths for consistency across platforms
    m=hashlib.md5()
    m.update(path.encode('utf-8')) #encoding avoids unicode error for unicode paths
    return m.hexdigest()

def get_contents_hash(path,blocksize = 65536):
    afile = open(path, 'rb')
    hasher = hashlib.sha256()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return hasher.hexdigest()


#PATH METHODS
def is_down(relpath, root=BASEDIR):
    path=os.path.abspath(os.path.join(root,relpath))
    return path.startswith(root)

def is_absolute(path,root=BASEDIR):
    return path.startswith(root)
    
def relpath_exists(relpath,root=BASEDIR):
    if root:
        return os.path.exists(os.path.join(root,relpath))
    else:
        return False

def relpath_valid(relpath,root=BASEDIR):
    """check relative path exists, is a sub of the docstore, and is not an absolute path"""
    return relpath_exists(relpath,root=root) and not is_absolute(relpath,root=root) and is_down(relpath,root=root)
    
def index_maker(path,index_collections):
    def _index(root,depth,index_collections,maxdepth=2):
        #print (f'Root :{root} Depth: {depth}')
        if True:
            files = os.listdir(root)
            for mfile in files:
                t = os.path.join(root, mfile)
                relpath=os.path.relpath(t,BASEDIR)
                #print(f'FILE/DIR: {t}')
                if os.path.isdir(t):    
                    if depth==maxdepth-1:
                        yield loader.render_to_string('documents/filedisplay/p_folder_nosub.html',
                                                   {'file': mfile,
                                                   	'filepath':relpath,
                                                   	'rootpath':path,
                                                    	})
                    else:
                        subfiles=_index(os.path.join(root, t),depth+1,index_collections)
                        #print(f'ROOT:{root},SUBFILES:{subfiles}')
                        yield loader.render_to_string('documents/filedisplay/p_folder.html',
                                                   {'file': mfile,
                                                   	'filepath':relpath,
                                                   	'rootpath':path,
                                                    'subfiles': subfiles,
                                                    	})
                    continue
                else:
                    stored,indexed=model_index(t,index_collections)
                    #log.debug('Local check: {},indexed: {}, stored: {}'.format(t,indexed,stored))
                    yield loader.render_to_string('documents/filedisplay/p_file.html',{'file': mfile, 'local_index':stored,'indexed':indexed})
                    continue
        else:
            print('look no further')
    basepath=os.path.join(BASEDIR,path)
    log.debug('Basepath: {}'.format(basepath))
    if os.path.isdir(basepath):
        return _index(basepath,0,index_collections)
    else:
        return "Invalid directory"

def directory_tags(path,isfile=False):
    """make subfolder tags from full filepath"""
    #returns fullrelativepath,folder,basename,hash_relpath
    log.debug('Path: {}'.format(path))
    a,b=os.path.split(path)
    if isfile:
        tags=[]
    else:
        a_hash=pathHash(path)
        tags=[(path,a,b,a_hash)]
    path=a
    while True:
        a,b=os.path.split(path)

        if b=='/' or b=='' or b=='\\':
            #print('break')
            
            break
        a_hash=pathHash(path)
        tags.append((path,a,b,a_hash))
        path=a
        
    tags=tags[::-1]
    log.debug(f'Tags: {tags}')
    return tags

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value, fileExt = os.path.splitext(value)
    originalvalue=value
    try:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')        
        value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
        value = unicode(re.sub('[-\s]+', '-', value))
    except NameError: #python3
    #except IndexError:
        value = unicodedata.normalize('NFKD', originalvalue).encode('ascii', 'ignore').decode()
        value = re.sub('[^\w\s-]', '', value).strip().lower()
        value = re.sub('[-\s]+', '-', value) if value else 'filename'
        #value=value.encode('ascii','ignore')      
    return value+fileExt





#FILE MODEL METHODS

def model_index(path,index_collections,hashcheck=False):
    """check if True/False file in collection is in database, return File object"""
    
    stored=File.objects.filter(filepath=path, collection__in=index_collections)
    if stored:
        indexed=stored.exclude(solrid='')
        return True,indexed
    else:
        return None,None


