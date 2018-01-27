# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

"""
from __future__ import unicode_literals
from .forms import SearchForm,TagForm
from documents.models import File,Collection,SolrCore,UserEdit
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.db.models.base import ObjectDoesNotExist
import solrJson, re, os, logging, unicodedata, urllib
from documents import solrcursor,updateSolr
from datetime import datetime
from usersettings import userconfig as config
import pages

log = logging.getLogger('ownsearch.views')
DOCBASEPATH=config['Models']['collectionbasepath']
RESULTS_PER_PAGE=10
#max size of preview text to return (to avoid loading up full text of huge document in browser)
try:
   CONTENTSMAX=int(config['Display']['maxcontents'])
except:
   CONTENTSMAX=10000


@login_required
def do_search(request,page_number=0,searchterm='',direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3=''):
#    log.debug('SESSION CACHE: '+str(vars(request.session)))
    page=pages.SearchPage(page_number=page_number,searchterm=searchterm,direction=direction,pagemax=pagemax,sorttype=sorttype,tag1field=tag1field,tag1=tag1,tag2field=tag2field,tag2=tag2,tag3field=tag3field,tag3=tag3)
#    print(request.session['META'].get('PATH_INFO'))
    log.debug('Request: {}'.format(request.META.get('PATH_INFO')))
    page.searchurl=request.META.get('PATH_INFO')
    request.session['lastsearch']=page.searchurl
    log.debug('Search parameters: {}'.format(page.__dict__))
    #GET PARAMETERS
    page.safe_searchterm()
    page.add_filters()    
    log.debug('Filters: {}, Tagfilters:{}'.format(page.filters,page.tagfilters))
    try:
    #GET AUTHORISED CORES AND DEFAULT
        corelist,DEFAULTCOREID,choice_list=authcores(request)
#        print(str(choice_list))
        log.debug('AUTHORISED CORE CHOICE: '+str(choice_list))
        log.debug('DEFAULT CORE ID:'+str(DEFAULTCOREID))

    #GET THE INDEX, a SolrCore object, or choose the default
        if 'mycore' not in request.session:  #set default if no core selected
            log.debug('no core selected.. setting default')
            request.session['mycore']=DEFAULTCOREID
        page.coreID=int(request.session.get('mycore'))
        #print(vars(request.session),'COREID:'+str(coreID),' CORELIST:'+str(corelist))
        if page.coreID in corelist:
            page.mycore=corelist[page.coreID]
        elif DEFAULTCOREID in corelist:
            page.mycore=corelist[DEFAULTCOREID]
            request.session['mycore']=DEFAULTCOREID
            page.coreID=DEFAULTCOREID
        else:
            log.warning('Cannot find any valid coreID in authorised corelist')
            return HttpResponse('Missing any config data for any authorised index: contact administrator')
    
    #SET THE RESULT PAGE    
        page.page_number=int(page.page_number) #urls always returns strings only
        log.info('Page: {}'.format(page.page_number))
    
    #DO SEARCH IF PAGE ESTABLISHED 
        
        if page.page_number > 0: #if page value not default (0) then proceed directly with search
            log.info('User {} searching with searchterm: {} and tag \"{}\" and tag2 \"{}\" on page {}'.format(request.user.username,page.searchterm,page.tag1,page.tag2,page.page_number))
            try:
                form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm)

                page.startnumber=(page.page_number-1)*RESULTS_PER_PAGE
                page.faceting=True
                """go search>>>>>>>>>>>>>>>>>>>>>>>>>>>>"""
                solrJson.pagesearch(page)
                page.nextpages(RESULTS_PER_PAGE)


            except Exception as e:
                log.error('Error {}'.format(e))
                page.clear_()

    #PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN REDIDRECT WITH A GET TO DO FIRST SEARCH
        # if this is a POST request we need to process the form data
        elif request.method == 'POST': #if data posted from form
            # create a form instance and populate it with data from the request:
            form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm,request.POST)
            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required
                page.searchterm=form.cleaned_data['search_term']
                page.sorttype=form.cleaned_data['SortType']
                coreselect=int(form.cleaned_data['CoreChoice'])
                if coreselect != page.coreID:  #NEW INDEX SELECTED
                    log.debug('change core')
                    page.coreID=coreselect  #new solr core ID
                    request.session['mycore']=page.coreID  #store the chosen index
        #            mycore=corelist[coreID]  #select new SolrCore object
                    log.debug('selected core'+str(coreselect))
#                request.session['results']='' #clear results from any previous searches
                
                page.searchterm_urlsafe=urllib.quote_plus(page.searchterm.encode('utf-8'))
                page.searchurl="/ownsearch/searchterm={}&page=1&sorttype={}".format(page.searchterm_urlsafe,page.sorttype)
#                request.session['lastsearch']=page.searchurl
                return HttpResponseRedirect(page.searchurl)
                
                    
        # START BLANK FORM if a GET (or any other method) we'll create a blank form; and clear last search
        else:
            form = SearchForm(choice_list,str(page.coreID),page.sorttype,page.searchterm)
            page.clear_()
            page.resultcount=-1
            request.session['lastsearch']=''

        #print(resultlist)
        page.searchterm_urlsafe=urllib.quote_plus(page.searchterm.encode('utf-8'))
        page.filterlist=[(tag,page.filters[tag]) for tag in page.filters]
        log.debug('Filter list : {}'.format(page.filterlist))
        #log.debug('All page data: {}'.format(searchpage.__dict__))
        return render(request, 'searchform.html', {'form': form, 'page':page})

    except solrJson.SolrCoreNotFound as e:
        log.error('Index not found on solr server')
        return HttpResponse('Index not found on solr server : check configuration')
    except solrJson.SolrConnectionError as e:
        log.error(e)
        return HttpResponse('No response from solr server : check network connection, solr status')

@login_required
def download(request,doc_id,hashfilename): #download a document from the docstore
    log.debug('Download of doc_id:'+doc_id+' hashfilename:'+hashfilename)
    #MAKE CHECKS BEFORE DOWNLOAD
    #check file exists in database and hash matches
    try:
        thisfile=File.objects.get(id=doc_id)
        log.info('User: '+request.user.username+' attempting to download file: '+thisfile.filename)
        assert thisfile.hash_filename==hashfilename
    except AssertionError:
        log.warning('Download failed because of hash mismatch')
        return HttpResponse('File not stored on server')
    except ObjectDoesNotExist:
        log.warning('Download failed as file ID not found in database')
        return HttpResponse('File not stored on server')
    #check user authorised to download
    if authid(request,thisfile) is False:
        log.warning(thisfile.filename+' not authorised or not present')
        return HttpResponse('File NOT authorised for download')    

    file_path = thisfile.filepath
    if os.path.exists(file_path):
        cleanfilename=slugify(os.path.basename(file_path))
        with open(file_path, 'rb') as thisfile:
            response=HttpResponse(thisfile.read(), content_type='application/force-download')
            response['Content-Disposition'] = 'inline; filename=' + cleanfilename
            log.info('DOWNLOAD User: '+str(request.user)+' Filepath: '+file_path)
            return response
        raise Http404
    else:
        return HttpResponse('File not stored on server')


@login_required
def get_content(request,doc_id,searchterm,tagedit='False'): 
    """make a page showing the extracted text, highlighting searchterm """
    
    log.debug('Get content for doc id: {} from search term {}'.format(doc_id,searchterm))
    
    page=pages.ContentPage(doc_id=doc_id,searchterm=searchterm,tagedit='False')
    page.safe_searchterm()
    page.searchurl=request.session.get('lastsearch','/ownsearch') #store the return page
    #load solr index in use, SolrCore object
    #GET INDEX
    #only show content if index defined in session:
    if request.session.get('mycore') is None:
        log.info('Get content request refused; no index defined in session')
        return HttpResponseRedirect('/') 
    page.coreID=int(request.session.get('mycore'))
    corelist,DEFAULTCOREID,choice_list=authcores(request)
    page.mycore=corelist[page.coreID]

    #HANDLE EDITS OF USER TAGS
    useredit_str=request.session.get('useredit','')
    log.debug('useredit: {}'.format(useredit_str))
    if useredit_str=='True':
        page.useredit=True	
    else:
        page.useredit= False
    if request.method == 'POST': #if data posted from form
        # create a form instance and populate it with data from the request:
        form = TagForm('',request.POST)
            # check whether it's valid:
        if request.POST.get('edit','')=='Edit':
            log.debug('Editing user tags')
            request.session['useredit']='True'
            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(page.doc_id,page.searchterm))
        elif request.POST.get('save','')=='Save':
            log.debug('Save user tags')
            request.session['useredit']=''
            if form.is_valid():
                # process the data in form.cleaned_data as required
                keywords=form.cleaned_data['keywords']
                """Permit only Latin alphanumeric and numbers as user tags""" 
                keyclean=[re.sub(r'[^a-zA-Z0-9, ]','',item) for item in keywords]
                updateresult=updateSolr.updatetags(page.doc_id,page.mycore,keyclean)
                if updateresult:
                    log.info('Update success of user tags: {} in solrdoc: {} by user {}'.format(keyclean,page.doc_id,request.user.username))
                    edit=UserEdit(solrid=page.doc_id,usertags=keyclean,corename=page.mycore.name)
                    edit.username=request.user.username
                    edit.time_modified=solrJson.timeaware(datetime.now())
                    edit.save()
                else:
                    log.debug('Update failed of user tags: {} in solrdoc: {}'.format(keyclean,page.doc_id))
            return HttpResponseRedirect("/ownsearch/doc={}&searchterm={}".format(page.doc_id,page.searchterm))
    else:

        #get a document content - up to max size characters
        page.results=solrJson.gettrimcontents(page.doc_id,page.mycore,CONTENTSMAX).results  #returns SolrResult object
        try:
            result=page.results[0]
            #log.debug(vars(result))
        except KeyError:
            return HttpResponse('Can\'t find document with ID '+page.doc_id+' COREID: '+page.coreID)
        
        page.process_result(result)
        log.debug('Data ID: {}'.format(page.data_ID)) 
        
        #Make a user tag form    
        form = page.tagform()
#            log.debug('tag1: {}'.format(tags1))

        #Use preview template if preview HTML stored
        if page.html:
            page.searchterm_urlsafe=urllib.quote_plus(page.searchterm)
            return render(request, 'blogpost.html', {'form':form, 'page':page})
            	
        #DIVERT ON BIG FILE

        log.debug('Highlight length: '+str(len(page.highlight)))
        #detect if large file (contents greater or equal to max size)
        if len(page.highlight)==CONTENTSMAX:
           #go get large highlights instead
           return get_bigcontent(request,page)
#        #check if file is registered and authorised to download
        page.authflag,page.matchfile_id,page.hashfilename=authfile(request,page.hashcontents,page.docname)

        #clean up and prepare the preview text for display
        page.splittext,page.last_snippet,page.cleanterm=cleanup(page.searchterm,page.highlight)
        
        #log.debug('Page contents : {}'.format(page.result.__dict__))
        return render(request, 'content_small.html', {'form':form,'page':page})


@login_required
def get_bigcontent(request,page): #make a page of highlights, for MEGA files
#        
    log.debug('GET BIGCONTENT')
    res=solrJson.bighighlights(page.doc_id,page.mycore,page.searchterm,CONTENTSMAX)
    if len(res.results)>0:
        #Get meta
        page.process_result(res.results[0]) #if duplicate, take the first
#        log.debug(result.data)
        #check if file is registered and authorised to download
        page.authflag,page.matchfile_id,page.hashfilename=authfile(request,page.hashcontents,page.docname)
        
        form = page.tagform()
        return render(request, 'content_big.html', {'form':form,'page':page})
#docsize':docsize, 'doc_id': doc_id, 'highlights': highlights, 'hashfile':hashfilename, 'fileid':matchfile_id,'searchterm': searchterm,'docname':docname, 'docpath':docpath, 'docexists':authflag})
    else:
        return HttpResponse('No document with ID '+doc_id+' COREID: '+coreID)


def cleansterm(searchterm):
    #    log.debug(searchterm)
    # take term in double quotes as search term
    try:
        cleanterm=re.search('\"(.+)\"',searchterm).group(0)[1:][:-1]
    except AttributeError as e:
        cleanterm=searchterm
    except Exception as e:
        log.debug(str(e))
        cleanterm=searchterm
    return cleanterm

def cleanup(searchterm,highlight):
    # CLEANUP TEXT
#    log.debug(repr(highlight[:400]))
    highlight=re.sub('\n \xc2\xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
    highlight=re.sub('\n \xa0 \n','\n',highlight) #clean up extraneous non breaking spaces 
#    print('SPACECLEANE'+repr(highlight[:400]))
    cleaned=re.sub('(\n[\s]+\n)+', '\n', highlight) #cleaning up chunks of white space
#    print('STRINGCLEANED'+repr(cleaned[:400]))
        
    cleansearchterm=cleansterm(searchterm)
    log.debug(cleansearchterm)
    lastscrap=''
    try:
        splittext=re.split(cleansearchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
        if len(splittext) > 1:
            lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
    except:
        splittext=[cleaned]
    return splittext,lastscrap,cleansearchterm
    

@login_required
def testsearch(request,doc_id,searchterm):
	    #load solr index in use, SolrCore object
    corestring=request.session.get('mycore')
    if corestring:
        coreID=int(corestring)
    else:
        coreID=''
    if coreID:
        mycore=cores[coreID]
        results=solrJson.testresponse(doc_id,mycore,searchterm)
        print results
        if len(results)>0:
            if 'highlight' in results[0].data:
                highlight=results[0].data['highlight']
                return HttpResponse(highlight)
        return HttpResponse(results)
    else:
        return HttpResponseRedirect('/')        
        

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    shortName, fileExt = os.path.splitext(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    return value+fileExt

##set up solr indexes
@login_required
def authcores(request):
    cores={}
    choice_list=()
    thisuser=request.user
    groupids=[group.id for group in thisuser.groups.all()]
    log.debug('authorised groups for user: '+str(groupids))
    corelist=(SolrCore.objects.filter(usergroup_id__in=groupids))
    log.debug('authorised core list '+str(corelist))
    for core in corelist:
        cores[core.id]=solrJson.SolrCore(core.corename)
        corenumber=str(core.id)
        coredisplayname=core.coreDisplayName
        choice_list +=((corenumber,coredisplayname),) #value/label
    try:
        DEFAULTCOREID=int(config['Solr']['defaultcoreid'])
        #print(defaultcoreID,cores)
        assert DEFAULTCOREID in cores     
    except Exception as e:
        log.debug('Default core ('+str(DEFAULTCOREID)+') set in userconfigs is not found in authorised indexes: first available is made default')
        try:
            log.debug(str(cores)+' '+str(choice_list))
            DEFAULTCOREID=int(choice_list[0][0])#if no default found, take first in list as new default
#            defaultcoreID=cores.keys()[0]  #take any old core, if default not found
        except Exception as e:
            log.error('No valid and authorised index set in database: fix in /admin interface')
            log.error(str(e))
            cores={}
            DEFAULTCOREID=0
    return cores, DEFAULTCOREID, choice_list

#CHECK IF FILE WITH SAME HASH EXISTS IN DATABASE, AUTHORISED FOR DOWNLOAD AND IS PRESENT ON  MEDIA
def authfile(request,hashcontents,docname,acceptothernames=True):
    matchfiles=File.objects.filter(hash_contents=hashcontents) #find local registered files by hashcontents
    if matchfiles:
        log.debug('hashcontents: '+hashcontents)    
    #get authorised cores
        #user groups that user belongs to
        authgroupids=[group.id for group in request.user.groups.all()]
        log.debug('authorised groups for user: '+str(authgroupids))
        #indexes that user is authorised for
        authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
        log.debug(str(authcoreids)+'.. cores authorised for user')
        
    #find authorised file
        altlist=[]
        for f in matchfiles:
            fcore=Collection.objects.get(id=f.collection_id).core_id  #get core of database file
            if fcore in authcoreids and os.path.exists(f.filepath) and docname==f.filename:
                #FILE AUTHORISED AND EXISTS LOCALLY
                log.debug('matched authorised file'+f.filepath)
                return True,f.id,f.hash_filename
            
            #finding authorised file that match hash and exist locally but have different filename
            elif fcore in authcoreids and os.path.exists(f.filepath):
                altlist.append(f)
         #if no filenames match, return a hashmatch
        if acceptothernames and altlist:
            log.debug('hashmatches with other filenames'+str(altlist))
            #return any of them
            log.debug('returning alternative filename match'+altlist[0].filepath)
            return True,altlist[0].id,altlist[0].hash_filename

    return False,'',''
        
def authid(request,doc):
    coreid=Collection.objects.get(id=doc.collection_id).core_id
    #print(coreid)
    #user groups that user belongs to
    authgroupids=[group.id for group in request.user.groups.all()]
    #print(authgroupids)
    #indexes that user is authorised for
    authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
    #print(authcoreids)
    if coreid in authcoreids:
        return True
    else:
        return False

