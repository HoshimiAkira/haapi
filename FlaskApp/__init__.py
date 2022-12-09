from flask import Flask , request, jsonify, make_response
from .package.module import MODULE_VALUE
from flask_cors import CORS
from pymongo import MongoClient
import jwt
import bcrypt
import datetime
from bson import ObjectId
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient,BlobBlock
import os,uuid

app = Flask(__name__)
CORS(app)
client = MongoClient("mongodb://havideomongo:c9y9p7KBDdwdlyYmkVKu5Y2v0qAoySaPhW8rcu6kFHRijIYTLjtes4NlAe7AJOzWq9em7cXhOHUXACDbdofrzQ==@havideomongo.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@havideomongo@")
db = client.havideo
video=db.video
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
                return make_response(jsonify( {'token':token,'username':user["username"],'identity':user["identity"]}), 200)
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
    
    password=password.encode('UTF-8')
    password=bcrypt.hashpw(password, \
        bcrypt.gensalt())

    info={
        "username":username,
        "password":password,
        "email":email,
        "identity":"user",
        "collectVideo":[]
    }

    users.insert_one(info)
    return make_response(jsonify( {'success':"Sign up success."}), 200)

@app.route('/api/v1.0/upload', methods=['POST'])
def upload():
    data=request.form
    files=request.files
    if video.find_one( {'title':data["title"] })!=None:
        return make_response(jsonify( {'fail':"Upload fail.Please Change your title"}), 400)
    local_path = "./file/"
    vid=files["video"]
    videoName=vid.filename
    vid.save("./file/"+videoName)
    video_path = os.path.join(local_path, vid.filename)
    video_client = blob_service_client.get_blob_client(container="havideoassvideo", blob=videoName)
    cover=files["cover"]
    coverName=cover.filename
    cover.save("./file/"+coverName)
    cover_path = os.path.join(local_path, cover.filename)
    cover_client = blob_service_client.get_blob_client(container="havideoassimg", blob=coverName)
    try:
        block_list=[]
        chunk_size=1024*1024
        with open(file=video_path, mode="rb") as videodata:
            while True:
                read_data = videodata.read(chunk_size)
                if not read_data:
                    break # done
                blk_id = str(uuid.uuid4())
                video_client.stage_block(block_id=blk_id,data=read_data)
                block_list.append(BlobBlock(block_id=blk_id))
        video_client.commit_block_list(block_list)
        os.remove("./file/"+videoName)
        with open(file=cover_path, mode="rb") as coverdata:
            cover_client.upload_blob(coverdata)
        os.remove("./file/"+coverName)
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
            "views":0,
            "collect":0
        }
        video.insert_one(info)
        return make_response(jsonify( {'success':"Upload success."}), 200)
    except:
        try:
            os.remove("./file/"+videoName)
            os.remove("./file/"+coverName)
        finally:
            return make_response(jsonify( {'message':"Upload fail.Please Change your file name"}), 400)

    













@app.route('/api/v1.0/addStafff', methods=['GET'])
def testregister(): 
    info={
        "username" : "admin",
        "password" : b"admin",
        "email" : "Zhang-T5@ulster.ac.uk",
        "identity":"admin",
        "collectVideo":[]
    }
    info["password"] = \
        bcrypt.hashpw(info["password"], \
        bcrypt.gensalt())
    users.insert_one(info)
    return make_response(jsonify( {'token':"success"}), 200)

    


if __name__ == "__main__":
    app.run()