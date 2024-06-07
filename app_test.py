import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, Request, responses
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv, find_dotenv
from pymongo.mongo_client import MongoClient

load_dotenv(find_dotenv())

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Connect to the MongoDB database
client = MongoClient(os.environ.get('MONGO_URI'))
db = client['medium_data']

class FetchDataForm:
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
    Fetches the data from Medium and stores the metadata in the MongoDB database.
    """
    if data_type == "medium_author":
        url = data_input
        print(f"Fetching data from: {url}")
        articles = scrape_medium_articles(url)

        # Print the scraped articles for debugging
        print(f"Scraped Articles: {articles}")

        # Save articles to MongoDB
        if articles:
            result = db['articles'].insert_many(articles)
            print(f"Inserted Article IDs: {result.inserted_ids}")
        else:
            print("No articles to insert.")

        return templates.TemplateResponse("select_articles.html", {"request": request, "articles": articles})

def scrape_medium_articles(url):
    """
    Scrapes articles from the given Medium author's page.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    articles = []
    for item in soup.find_all('div', class_='postArticle'):
        title_tag = item.find('h3')
        if title_tag:
            title = title_tag.text
        else:
            title = "No title"

        link_tag = item.find('a', {'data-action': 'open-post'})
        if link_tag:
            link = link_tag['href']
        else:
            link = "No link"

        subtitle_tag = item.find('h4')
        if subtitle_tag:
            subtitle = subtitle_tag.text
        else:
            subtitle = "No subtitle"

        article = {
            'title': title,
            'link': link,
            'subtitle': subtitle
        }
        articles.append(article)

    return articles

@app.get("/get-fetch-data/", response_class=HTMLResponse)
async def fetch_articles(request: Request):
    """
    Renders the page for fetching data from Medium.
    """
    articles = list(db['articles'].find({}, {'title': 1, 'link': 1, 'subtitle': 1}))
    return templates.TemplateResponse("select_articles.html", {"request": request, "articles": articles})

@app.post("/delete-selected-articles/")
async def delete_selected_articles(request: Request, article_ids: str = Form(...)):
    """
    Deletes the selected articles from the MongoDB database.
    """
    article_id_list = article_ids.split(',')
    for article_id in article_id_list:
        db['articles'].delete_one({"_id": ObjectId(article_id)})

    return responses.JSONResponse(status_code=200, content={"message": "Articles deleted successfully!"})
