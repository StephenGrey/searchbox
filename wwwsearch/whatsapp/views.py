# -*- coding: utf-8 -*-
"""
View WhatsApp conversations 

"""
from __future__ import unicode_literals
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Q,Count #Count to count up unique entries
from .models import Message, PhoneNumber
import operator #for sorting
import json, logging
from .conversation import Conversation, get_name, list_messages
from django.http import JsonResponse
log=logging.getLogger('ownsearch.whatsapp.views')


def home(request):    
    combo=list_messages()
    return render(request, 'whatsapp/list.html',{'list': combo})

def messages(request,filter1='',filter2=''):
    
    c=Conversation(filter1,filter2,request=request)
    if c.messages==[]:
        return HttpResponse('No messages')

    return render(request, 'whatsapp/messages.html',{'list': c.messages, 'filter1': c.node1, 'filter2':c.node2, 'filter1_name':c.node1_name, 'filter2_name':c.node2_name, 'filter2_records':c.node2_records, 'filter1_records':c.node1_records, 'preview_html':c.preview_html, 'phonenumber_panel_html': c.phonenumber_panel_html  })

def post_namefiles(request):
    
    #print('Ajax test view:')
    
    if request.is_ajax():
       if request.method == 'POST':
            log.debug('Raw Data: {}'.format( request.body))
    response_json = json.dumps(request.POST)
    data = json.loads(response_json)
    log.debug ("Json data: {}.".format(data))
    
    result,verified=update_phonerecords(data,request.user.username)

    jsonresponse = {
    'saved': result,
    'verified':verified
    }
    return JsonResponse(jsonresponse)


#move this:
def update_phonerecords(data,username):
    log.info('User \'{}\' updating phone records with data: {}'.format(username,data))
    try:
        pid=data.pop('record-ID',None)
        if pid=='':
            log.warning('No record found')
            return False
        existing=PhoneNumber.objects.get(id=pid)
        print('Record found: '.format(existing))
        print(existing.__dict__)
        
        personal=data.pop('personal',None)
        if personal=='true' and existing.personal==False:
            existing.personal=True
            personal_change=True
        elif personal=='false' and existing.personal==True:
            existing.personal=False
            personal_change=False
        else:
            personal_change=None
        
        verified=data.pop('verified',None)
        if verified=='1' and existing.verified==False:
            existing.verified=True
            print('verified True')
            verified_change=True
        elif verified=='0' and existing.verified==True:
            existing.verified=False
            print('verified False')
            verified_change=False
        else:
            verified_change=None
        csrf=data.pop('csrfmiddlewaretoken',None)
        existing.name=data['name']
        existing.name_source=data['name_source']
        existing.name_possible=data['name_possible']
        existing.notes=data['notes']
        existing.save() 
        log.info("New data saved")
        return True,verified_change 
    except Exception as e:
        log.error("Failed to edit phone record data with saved data: {} and error {}".format(data,e))
        return False,None
        
        
 
