import os
import base64
import concurrent.futures

from pydantic import BaseModel
from bson.objectid import ObjectId
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv, find_dotenv
from pymongo.mongo_client import MongoClient
from fastapi.templating import Jinja2Templates
from fastapi import Form, Request, responses, FastAPI

from pytube import Playlist, YouTube
from src.youtube_scraper.YT2Image import YouTubeDownloader

load_dotenv(find_dotenv())

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Connect to the MongoDB database
client = MongoClient(os.environ.get('MONGO_URI'))
db = client['youtube_data']


class FetchDataForm(BaseModel):
    data_type: str
    data_input: str


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Renders the home page of the application.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/fetch-data/", response_class=HTMLResponse)
async def fetch_data(request: Request, data_type: str = Form(...), data_input: str = Form(...)):
    """
    Fetches the data from the YouTube API and stores the metadata in the MongoDB database.
    """
    folder_path = "./output"
    youtubemanager = YouTubeDownloader()
    print(data_type, data_input)
    if data_type == "youtube_link":
        if "https://youtube.com/playlist?" in data_input:
            print("Playlist link detected")
            playlist = Playlist(data_input)
            video_metadata = youtubemanager.get_video_metadata(
                folder_path, playlist_data=playlist)
        else:
            youtube = YouTube(data_input)
            video_metadata = youtubemanager.get_video_metadata(
                folder_path, youtube_data=youtube)

        youtubemanager.save_metadata_to_json(
            file_name=video_metadata[0]['title'].replace(" ", "_"), metadata=video_metadata)

        youtubemanager.extract_images(folder_path)

        youtubemanager.delete_folder(folder_path)

        # Finding metadata for each video
        video_meta = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(
                db['metadata'].find_one, {'video_id': video_id}, {'title': 1, 'video_id': 1}) for video_id in db['image'].distinct('video_id')]
            concurrent.futures.wait(futures)
            for future in futures:
                video_meta.append(future.result())

        return templates.TemplateResponse("select_videos.html", {"request": request, "videos": video_meta})


@app.get("/get-fetch-data/", response_class=HTMLResponse)
async def fetch_video(request: Request):
    """
    Renders the page for fetching data from the YouTube API.
    """
    video_meta = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(
            db['metadata'].find_one, {'video_id': video_id}, {'title': 1, 'video_id': 1}) for video_id in db['image'].distinct('video_id')]
        concurrent.futures.wait(futures)
        for future in futures:
            video_meta.append(future.result())

    return templates.TemplateResponse("select_videos.html", {"request": request, "videos": video_meta})


@app.get("/images/", response_class=HTMLResponse)
async def read_root(request: Request, video_id: str):
    """
    Renders the page for displaying the images of a video.
    """
    # Fetch all images from the collection
    images_cursor = db["image"].find({'video_id': video_id})
    images = []

    def image_bs64(img: dict):
        img['image_base64'] = base64.b64encode(img['image_id']).decode('utf-8')
        return img

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(image_bs64, img) for img in images_cursor]
        concurrent.futures.wait(futures)
        for future in futures:
            images.append(future.result())

    return templates.TemplateResponse("display_images.html", {"request": request, "images": images})


@app.post("/delete-selected-images/")
async def delete_selected_images(request: Request, image_ids: str = Form(...)):
    """
    Deletes the selected images from the MongoDB database.
    """
    image_id_list = image_ids.split(',')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(db["image"].delete_one, {"_id": ObjectId(image_id)})
                   for image_id in image_id_list]
        concurrent.futures.wait(futures)

    return responses.JSONResponse(status_code=200, content={"message": "Images deleted successfully!"})
