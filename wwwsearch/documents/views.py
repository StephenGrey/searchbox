# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from django.http import HttpResponse
from .forms import IndexForm
from django.shortcuts import render, redirect
from django.utils import timezone
import pytz #support localising the timezone
from models import Collection,File
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import FileSpecTable as filetable
import datetime, hashlib, os, logging, requests
import indexSolr, updateSolr, solrICIJ, solrDeDup, solrcursor
import ownsearch.solrSoup as solr
from django.contrib.admin.views.decorators import staff_member_required
log = logging.getLogger('ownsearch.docs.views')
from usersettings import userconfig as config


@staff_member_required()
def index(request):
    #get the core , or set the the default
    cores,defaultcoreID=getindexes()
    if 'mycore' not in request.session:  #set default if no core selected
        if defaultcoreID: #if a default defined, then set as chosen core
            request.session['mycore']=defaultcoreID
    coreID=request.session.get('mycore')
    if request.method=='POST': #if data posted # switch core
#        print('post data')
        form=IndexForm(request.POST)
        if form.is_valid():
            coreID=form.cleaned_data['CoreChoice']
#            print ('change core to',coreID)
            request.session['mycore']=coreID
    else:
#        print(request.session['mycore'])
        form=IndexForm(initial={'CoreChoice':coreID})
#        print('Core set in request: ',request.session['mycore'])
    latest_collection_list = Collection.objects.filter(core=coreID)
    return render(request, 'documents/scancollection.html',{'form': form, 'latest_collection_list': latest_collection_list})

def listfiles(request):
#   print('Core set in request: ',request.session['mycore'])
#    cores=solr.getcores() #fetch dictionary of installed solr indexes (cores)
    cores,defaultcoreID=getindexes()
    if 'mycore' in request.session:
        coreID=request.session['mycore'] #currently selected core
    else:
        print ('ERROR no stored core in session')
        return HttpResponse( "No index selected...please go back")
#        coreID=defaultcore
    mycore=cores[str(coreID)] # get the working core
    log.info('using index: '+ str(mycore.name))
    try:
        if request.method == 'POST' and 'list' in request.POST and 'choice' in request.POST:
            #get the files in selected collection
            if True:
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                collectionpath=thiscollection.path
                filelist=File.objects.filter(collection=thiscollection)
                #print(filelist)
                return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })
#            except:
#                return HttpResponse( "Error...please go back")
    #SCAN DOCUMENTS IN A COLLECTION on disk hash contents and meta and update after changes.
        elif request.method == 'POST' and 'scan' in request.POST and 'choice' in request.POST:
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            #>> DO THE SCAN ON THIS COLLECTION
            if True:
                mycore.ping()
                scanfiles=updateSolr.scandocs(thiscollection)
                newfiles,deletedfiles,movedfiles,unchangedfiles,changedfiles=scanfiles
                if sum(scanfiles)>0:
                    return HttpResponse (" <p>Scanned "+str(sum(scanfiles))+" docs<p>New: "+str(newfiles)+"<p>Deleted: "+str(deletedfiles)+"<p> Moved: "+str(movedfiles)+"<p>Changed: "+str(changedfiles)+"<p>Unchanged: "+str(unchangedfiles))
                else:
                    return HttpResponse (" Scan Failed!")
    #INDEX DOCUMENTS IN COLLECTION IN SOLR
        elif request.method == 'POST' and 'index' in request.POST and 'choice' in request.POST:
            if True:
                #print('try to index in Solr')
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                icount,iskipped,ifailed=indexdocs(thiscollection,mycore) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing.. <p>indexed: "+str(icount)+"<p>skipped:"+str(iskipped)+"<p>failed:"+str(ifailed))

    #INDEX VIA ISIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR
        elif request.method == 'POST' and 'indexICIJ' in request.POST and 'choice' in request.POST:
            if True:
                #print('try to index in Solr')
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                icount,iskipped,ifailed=indexdocs(thiscollection,mycore,forceretry=True,useICIJ=True) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing w ICIJ tool .. <p>indexed: "+str(icount)+"<p>skipped:"+str(iskipped)+"<p>failed:"+str(ifailed))
    
    #CURSOR SEARCH OF SOLR INDEX
        elif request.method == 'POST' and 'solrcursor' in request.POST and 'choice' in request.POST:
            #print('try cursor scan of Solr Index')
            if True:
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
            #print (thiscollection,mycore)
                match,skipped,failed=indexcheck(thiscollection,mycore) #GO SCAN THE SOLR INDEX
                return HttpResponse ("Checking solr index.. <p>files indexed: "+str(match)+"<p>files not found:"+str(skipped)+"<p>errors:"+str(failed))
    #REMOVE DUPLICATES FROM SOLR INDEX
        elif request.method == 'POST' and 'dupscan' in request.POST:
            print('try scanning for duplicates')
            if True:
                mycore.ping()
            #print (thiscollection,mycore)
                dupcount,deletecount=solrDeDup.filepathdups(mycore,delete=True) #GO REMOVE DUPLICATES
                return HttpResponse ("Checking solr index for duplicate paths/filenames in solr index \""+str(mycore)+"\"<p>duplicates found: "+str(dupcount)+"<p>files removed: "+str(deletecount))
        else:
            return redirect('index')
    except solr.SolrConnectionError:
        return HttpResponse("No connection to Solr index: (re)start Solr server")
    except solr.SolrCoreNotFound:
        return HttpResponse("Solr index not found: check index name in /admin")
    except indexSolr.ExtractInterruption as e:
        return HttpResponse ("Indexing w ICIJ tool interrupted -- Solr Server not available. \n"+e.message)
    except requests.exceptions.RequestException as e:
        print ('caught requests connection error')
        return HttpResponse ("Indexing interrupted -- Solr Server not available")


#checking for what files in existing solrindex
def indexcheck(collection,thiscore):

    #get the basefilepath
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore

    #first get solrindex ids and key fields
    try:#make a dictionary of filepaths from solr index
        indexpaths=solrcursor.cursor(thiscore)
    except Exception as e:
        print('Failed to retrieve solr index')
        print (str(e))
        return 0,0,0

    #now compare file list with solrindex
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)

        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)

	#INDEX CHECK: METHOD ONE : IF RELATIVE PATHS STORED MATCH
            if relpath in indexpaths:  #if the path in database in the solr index
                solrdata=indexpaths[relpath][0] #take the first of list of docs with this path
                #print ('PATH :'+file.filepath+' found in Solr index', 'Solr \'id\': '+solrdata['id'])
                file.indexedSuccess=True
                file.solrid=solrdata['id']
                file.save()
                counter+=1
        #INDEX CHECK: METHOD TWO: CHECK IF FILE STORED IN SOLR INDEX UNDER CONTENTS HASH                
            else:
                #print('trying hash method')
                #is there a stored hash, if not get one
                if not hash:
                    hash=hexfile(file.filepath)
                    file.hash_contents=hash
                    file.save()
                #now lookup hash in solr index
                solrresult=solr.hashlookup(hash,thiscore)
                #print(solrresult)
                if len(solrresult)>0:
                    #if some files, take the first one
                    solrdata=solrresult[0]
                    #print('solrdata:',solrdata)
                    file.indexedSuccess=True
                    file.solrid=solrdata['id']
                    file.save()
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully (HASHMATCH)', 'Solr \'id\': '+solrdata['id'])
                #NO MATCHES< RETURN FAILURE
                else:
                    log.info(str(file.filepath)+'.. not found in Solr index')
                    file.indexedSuccess=False
                    file.solrid='' #wipe any stored solr id; DEBUG: this wipes also oldsolr ids scheduled for delete
                    file.save()
                    skipped+=1
        return counter,skipped,failed

#MAIN METHOD FOR EXTRACTING DATA
def indexdocs(collection,mycore,forceretry=False,useICIJ=False): #index into Solr documents not already indexed
    #need to check if mycore and collection are valid objects
    if isinstance(mycore,solr.SolrCore) == False or isinstance(collection,Collection) == False:
        log.warning('indexdocs() parameters invalid')
        return 0,0,0
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)
        #main loop
        for file in filelist:
            if file.indexedSuccess:
                #skip this file, it's already indexed
                #print('Already indexed')
                skipped+=1
            elif file.indexedTry==True and forceretry==False:
                #skip this file, tried before and not forceing retry
                #print('Previous failed index attempt, not forcing retry:',file.filepath)
                skipped+=1
            elif indexSolr.ignorefile(file.filepath) is True:
                #skip this file because it is on ignore list
                log.info('Ignoring: '+str(file.filepath))
                skipped+=1
            else: #do try to index this file
                log.info('Attempting index of '+str(file.filepath))
                #print('trying ...',file.filepath)
                #if was previously indexed, store old solr ID and then delete if new index successful
                oldsolrid=file.solrid
                #getfile hash if not already done
                if not file.hash_contents:
                    file.hash_contents=hexfile(file.filepath)
                    file.save()
                #now try the extract
                if useICIJ:
                    print('using ICIJ extract method..')
                    result = solrICIJ.ICIJextract(file.filepath,file.hash_contents,mycore)
                else:
                    try:
                        result=indexSolr.extract(file.filepath,file.hash_contents,mycore)
                    except solr.SolrCoreNotFound as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')
                    except solr.SolrConnectionError as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')
                    except requests.exceptions.RequestException as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')               
         
                if result is True:
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully')
                    if not useICIJ:
                        file.solrid=file.hash_filename  #extract uses hashfilename for an id , so add it
                    else:
                        file.solrid=''
                    #DEBUG: above won't work for ICIJ method as does NOT use hasfilename as id
                    file.indexedSuccess=True
                    #now delete previous solr doc (if any): THIS IS ONLY NECESSARY IF ID CHANGES  
                    print ('Old ID: '+oldsolrid,'New ID: '+file.solrid)
                    if oldsolrid and oldsolrid!=file.solrid:
                        print('now delete old solr doc',oldsolrid)
                        #DEBUG: NOT TESTED YET
                        response,status=updateSolr.delete(oldsolrid,mycore)
                        if status:
                            print('Deleted solr doc with ID:'+oldsolrid)
                    file.save()
                else:
                    log.info('PATH : '+str(file.filepath)+' indexing failed')
                    failed+=1
                    file.indexedTry=True  #set flag to say we've tried
                    file.save()
        return counter,skipped,failed
    
def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
    return m.hexdigest()

#set up solr indexes
def getindexes():
    cores=solr.getcores()
    defaultcoreID=config['Solr']['defaultcoreid']
    log.debug('CORES: '+str(cores)+' DEFAULT CORE ID:'+str(defaultcoreID))
    if defaultcoreID not in cores:
        try:
            defaultcoreID=cores.keys()[0]  #take any old core, if default not found
        except Exception as e:
            log.warning('No indexes defined in database')
            defaultcoreID='' #if no indexes, no valid default
    return cores,defaultcoreID