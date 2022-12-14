from flask import Flask , request, jsonify, make_response
from .package.module import MODULE_VALUE
from flask_cors import CORS
from pymongo import MongoClient
import jwt
import bcrypt
from datetime import date
import datetime
from bson import ObjectId
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient,BlobBlock
import os,uuid
import tempfile
from functools import wraps
import time

app = Flask(__name__)
CORS(app)
client = MongoClient("mongodb://havideomongo:c9y9p7KBDdwdlyYmkVKu5Y2v0qAoySaPhW8rcu6kFHRijIYTLjtes4NlAe7AJOzWq9em7cXhOHUXACDbdofrzQ==@havideomongo.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@havideomongo@")
db = client.havideo
videos=db.video
users=db.users
app.config['SECRET_KEY'] = 'zsecret'
account_url = "https://havideoassblob.blob.core.windows.net"
default_credential = DefaultAzureCredential()
blob_service_client = BlobServiceClient(account_url, credential=default_credential)
@app.route("/")
def index():
    return (
        "hello world"
    )

def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        token = request.args.get('token')
        if not token:
            return jsonify( {'message' : 'Token is missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'],algorithms='HS256')
        except:
            return jsonify( {'message' : 'Token is invalid'}), 401
        return func(*args, **kwargs)

    return jwt_required_wrapper

@app.route('/api/v1.0/login', methods=['POST'])
def login():
    data=request.form
    email=data["email"]
    password=data["password"]
    if email!= "":
        user=users.find_one( {'email':email } )
        if user is not None:
            if bcrypt.checkpw(bytes(password, 'UTF-8'), user["password"]):
                token = jwt.encode( {'user' : user["email"],'identity' : user["identity"], 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=30)}, app.config['SECRET_KEY'])
                return make_response(jsonify( {'token':token,'username':user["username"],'identity':user["identity"],'id':str(user["_id"])}), 200)
            else:
                return make_response(jsonify( {'message':'Bad password'}), 401)
        else:
            return make_response(jsonify( {'message':'Bad Email'}), 401)
    else:
        return make_response(jsonify({'message':'Email required'}), 401)
    
@app.route('/api/v1.0/register', methods=['POST'])
def register():
    data=request.form
    email=data["email"]
    if(users.find_one( {'email':email })!=None):
        return make_response(jsonify({'message':'Email have been used'}), 401)
    username=data["username"]
    password=data["password"]
    confirm=data["confirm"]
    password=password.encode('UTF-8')
    password=bcrypt.hashpw(password, \
        bcrypt.gensalt())
    if(confirm!="up"):
        info={
            "username":username,
            "password":password,
            "email":email,
            "identity":"user",
            "collectVideo":[]
        }
    else:
        info={
            "username":username,
            "password":password,
            "email":email,
            "identity":"up",
            "collectVideo":[]
        }
    

    users.insert_one(info)
    return make_response(jsonify( {'success':"Sign up success."}), 200)

@app.route('/api/v1.0/video', methods=['POST'])
@jwt_required
def upload():
    data=request.form
    files=request.files
    if videos.find_one( {'title':data["title"] })!=None:
        return make_response(jsonify( {'fail':"Upload fail.Please Change your title"}), 400)
    tempFilePath = tempfile.gettempdir()
    vid=files["video"]
    videoName=vid.filename
    vid.save(tempFilePath+"/"+videoName)
    video_path = os.path.join(tempFilePath, vid.filename)
    video_client = blob_service_client.get_blob_client(container="havideoassvideo", blob=videoName)
    cover=files["cover"]
    coverName=cover.filename
    cover.save(tempFilePath+"/"+coverName)
    cover_path = os.path.join(tempFilePath, cover.filename)
    cover_client = blob_service_client.get_blob_client(container="havideoassimg", blob=coverName)
    try:
        block_list=[]
        chunk_size=1024*1024
        with open(file=video_path, mode="rb") as videodata:
            while True:
                read_data = videodata.read(chunk_size)
                if not read_data:
                    break
                blk_id = str(uuid.uuid4())
                video_client.stage_block(block_id=blk_id,data=read_data)
                block_list.append(BlobBlock(block_id=blk_id))
        video_client.commit_block_list(block_list)
        with open(file=cover_path, mode="rb") as coverdata:
            cover_client.upload_blob(coverdata)
        coverurl="https://havideoassblob.blob.core.windows.net/havideoassimg/"+coverName
        videourl="https://havideoassblob.blob.core.windows.net/havideoassvideo/"+videoName
        info={
            "title":data["title"],
            "publisher":data["publisher"],
            "intro":data["intro"],
            "genre":data["genre"],
            "video":videourl,
            "cover":coverurl,
            "comment":[],
            "producer":data["producer"],
            "views":0,
            "collect":0,
            "date":date.today().isoformat()
        }
        videos.insert_one(info)
        return make_response(jsonify( {'success':"Upload success."}), 200)
    except:
        return make_response(jsonify( {'message':"Upload fail.Please Change your file name"}), 400)

@app.route("/api/v1.0/video", methods=["GET"])
@jwt_required
def show_all_videos():
    page_num, page_size = 1, 9
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))
    data_to_return = []
    showdata=[]
    for video in videos.find().sort("_id",-1):
        video["_id"] = str(video["_id"])
        showdata.append(video)
    if request.args.get("title")!="":
        title=request.args.get("title")
        showdata=title_filter(showdata,title)
    if request.args.get("publisher")!="":
        publisher=request.args.get("publisher")
        showdata=publisher_filter(showdata,publisher)
    if request.args.get("producer")!="":
        producer=request.args.get("producer")
        showdata=producer_filter(showdata,producer)
    if request.args.get("genre")!="":
        genre=request.args.get("genre")
        showdata=genre_filter(showdata,genre)
    for video in showdata[page_start:page_start+page_size]:
        data={
            "id":video["_id"],
            "picSrc":video["cover"],
            "title":video["title"],
            "views":video["views"],
            "collect":video["collect"],
            "date":video["date"]
        }
        
        data_to_return.append(data)
            

    return make_response( jsonify(data_to_return), 200 )

@app.route("/api/v1.0/video/<string:id>", methods=["GET"])
@jwt_required
def show_one_video(id):
    data_to_return=[]
    comment_to_return=[]
    page_num, page_size = 1, 10
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))
    try:
        video = videos.find_one({'_id':ObjectId(id)})
    except:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )
    if video is not None:
        videos.update_one( { "_id" : ObjectId(id) }, { "$set": { "views" : video["views"]+1 } } )
        video['_id'] = str(video['_id'])
        video["views"]+=1
        video["check"]=False
        uid=request.args.get("uid")
        print(uid)
        user=users.find_one({'_id':ObjectId(uid)})
        for col in user["collectVideo"]:
            if(str(col)==video['_id']):
                video["check"]=True
                break
        for comment in video["comment"]:
            comment["_id"]=str(comment["_id"])
            comment_to_return.append(comment)
        video["comment"]=comment_to_return
        data_to_return.append(video)
        return make_response( jsonify( data_to_return ), 200 )
    else:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )
    
@app.route("/api/v1.0/video/<string:id>/comment", methods=["POST"])
@jwt_required
def add_comment(id):
    video = videos.find_one({'_id':ObjectId(id)})
    if video is not None:
        new_comment = {
            "_id" : ObjectId(),
            "user_id" : request.form["user_id"],
            "username" : request.form["username"],
            "comment" : request.form["comment"],
            "mark" : request.form["mark"],
            "date":date.today().isoformat()
        }
        print(new_comment["user_id"])
        print(new_comment["comment"])
        print(new_comment["mark"])
        videos.update_one( { "_id" : ObjectId(id) }, { "$push": { "comment" : new_comment } } )
        return make_response( jsonify( { "success" : "Add Comment Success" } ), 201 )
    else:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )

@app.route("/api/v1.0/video/<string:id>/subtitle", methods=["POST"])
@jwt_required
def add_subtitle(id):
    video = videos.find_one({'_id':ObjectId(id)})
    if video is not None:
        files=request.files
        tempFilePath = tempfile.gettempdir()
        subtitle=files["subtitle"]
        subtitleName=subtitle.filename
        subtitle.save(tempFilePath+"/"+subtitleName)
        subtitle_path = os.path.join(tempFilePath, subtitleName)
        subtitle_client = blob_service_client.get_blob_client(container="havideoassvtt", blob=subtitleName)
        try:
            with open(file=subtitle_path, mode="rb") as vttdata:
                subtitle_client.upload_blob(vttdata)
            vtturl="https://havideoassblob.blob.core.windows.net/havideoassvtt/"+subtitleName
            videos.update_one( { "_id" : ObjectId(id) }, { "$set": { "vtt" : vtturl } } )
            return make_response( jsonify( { "success" : "Add subtitle Success" } ), 201 )
        except:
            return make_response(jsonify( {'message':"Upload fail.Please Change your file name"}), 400)
    else:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )

@app.route("/api/v1.0/video/<string:id>", methods=["DELETE"])
@jwt_required
def delete_video(id):
    try:
        video = videos.find_one({'_id':ObjectId(id)})
    except:
        response = jsonify({"message" : "Invalid video ID"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'DELETE')
        return make_response(  response ), 404 
    video = videos.find_one({'_id':ObjectId(id)})
    if video is not None:
        videoName= video["video"].replace("https://havideoassblob.blob.core.windows.net/havideoassvideo/","")
        video_client = blob_service_client.get_blob_client(container="havideoassvideo", blob=videoName)
        coverName=video["cover"].replace("https://havideoassblob.blob.core.windows.net/havideoassimg/","")
        cover_client = blob_service_client.get_blob_client(container="havideoassimg", blob=coverName)
        video_client.delete_blob()
        cover_client.delete_blob()
        result = videos.delete_one( { "_id" : ObjectId(id) } )
        if result.deleted_count == 1:
            return make_response( {"success":"delete success"}, 204 )
    else:
        response = jsonify({"message" : "Invalid video ID"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'DELETE')
        return make_response(  response ), 404 

@app.route("/api/v1.0/video/<string:vid>/comment/<string:cid>", methods=["DELETE"])
@jwt_required
def delete_comment(vid, cid):
    
    try:
        video = videos.find_one({'_id':ObjectId(vid)})
        comment=ObjectId(cid)
    except:
        response = jsonify({"message" : "Invalid video ID"})
        response.headers.add('Access-Control-Allow-Methods', 'DELETE')
        response.headers.add('Access-Control-Allow-Origin', '*')
        return make_response(  response ), 404 
    videos.update_one( \
    { "_id" : ObjectId(vid) }, \
    { "$pull" : { "comment" : \
    { "_id" : ObjectId(cid) } } } )
    return make_response( jsonify( {"success":"delete success"} ), 204)

@app.route("/api/v1.0/video/<string:id>", methods=["POST"])
@jwt_required
def add_collection(id):
    video = videos.find_one({'_id':ObjectId(id)})
    if video is not None:
        collectNum=video["collect"]
        uid=request.form["id"]
        videos.update_one( { "_id" : ObjectId(id) }, { "$set": { "collect" : collectNum+1 } } )
        users.update_one( { "_id" : ObjectId(uid) }, { "$push": { "collectVideo" : ObjectId(id) } } )
        return make_response( jsonify( { "success" : "Add Collect Success" } ), 201 )
    else:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )

@app.route("/api/v1.0/collection", methods=["GET"])
@jwt_required
def show_all_collection():
    page_num, page_size = 1, 9
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))
    data_to_return = []
    showdata=[]
    uid=request.args.get('id')
    user=users.find_one({'_id':ObjectId(uid)})
    for video in videos.find().sort("_id",-1):
        for col in user["collectVideo"]:
            if(str(col)==str(video["_id"])):
                video["_id"] = str(video["_id"])
                showdata.append(video)
    if request.args.get("title")!="":
        title=request.args.get("title")
        showdata=title_filter(showdata,title)
    if request.args.get("publisher")!="":
        publisher=request.args.get("publisher")
        showdata=publisher_filter(showdata,publisher)
    if request.args.get("producer")!="":
        producer=request.args.get("producer")
        showdata=producer_filter(showdata,producer)
    if request.args.get("genre")!="":
        genre=request.args.get("genre")
        showdata=genre_filter(showdata,genre)
    for video in showdata[page_start:page_start+page_size]:
        data={
            "id":video["_id"],
            "picSrc":video["cover"],
            "title":video["title"],
            "views":video["views"],
            "collect":video["collect"],
            "date":video["date"]
        }
        
        data_to_return.append(data)
            

    return make_response( jsonify(data_to_return), 200 )

@app.route("/api/v1.0/video/<string:id>/cancel", methods=["POST"])
@jwt_required
def cancel_collection(id):
    video = videos.find_one({'_id':ObjectId(id)})
    if video is not None:
        collectNum=video["collect"]
        uid=request.form["id"]
        videos.update_one( { "_id" : ObjectId(id) }, { "$set": { "collect" : collectNum-1 } } )
        users.update_one( { "_id" : ObjectId(uid) }, { "$pull": { "collectVideo" : ObjectId(id) } } )
        return make_response( jsonify( { "success" : "Cancel Collect Success" } ), 201 )
    else:
        return make_response( jsonify( {"message" : "Invalid video ID"} ), 404 )


def title_filter(showdata,title):
    data_to_return = []
    for video in showdata:
        if video["title"].lower().find(title.lower())!=-1:
            data_to_return.append(video)
    return data_to_return


def publisher_filter(showdata,publisher):
    data_to_return = []
    for video in showdata:
        if publisher.lower()in video["publisher"].lower() :
            data_to_return.append(video)
    return data_to_return

def producer_filter(showdata,producer):
    data_to_return = []
    for video in showdata:
        if  producer.lower() in video["producer"].lower():
            data_to_return.append(video)
    return data_to_return

def genre_filter(showdata,genre):
    data_to_return = []
    for video in showdata:
        if genre.lower() in video["genre"].lower():
            data_to_return.append(video)
    return data_to_return







    


if __name__ == "__main__":
    app.run()