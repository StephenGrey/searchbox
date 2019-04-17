# -*- coding: utf-8 -*-
"""DUPLICATES AND ORPHANS FINDER AND MEDIA SCANNER"""
from __future__ import unicode_literals
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from . import pages
from documents import file_utils, documentpage as pages, sql_connect as sql
from dups import forms
import os, configs, logging,json,threading
log = logging.getLogger('ownsearch.dups.views')
from watcher import watch_dispatch

dupsconfig=configs.config.get('Dups')
DEFAULT_MASTERINDEX_PATH=dupsconfig.get('masterindex_path') if dupsconfig else None
MEDIAROOT=dupsconfig.get('rootpath') if dupsconfig else None

#log.debug(MEDIAROOT)
#log.debug(DEFAULT_MASTERINDEX_PATH)

@staff_member_required()
def index(request,path='',duplist=False,orphans=False):
    """display files in a directory"""
    warning=""
    log.debug(f'Thread: {threading.get_ident()}')
    log.debug(f'path: {path}')
    log.debug(f'Mediaroot: {MEDIAROOT}')
    job_id=request.session.get('dup_tasks')
    
    path_info=request.META.get('PATH_INFO')
    request.session['lastpage']=path_info
    #log.debug(request.session.get('lastpage'))
    
    
    path=os.path.normpath(path) if path else '' #cope with windows filepaths
    
    log.debug(f'Dups only: {duplist}')
    
    page=pages.FilesPage(request=request,default_master=DEFAULT_MASTERINDEX_PATH)
        
    if not MEDIAROOT or not page.masterindex_path:
    	    return HttpResponse ("Missing 'Dups' configuration information in user.settings : set the 'rootpath' and 'masterindex_path' variables")
    
    if request.method == 'POST':
       log.info(request.POST)
       checklist=request.POST.getlist('checkbox')
       if 'scan' in request.POST:
           
           page.local_scanpath=request.POST.get('local-path')
           page.local_scanpath=os.path.normpath(page.local_scanpath) if page.local_scanpath else ''
           log.debug('scanning scanfolder {page.local_scanpath}')
           if not os.path.exists(os.path.join(MEDIAROOT,page.local_scanpath)):
               log.error('scan request sent non-existent path')
               return redirect('dups_index',path=path)
           fullpath=os.path.join(MEDIAROOT,page.local_scanpath)
           fullpath=os.path.normpath(fullpath) if fullpath else ''
           job_id=watch_dispatch.make_dupscan_job(fullpath,'local',_test=0)
           request.session['dup_tasks']=job_id
           request.session['scanfolder']=page.local_scanpath
           return redirect('dups_index',path=path)

       elif 'masterscan' in request.POST:
           full_masterpath=os.path.join(MEDIAROOT,page.masterindex_path)
           full_masterpath=os.path.normpath(full_masterpath) if full_masterpath else ''
           log.debug(f'scanning master: {full_masterpath}')
           job_id=watch_dispatch.make_dupscan_job(full_masterpath,'master',_test=0)
           request.session['dup_tasks']=job_id
           request.session['masterfolder']=page.masterindex_path
           log.debug(f'redirecting back to dups in {path}')
           return redirect('dups_index',path=path)           

    page.get_stored(MEDIAROOT)
     
    if request.method == 'POST':
        if request.POST.get('delete-button')=='Delete':
            log.debug(f'Deleting: {checklist}')
            for relfile in checklist:
                f=os.path.join(MEDIAROOT,relfile)
                result=file_utils.delete_file(f)
                log.info(f'Deleted: {f} Result: {result}')
                if result:
                    page.remove_file(f)

        elif request.POST.get('action')=='move':
            reldest=request.POST.get('destination')
            destination=os.path.join(MEDIAROOT,reldest)
            try:
                assert os.path.exists(destination)
                request.session['destination']=reldest
                
                for f in checklist:
                    source=os.path.join(MEDIAROOT,f)
                    filename=os.path.basename(source)
                    filedest=os.path.join(destination,filename)
                    log.debug(f'Moving ... {source} to {filedest}')
                    result=file_utils.move_file(source,filedest)
                    log.info(f'Moved.. \'{source}\' to \'{filedest}\' result:{result}')
                    if result:
                        page.move_file(source,filedest)
            except AssertionError:
                pass
                       
       

    #page.masterform=forms.MasterForm()
    
    
    
    if os.path.exists(os.path.join(MEDIAROOT,path)):
        #page.masterpath=masterindex_path
        if path:
            rootpath=path
            tags=file_utils.directory_tags(path)
        else:
            rootpath=""
            tags=None
        
        
        
        if page.masterindex_path:
            page.inside_master=file_utils.new_is_inside(path,page.masterindex_path)
        page.inside_scan_folder=file_utils.new_is_inside(path,page.local_scanpath) if page.local_scanpath else None
        
        if duplist:
            #display only duplicates
            warning="""
            
            (Only first 500 duplicate files shown)"""
            if page.masterspecs and page.inside_master:
                c=file_utils.check_master_dups_html(os.path.join(MEDIAROOT,path),scan_index=page.specs,master_index=page.masterspecs,rootpath=MEDIAROOT)
                log.debug(f'Scanned \'{path}\' for duplicates')
            elif page.specs and page.inside_scan_folder:
                combodups=sql.ComboIndex(page.masterspecs,page.specs,folder=os.path.join(MEDIAROOT,path))
                c=file_utils.check_local_dups_html(os.path.join(MEDIAROOT,path),scan_index=page.specs,master_index=page.masterspecs,combo=combodups,rootpath=MEDIAROOT)
                log.debug(f'Scanned \'{path}\' for duplicates')
            else:
                c=None                
                warning="Navigate to a scanned folder to see duplicates"
                       
        elif orphans:
            #display only orphans
            warning="""
            
            (Only first 500 orphan files shown)"""
            if page.masterspecs and page.inside_master:
                c=None
                warning="Navigate to scan folder to see orphans from master"
#                c=file_utils.check_master_dups_html(os.path.join(MEDIAROOT,path),scan_index=page.specs,master_index=page.masterspecs,rootpath=MEDIAROOT)
#                log.debug(f'Scanned \'{path}\' for orphans')
            elif page.specs and page.inside_scan_folder:
                combodups=sql.ComboIndex(page.masterspecs,page.specs,folder=os.path.join(MEDIAROOT,path))
                c=file_utils.check_local_dups_html(os.path.join(MEDIAROOT,path),scan_index=page.specs,master_index=page.masterspecs,combo=combodups,rootpath=MEDIAROOT,orphans=True)
                log.debug(f'Scanned \'{path}\' for orphans')
            else:
                c=None                
                warning="Navigate to a scan folder to see orphans"

            
            
            
        
        else:
            try:
                c = file_utils.Dups_Index_Maker(path,'',specs=page.specs,masterindex=page.masterspecs,rootpath=MEDIAROOT)._index
            except file_utils.EmptyDirectory as e:
                c= None
        if job_id:
            page.job=f'SB_TASK.{job_id}'
            log.debug(f'job: {page.job}')
            page.results=watch_dispatch.get_extract_results(page.job)
            log.debug(page.results)
            
        return render(request,'dups/listindex.html',
                                   {'page': page, 'subfiles': c, 'rootpath':rootpath, 'tags':tags,  'path':path,'warning':warning})
    else:
        return redirect('dups_index',path='')

@login_required
def dups_api(request):
    """ajax API to update data"""
    jsonresponse={'saved':False,'message':'Unknown error'}
    try:
        if not request.is_ajax():
            return HttpResponse('API call: Not Ajax')
        else:
            if request.method == 'POST':
                folder_type=request.POST.get('folder_type')
                folder_path=request.POST.get('folder_path')
                folder_path=os.path.normpath(folder_path) if folder_path else '' #cope with windows filepaths
                log.debug(folder_type)
                log.debug(folder_path)
                if folder_type=='local':
                    request.session['scanfolder']=folder_path
                    jsonresponse={'saved':True}
                if folder_type=='master':
                    new_masterindex_path=folder_path
                    request.session['masterfolder']=new_masterindex_path
                    jsonresponse={'saved':True}
                    if new_masterindex_path != DEFAULT_MASTERINDEX_PATH:
                       configs.userconfig.update('Dups','masterindex_path',new_masterindex_path)
                log.debug('Json response:{}'.format(jsonresponse))
            else:
                log.debug('Error: Get to API')
    except Exception as e:
        log.debug(e)
    return JsonResponse(jsonresponse)
    
@staff_member_required()
def file_dups_api(request):
    """ajax API to get duplicates by hash"""
    jsonresponse={'dups':'', 'message':'No files or error'}
    try:
        if not request.is_ajax():
            return HttpResponse('API call: Not Ajax')
        else:
            log.debug(request.GET)

            if request.method == 'GET':
                _hash=request.GET.get('hash')
                if file_utils.safe_hash(_hash):
                    masterindex_path=request.session.get('masterfolder',DEFAULT_MASTERINDEX_PATH)
                    if masterindex_path:
                        masterspecs=file_utils.StoredBigFileIndex(os.path.join(MEDIAROOT,masterindex_path))
                        duplist=file_utils.specs_path_list(masterspecs,_hash)
                        log.debug(duplist)
                        jsonresponse={'dups':duplist}
                    else:
                        log.debug('no masterfolder stored')
                else:
                    log.debug('invalid hash')
            else:
                log.debug('Error: send a Get request')
    except Exception as e:
        log.debug(e)
    log.debug('Json response:{}'.format(jsonresponse))
    return JsonResponse(jsonresponse)
    
@staff_member_required()
def file_dups(request,_hash):
    duplist_master,duplist_local="",""
    page=pages.FilesPage(request=request,default_master=DEFAULT_MASTERINDEX_PATH)
    page.get_stored(MEDIAROOT)
    destination=request.session.get('destination')
    page.hash=None
    if file_utils.safe_hash(_hash):
        page.hash=_hash
        log.info(f'Displaying dups for hash: {_hash}')
        if request.method=='POST':
            log.debug(request.POST)
            checklist=request.POST.getlist('checked')
            if request.POST.get('delete-button')=='Delete':
                log.debug(f'Deleting: {checklist}')
                for path in checklist:
                    if path=="":
                        continue
                    if os.path.exists(path):
                        result=file_utils.delete_file(path)
                        log.info(f'Deleted: {path} Result: {result}')
                        if result: #result:
                            try:
                                page.remove_file(path)
                            except Exception as e:
                                log.error(e)
                    else:
                        log.info(f'Remove non-existing {path} from database')
                        try:
                            page.remove_file(path)
                        except Exception as e:
                            log.error(e)
                page.save() #commit the deletes
                
            elif request.POST.get('action')=='move':
                reldest=request.POST.get('destination')
                destination=os.path.join(MEDIAROOT,reldest)
                assert os.path.exists(destination)
                request.session['destination']=reldest
                
                for f in checklist:
                    if f=='':
                        continue
                    filename=os.path.basename(f)
                    filedest=os.path.join(destination,filename)
                    log.debug(f'Moving ... {f} to {filedest}')
                    result=file_utils.move_file(f,filedest)
                    log.info(f'Moved.. \'{f}\' to \'{filedest}\' result:{result}')
                    if result:
                        page.move_file(f,filedest)
                    
                        
        
        if page.masterspecs:
            duplist_master=file_utils.specs_path_list(page.masterspecs,_hash)
            log.debug(duplist_master)
        if page.specs:
            log.debug(page.specs)
            duplist_local=file_utils.specs_path_list(page.specs,_hash)
            log.debug(duplist_local)
        #log.debug(page.__dict__)
        return_url=request.session.get('lastpage')
        page.return_url=return_url if return_url else None
        if duplist_local or duplist_master:
            return render(request,'dups/list_files.html',
                                   {'files_master': duplist_master,
                                   'files_local':duplist_local,
                                   'default_destination':destination,
                                   'page':page,
                                   })  #removing page
        else:
            return render(request,'dups/list_files.html',
                                   {'files_master': None,
                                   'files_local':None,
                                   'default_destination':None,
                                   'page':page,
                                   })  #removing page
    return HttpResponse('error')
    
    
    