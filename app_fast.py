import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, Request, responses
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId

from src.logger import logger


load_dotenv(find_dotenv())

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Connect to the MongoDB database
client = MongoClient(os.getenv('MONGO_URI'))
db = client['medium_data']

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    logger.info("Home Page Requested\n\n")
    """
    Renders the home page of the application.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/fetch-data/", response_class=HTMLResponse)
async def fetch_data(request: Request, data_input: str = Form(...)):
    """
    Fetches the data from Medium and stores the metadata in the MongoDB database.
    """
    url = data_input
    logger.info(f"Fetching data from: {url}\n\n")
    articles = scrape_medium_articles(url)

    # Print the scraped articles for debugging
    logger.info(f"Scraped Articles: {articles}\n\n")

    # Save articles to MongoDB
    if articles:
        result = db['articles'].insert_many(articles)
        logger.info(f"Inserted Article IDs: {result.inserted_ids}\n\n")
    else:
        logger.info("No articles to insert.\n\n")

    return templates.TemplateResponse("select_articles.html", {"request": request, "articles": articles})

def scrape_medium_articles(author_url):
    """
    Scrapes articles from the given Medium author's page.
    """
    response = requests.get(author_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    articles = []
    logger.info('Scrapping title, link, and subtitle\n\n')
    # logger.info(f"Beutified data: {soup}\n\n")
    for item in soup.find_all('div', class_='ab cm'):
        title_tag = item.find('h2')
        title = title_tag.text if title_tag else "No title"

        link_tag = item.find('a', href=True)
        link = link_tag['href'].split('?')[0] if link_tag else "No link"
        if link.startswith('/'):
            link = 'https://medium.com' + link

        subtitle_tag = item.find('h3')
        subtitle = subtitle_tag.text if subtitle_tag else "No subtitle"

        logger.info("Scrapping article content from link\n\n")
        # Scrape full content of the article
        article_content = scrape_article_content(link)

        article = {
            'title': title,
            'link': link,
            'subtitle': subtitle,
            'content': article_content
        }
        articles.append(article)

    return articles

def scrape_article_content(article_url):
    """
    Scrapes the full content of an individual Medium article.
    """
    response = requests.get(article_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    logger.info(f'Beutified article data: {soup}\n\n')

    content = ""
    for para in soup.find_all('p'):
        # logger.info(f"Scrapped paragraph: {para}\n\n")
        content += para.text + "\n"

    logger.info(f'Scrapped article content: {content}\n\n')
    return content

@app.get("/get-fetch-data/", response_class=HTMLResponse)
async def fetch_articles(request: Request):
    """
    Renders the page for fetching data from Medium.
    """
    articles = list(db['articles'].find({}, {'title': 1, 'link': 1, 'subtitle': 1, 'content': 1}))
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

# Run the application with: uvicorn app_fast:app --reload
