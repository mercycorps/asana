import datetime
import urllib2
import json
import base64
import csv
import operator

from django.http import HttpResponseRedirect
from .forms import ReadForm, UploadForm, ODKForm, SiloForm, FieldEditForm, MongoEditForm
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden,\
    HttpResponseRedirect, HttpResponseNotFound, HttpResponseBadRequest,\
    HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect, render
from django.template import RequestContext, Context
from django.db import models
from django.shortcuts import render_to_response
from django.shortcuts import render
from django.db.models import Max
from django.db.models import F
from django.views.decorators.csrf import csrf_protect
from .tables import SiloTable
import django_tables2 as tables
from django_tables2 import RequestConfig

from .models import Silo, DataField, ValueStore, RemoteEndPoint, Read, ReadType, LabelValueStore
from .serializers import SiloSerializer, UserSerializer, ReadSerializer, ReadTypeSerializer

from django.contrib.auth.decorators import login_required
from tola.util import siloToDict

from rest_framework import renderers, viewsets
from django.core.urlresolvers import reverse

from django.utils import timezone

# Edit existing silo meta data
@csrf_protect
def editSilo(request, id):
    getSilo = Silo.objects.get(pk=id)

    if request.method == 'POST':  # If the form has been submitted...
        form = SiloForm(request.POST, instance=getSilo)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # save data to read
            updated = form.save()
            return HttpResponseRedirect('/display')  # Redirect after POST to getLogin
        else:
            print form.errors
            return HttpResponse("Form Did Not Save!")
    else:

        form = SiloForm(instance=getSilo)  # An unbound form

    return render(request, 'silo/edit.html', {
        'form': form, 'silo_id': id,
    })


#DELETE-SILO
@csrf_protect
def deleteSilo(request, id):
    deleteSilo = Silo.objects.get(pk=id).delete()

    return render(request, 'silo/delete.html')


#READ VIEWS
def home(request):
    """
    List of Current Read sources that can be updated or edited
    """
    get_reads = Read.objects.all()

    return render(request, 'read/home.html', {'getReads': get_reads, })


def initRead(request):
    """
    Create a form to get feed info then save data to Read
    and re-direct to getJSON or uploadFile function
    """
    if request.method == 'POST':  # If the form has been submitted...
        form = ReadForm(request.POST, request.FILES)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # save data to read
            new_read = form.save()
            id = str(new_read.id)
            if form.instance.file_data:
                redirect_var = "file/%s" % id
            else:
                redirect_var = "read/login"
            return HttpResponseRedirect('/' + redirect_var + '/')  # Redirect after POST to getLogin
        else:
            messages.error(request, 'Invalid Form', fail_silently=False)
    else:
        form = ReadForm()  # An unbound form

    return render(request, 'read/read.html', {
        'form': form,
    })

def odk(request):
    """
    Create a form to get add an ODK service like formhub or Ona
    and re-direct to login
    """
    if request.method == 'POST':  # If the form has been submitted...
        form = ODKForm(request.POST, request.FILES)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # save data to read
            if request.POST['url_source']:
                url_read = request.POST['url_source']
            else:
                url_read = request.POST['source']
            redirect_var = "read/odk_login"
            return HttpResponseRedirect('/' + redirect_var + '/?read_url=' + url_read)  # Redirect after POST to getLogin
        else:
            messages.error(request, 'Invalid Form', fail_silently=False)
    else:
        form = ODKForm()  # An unbound form

    return render(request, 'read/odkform.html', {
        'form': form,
    })

def odkLogin(request):
    """
    Some services require a login provide user with a
    login to service if needed and select a silo
    """
    # get all of the silo info to pass to the form
    get_silo = Silo.objects.all()

    #url from service
    url = request.GET.get('read_url', 'TEST')

    #redirect to JSON list of forms
    redirect_var = "read/odk_login"

    # display login form
    return render(request, 'read/login.html', {'get_silo': get_silo, 'url': url, 'redirect_var': redirect_var})


def showRead(request, id):
    """
    Show a read data source and allow user to edit it
    """
    get_read = Read.objects.get(pk=id)

    if request.method == 'POST':  # If the form has been submitted...
        form = ReadForm(request.POST, request.FILES, instance=get_read)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # save data to read
            form.save()
            if form.instance.file_data:
                redirect_var = "file/" + id + "/"
            else:
                redirect_var = "read/login/"
            return HttpResponseRedirect('/' + redirect_var)  # Redirect after POST to getLogin
        else:
            messages.error(request, 'Invalid Form', fail_silently=False)
    else:
        form = ReadForm(instance=get_read)  # An unbound form

    return render(request, 'read/read.html', {
        'form': form, 'read_id': id,
    })


def uploadFile(request, id):
    """
    Upload CSV file and save its data
    """
    if request.method == 'POST':
        form = UploadForm(request.POST)  # A form bound to the POST data
        if form.is_valid():
            read_obj = Read.objects.get(pk=id)
            today = datetime.date.today()
            today.strftime('%Y-%m-%d')
            today = str(today)
            
            #New silo or existing
            if request.POST['new_silo']:
                new_silo = Silo(name=request.POST['new_silo'], source=read_obj, owner=read_obj.owner, create_date=today)
                new_silo.save()
                silo_id = new_silo.id
            else:
                silo_id = request.POST['silo_id']

            #create object from JSON String
            data = csv.reader(read_obj.file_data)
            
            labels = data.next() #First row of CSV should be Column Headers

            for row in data:
                lvs = LabelValueStore()
                lvs.silo_id = silo_id
                for col_counter, val in enumerate(row):
                    if labels[col_counter] is not "" and labels[col_counter] is not None: setattr(lvs, labels[col_counter], val) 
                lvs.create_date = timezone.now()
                lvs.save()
            
            return HttpResponseRedirect('/silo_detail/' + str(silo_id) + '/')
    else:
        form = UploadForm()  # An unbound form

    # get all of the silo info to pass to the form
    get_silo = Silo.objects.all()
    
    # display login form
    return render(request, 'read/file.html', {
        'form': form, 'read_id': id, 'get_silo': get_silo,
    })


def getLogin(request):
    """
    Some services require a login provide user with a
    login to service if needed and select a silo
    """
    # get all of the silo info to pass to the form
    get_silo = Silo.objects.all()

    # display login form
    return render(request, 'read/login.html', {'get_silo': get_silo})


def getJSON(request):
    """
    Get JSON feed info from form then grab data
    """
    # retrieve submitted Feed info from database
    read_obj = Read.objects.latest('id')
    # set date time stamp
    today = datetime.date.today()
    today.strftime('%Y-%m-%d')
    today = str(today)
    try:
        request2 = urllib2.Request(read_obj.read_url)
        #if they passed in a usernmae get auth info from form post then encode and add to the request header
        if request.POST['user_name']:
            username = request.POST['user_name']
            password = request.POST['password']
            base64string = base64.encodestring('%s:%s' % (username, password))[:-1]
            request2.add_header("Authorization", "Basic %s" % base64string)
        #retrieve JSON data from formhub via auth info
        json_file = urllib2.urlopen(request2)
    except Exception as e:
        print e
        messages.success(request, 'Authentication Failed, Please double check your login credentials and URL!')

    #New silo or existing
    if request.POST['new_silo']:
        #print "NEW"
        new_silo = Silo(name=request.POST['new_silo'], source=read_obj, owner=read_obj.owner, create_date=today)
        new_silo.save()
        silo_id = new_silo.id
    else:
        #print "EXISTING"
        silo_id = request.POST['silo_id']

    #create object from JSON String
    data = json.load(json_file)
    json_file.close()
    
    #loop over data and insert create and edit dates and append to dict
    for row in data:
        lvs = LabelValueStore()
        lvs.silo_id = silo_id
        for new_label, new_value in row.iteritems():
            if new_value is not "" and new_label is not None:
                setattr(lvs, new_label, new_value)
        lvs.create_date = timezone.now()
        lvs.save()
    messages.success(request, "Data imported correctly into MONGO")
    #return render(request, "read/show-columns.html", {'getFields': None, 'silo_id': silo_id})
    return HttpResponseRedirect('/silo_detail/' + silo_id + '/')

#display
#INDEX
def index(request):
    return render(request, 'index.html')

#SILOS
def listSilos(request):
    """
    Each silo is listed with links to details
    """
    #get all of the silos
    get_silos = Silo.objects.all()

    return render(request, 'display/silos.html',{'get_silos':get_silos})

#SILO-SOURCES
def listSiloSources(request):
    """
    List all of the silo sources (From Read model) and provide links to edit
    """
    #get fields to display back to user for verification
    getSources = Read.objects.filter(silo_id=silo_id)

    #send the keys and vars from the json data to the template along with submitted feed info and silos for new form
    return render_to_response("display/stores.html", {'getSilo':getSilo,'silo_id':silo_id})

#Display a single Silo
def viewSilo(request,id):
    """
    View a silo and it's meta data
    """
    silo_id = id
    #get all of the silos
    get_sources = Read.objects.all().filter(silo__id=silo_id)

    return render(request, 'display/silo-sources.html',{'get_sources':get_sources})

        
def define_table(columns):
    from django.template.base import add_to_builtins
    add_to_builtins('silo.templatetags.underscoretags')
    
    """
    Dynamically builds a django-tables2 table without specifying the column names
    It is important to build the django-tables2 dynamically because each time a silo 
    is loaded from MongoDB, it is not known what columns heading it has or how mnay columns it has
    """
    EDIT_DEL_TEMPLATE = '''
        <a class="btn btn-default btn-xs" role="button" href="/value_edit/{{ record|get:'_id'|get:'$oid' }}">Edit</a>
        <a class="btn btn-danger btn-xs" style="color: #FFF;" role="button" href="/value_delete/{{ record|get:'_id'|get:'$oid'  }}">Delete</button> 
        '''
    attrs = dict((c, tables.Column()) for c in columns)
    attrs['Operation'] = tables.TemplateColumn(EDIT_DEL_TEMPLATE)
    attrs['Meta'] = type('Meta', (), dict(exclude=["_id", "edit_date", "create_date"], attrs={"class":"paleblue", "orderable":"True", "width":"100%"}) )
    
    klass = type('DynamicTable', (tables.Table,), attrs)
    return klass


#SILO-DETAIL Show data from source
def siloDetail(request,id):
    """
    Show silo source details
    """
    table = LabelValueStore.objects(silo_id=id).to_json()
    decoded_json = json.loads(table)
    
    if decoded_json:
        silo = define_table(decoded_json[0].keys())(decoded_json)
    
        #This is needed in order for table sorting to work
        RequestConfig(request).configure(silo)
    
        #send the keys and vars from the json data to the template along with submitted feed info and silos for new form
        return render(request, "display/stored_values.html", {"silo": silo})
    else:
        messages.error(request, "Silo with id = %s does not exist" % id)
        return HttpResponseRedirect(request.META['HTTP_REFERER'])

#SHOW-MERGE FORM
def mergeForm(request,id):
    """
    Merge different silos using a multistep column mapping form
    """
    getSource = Silo.objects.get(id=id)
    getSourceTo = Silo.objects.all()
    return render(request, "display/merge-form.html", {'getSource':getSource,'getSourceTo':getSourceTo})

#SHOW COLUMNS FOR MERGE FORM
def mergeColumns(request):
    """
    Step 2 in Merge different silos, map columns
    """
    from_silo_id = request.POST["from_silo_id"]
    to_silo_id = request.POST["to_silo_id"]

    lvs = json.loads(LabelValueStore.objects(silo_id__in = [from_silo_id, to_silo_id]).to_json())
    getSourceFrom = []
    getSourceTo = []
    for l in lvs:
        if from_silo_id == str(l['silo_id']):
            getSourceFrom.extend([k for k in l.keys() if k not in getSourceFrom])
        else:
            getSourceTo.extend([k for k in l.keys() if k not in getSourceTo])
    
    return render(request, "display/merge-column-form.html", {'getSourceFrom':getSourceFrom, 'getSourceTo':getSourceTo, 'from_silo_id':from_silo_id, 'to_silo_id':to_silo_id})

import pymongo
def doMerge(request):
    from_silo_id = request.POST['from_silo_id']
    to_silo_id = request.POST["to_silo_id"]

    try:
        from_silo_id = int(from_silo_id)
        to_silo_id = int(to_silo_id)
    except ValueError as e:
        from_silo_id = None
        to_silo_id = None
        print("The from_silo_id and/or the to_silo_id is not an integer")
    
    conn = pymongo.Connection()
    db = conn.tola

    if from_silo_id != None and to_silo_id != None:
        for k in request.POST:
            if k != "silo_id" and k !=  "_id" and k != "to_silo_id" and k != "from_silo_id" and k != "csrfmiddlewaretoken": 
                from_field = request.POST.getlist(k)[0].lower()
                to_field = request.POST.getlist(k)[1].lower()
            
                if to_field == "Ignore":
                    "This field should be deleted from the silo_id = 'from_silo_id'"
                    print ("FROM FIELD: %s and SILO_ID: %s" % (from_field, from_silo_id))
                    db.label_value_store.update( 
                        { "silo_id": from_silo_id }, 
                        { 
                            "$unset": {from_field: ""}, 
                        }, 
                        False,  False,  None, True 
                    )
                elif to_field == "0":
                    "Nothing should be done in this case because when the silo_id is updated to to_silo_id this field will become part of the to_silo_id "
                    pass
                else:
                    db.label_value_store.update(
                        { "silo_id": from_silo_id }, 
                        { 
                            "$rename": { from_field:  to_field },  
                            "$currentDate": { 'edit_date': True } 
                        }, 
                        False, False, None, True 
                    )

        db.label_value_store.update( 
            { "silo_id": from_silo_id }, 
            { 
                "$set": { "silo_id": to_silo_id }, 
            }, 
            False, False, None, True 
        )
        Silo.objects.filter(pk = from_silo_id).delete()
    #messages.success(request, "Silos merged successfully")
    return HttpResponseRedirect("/silo_detail/%s" % to_silo_id)

#EDIT A SINGLE VALUE STORE
def valueEdit(request,id):
    """
    Edit a value
    """
    doc = LabelValueStore.objects(id=id).to_json()
    data = {}
    jsondoc = json.loads(doc)
    silo_id = None
    for item in jsondoc:
        for k, v in item.iteritems():
            #print("The key and value are ({}) = ({})".format(k, v))
            if k == "_id":
                #data[k] = item['_id']['$oid']
                pass
            elif k == "silo_id":
                silo_id = v
            elif k == "edit_date":
                edit_date = datetime.datetime.fromtimestamp(item['edit_date']['$date']/1000)
                data[k] = edit_date.strftime('%Y-%m-%d %H:%M:%S')
            elif k == "create_date":
                create_date = datetime.datetime.fromtimestamp(item['create_date']['$date']/1000)
                data[k] = create_date.strftime('%Y-%m-%d')
            else:
                data[k] = v
    if request.method == 'POST': # If the form has been submitted...
        form = MongoEditForm(request.POST or None, extra = data) # A form bound to the POST data
        if form.is_valid():
            lvs = LabelValueStore.objects(id=id)[0]
            for lbl, val in form.cleaned_data.iteritems():
                if lbl != "id" and lbl != "silo_id" and lbl != "csrfmiddlewaretoken":
                    setattr(lvs, lbl, val)
            lvs.edit_date = timezone.now()
            lvs.save()
            return HttpResponseRedirect('/value_edit/' + id)
        else:
            print "not valid"
    else:
        form = MongoEditForm(initial={'silo_id': silo_id, 'id': id}, extra=data)

    return render(request, 'read/edit_value.html', {'form': form, 'silo_id': silo_id})

def valueDelete(request,id):
    """
    Delete a value
    """
    #deleteStore = ValueStore.objects.get(pk=id).delete()
    
    lvs = LabelValueStore.objects(id=id)[0]
    silo_id = lvs.silo_id
    lvs.delete()
    
    messages.success(request, "Record deleted successfully")
    return render(request, 'read/delete_value.html')

#FEED VIEWS
# API Classes

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class SiloViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """
    queryset = Silo.objects.all()
    serializer_class = SiloSerializer

class ReadViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """
    queryset = Read.objects.all()
    serializer_class = ReadSerializer

class ReadTypeViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """
    queryset = ReadType.objects.all()
    serializer_class = ReadTypeSerializer

# End API Classes


def customFeed(request,id):
    """
    All tags in use on this system
    id = Silo
    """
    queryset = LabelValueStore.objects.exclude("silo_id").filter(silo_id=id).to_json()

    return render(request, 'feed/json.html', {"jsonData": queryset}, content_type="application/json")

#Feeds
def listFeeds(request):
    """
    Get all Silos and Link to REST API pages
    """
    #get all of the silos
    #getSilos = Silo.objects.all()
    getSilos = Silo.objects.all().prefetch_related('remote_end_points')

    return render(request, 'feed/list.html',{'getSilos': getSilos})

def createFeed(request):
    """
    Create an XML or JSON Feed from a given Silo
    """
    getSilo = ValueStore.objects.filter(field__silo__id=request.POST['silo_id']).order_by('row_number')

    #return a dict with label value pair data
    formatted_data = siloToDict(getSilo)

    getFeedType = FeedType.objects.get(pk = request.POST['feed_type'])

    if getFeedType.description == "XML":
        xmlData = serialize(formatted_data)
        return render(request, 'feed/xml.html', {"xml": xmlData}, content_type="application/xhtml+xml")
    elif getFeedType.description == "JSON":
        jsonData = simplejson.dumps(formatted_data)
        return render(request, 'feed/json.html', {"jsonData": jsonData}, content_type="application/json")

def export_silo(request, id):
    
    silo_name = Silo.objects.get(id=id).name
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s.csv"' % silo_name
    writer = csv.writer(response)

    silo_data = LabelValueStore.objects(silo_id=id)
    if silo_data:
        columns_headings = [col for col in silo_data[0]]
        writer.writerow(columns_headings)
        
        for row in silo_data:
            writer.writerow([row[col] for col in row])

    return response

from oauth2client.client import flow_from_clientsecrets
from oauth2client.django_orm import Storage
from oauth2client import xsrfutil
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from .models import GoogleCredentialsModel
from apiclient.discovery import build
import os, logging, httplib2, json, datetime

import gdata.spreadsheets.client


from django.http import JsonResponse

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
FLOW = flow_from_clientsecrets(
    CLIENT_SECRETS,
    scope='https://www.googleapis.com/auth/drive https://spreadsheets.google.com/feeds',
    redirect_uri=settings.GOOGLE_REDIRECT_URL)
    #redirect_uri='http://localhost:8000/oauth2callback/')


def export_to_google_spreadsheet(credential_json, silo_id, spreadsheet_key):


    # Create OAuth2Token for authorizing the SpreadsheetClient
    token = gdata.gauth.OAuth2Token(
        client_id = credential_json['client_id'],
        client_secret = credential_json['client_secret'],
        scope = 'https://spreadsheets.google.com/feeds',
        user_agent = "TOLA",
        access_token = credential_json['access_token'],
        refresh_token = credential_json['refresh_token'])

    # Instantiate the SpreadsheetClient object
    sp_client = gdata.spreadsheets.client.SpreadsheetsClient(source="TOLA")

    # authorize the SpreadsheetClient object
    sp_client = token.authorize(sp_client)
    #print(sp_client)
    
    
    # Create a WorksheetQuery object to allow for filtering for worksheets by the title
    worksheet_query = gdata.spreadsheets.client.WorksheetQuery(title="Sheet1", title_exact=True)
    
    
    # Get a feed of all worksheets in the specified spreadsheet that matches the worksheet_query
    worksheets_feed = sp_client.get_worksheets(spreadsheet_key, query=worksheet_query)
    #print("worksheets_feed: %s" % worksheets_feed)
    
    
    # Retrieve the worksheet_key from the first match in the worksheets_feed object
    worksheet_key = worksheets_feed.entry[0].id.text.rsplit("/", 1)[1]
    #print("worksheet_key: %s" % worksheet_key)
    
    silo_data = LabelValueStore.objects(silo_id=silo_id)
    
    # Create a CellBatchUpdate object so that all cells update is sent as one http request
    batch = gdata.spreadsheets.data.BuildBatchCellsUpdate(spreadsheet_key, worksheet_key)
    
    col_index = 0
    row_index = 1
    col_info = {}
    
    for row in silo_data:
        row_index = row_index + 1
        for i, col_name in enumerate(row):
            if col_name not in col_info.keys():
                col_index = col_index + 1
                col_info[col_name] = col_index
                batch.add_set_cell(1, col_index, col_name) #Add column names
            #print("%s = %s - %s: %s" % (col_info[col_name], col_name, type(row[col_name]),  row[col_name]))
            
            val = row[col_name]
            if col_name != "isd":
                try:
                    #val = str(val)#.encode('ascii', 'ignore')
                    val = val.encode('ascii', 'xmlcharrefreplace')
                except Exception as e:
                    try:
                        val = str(val)
                    except Exception as e1:                        
                        print(e)
                        print(val)
                        pass
            
                batch.add_set_cell(row_index, col_info[col_name], val)
    
    # By default a blank Google Spreadsheet has 26 columns but if our data has more column
    # then add more columns to Google Spreadsheet otherwise there would be a 500 Error!
    if col_index and col_index > 26:
        worksheet = worksheets_feed.entry[0]
        worksheet.col_count.text = str(col_index)

        # Send the worksheet update call to Google Server
        sp_client.update(worksheet, force=True)

    try:
        # Finally send the CellBatchUpdate object to Google
        sp_client.batch(batch, force=True)
    except Exception as e:
        print("ERROR: %s" % e)
        return False

    return True


@login_required
def export_gsheet(request, id):
    gsheet_endpoint = None
    storage = Storage(GoogleCredentialsModel, 'id', request.user, 'credential')
    credential = storage.get()
    if credential is None or credential.invalid == True:
        FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY, request.user)
        authorize_url = FLOW.step1_get_authorize_url()
        #return HttpResponseRedirect(authorize_url)
        messages.error(request, "You must first <a href='%s'>authorize</a> before you could export to Gooogle Spreadsheet." % authorize_url)
        return JsonResponse({"redirect_url": authorize_url})

    credential_json = json.loads(credential.to_json())

    try:
        gsheet_endpoint = RemoteEndPoint.objects.get(silo__id=id, silo__owner = request.user, name='Google')
    except RemoteEndPoint.MultipleObjectsReturned:
        print("multiple records exist and that should NOT be the case")
    except RemoteEndPoint.DoesNotExist:
        print("Remote End point does not exist; creating one...")
        url = request.GET.get('link', None)
        file_id = request.GET.get('resource_id', None)
        if url == None:
            print ("No link provided for the remote end point")
        if file_id == None:
            print("No file id is available")
        gsheet_endpoint = RemoteEndPoint(name="Google", silo_id=id, link=url, resource_id=file_id)
        gsheet_endpoint.save()
    except Exception as e:
        print(e)

    #print("about to export to gsheet: %s" % gsheet_endpoint.resource_id)
    if export_to_google_spreadsheet(credential_json, id, gsheet_endpoint.resource_id) == True:
        link = "Your exported data is available at <a href=" + gsheet_endpoint.link + " target='_blank'>Google Spreadsheet</a>"
        messages.success(request, link)
    else:
        messages.error(request, 'Something went wrong; try again; here we go.')

    return JsonResponse({'foo': 'bar'})

@login_required
def export_new_gsheet(request, id):
    storage = Storage(GoogleCredentialsModel, 'id', request.user, 'credential')
    credential = storage.get()
    if credential is None or credential.invalid == True:
        FLOW.params['state'] = xsrfutil.generate_token(settings.SECRET_KEY, request.user)
        authorize_url = FLOW.step1_get_authorize_url()
        #print("STEP1 authorize_url: %s", authorize_url)
        return HttpResponseRedirect(authorize_url)

    credential_json = json.loads(credential.to_json())
    silo_id = id
    silo_name = Silo.objects.get(pk=silo_id).name

    http = httplib2.Http()

    # Authorize the http object to be used with "Drive API" service object
    http = credential.authorize(http)

    # Build the Google Drive API service object
    service = build("drive", "v2", http=http)

    # The body of "insert" API call for creating a blank Google Spreadsheet
    body = {
        'title': silo_name,
        'description': "Exported Data from Mercy Corps TolaData",
        'mimeType': "application/vnd.google-apps.spreadsheet"
    }

    # Create a new blank Google Spreadsheet file in user's Google Drive
    google_spreadsheet = service.files().insert(body=body).execute()

    # Get the spreadsheet_key of the newly created Spreadsheet
    spreadsheet_key = google_spreadsheet['id']
    #print(spreadsheet_key)
    if export_to_google_spreadsheet(credential_json, silo_id, spreadsheet_key) == True:
        link = "Your exported data is available at <a href=" + google_spreadsheet['alternateLink'] + " target='_blank'>Google Spreadsheet</a>"
        messages.success(request, link)
    else:
        messages.error(request, 'Something went wrong; try again.')
    return HttpResponseRedirect("/")

@login_required
def oauth2callback(request):
    if not xsrfutil.validate_token(settings.SECRET_KEY, request.REQUEST['state'], request.user):
        return  HttpResponseBadRequest()

    credential = FLOW.step2_exchange(request.REQUEST)
    storage = Storage(GoogleCredentialsModel, 'id', request.user, 'credential')
    storage.put(credential)
    #print(credential.to_json())
    return HttpResponseRedirect("/")


