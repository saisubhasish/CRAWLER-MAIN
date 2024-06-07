import argparse
from src.logger import logger
from src.utils.common import *
from src.data_preprocessing.data_cleaning import text_processing
from src.web_crawler.chromedriver_loader import ChromeLoader
from src.web_crawler.beutifulsoup_transformer import Bs4Transformer
from src.web_crawler.trafilatura_crawler import trafilatura_scraper


def scrape_website(urls: list, title: list, date: list = None):
    try:
        # Load
        # remove 10 from here its for testing purpose
        chrome_loader = ChromeLoader(urls)
        documents = chrome_loader.load()

        logger.info(f"Documents loaded: {len(documents)}")
        # logger.info(f"Document: {documents[0]}")

        # Transform using soup
        bs_transformer = Bs4Transformer()
        docs_transformed = bs_transformer.transform_documents(
            documents, tags_to_extract=(args.tags_to_extract).split(','), class_to_extract=args.class_to_extract, remove_lines=True, unwanted_tags=["script", "style"])

        metadata = [{'title': title if title else None, 'source': doc.metadata['source'],
                    'page_content': text_processing(doc.page_content)} for doc, title in zip(docs_transformed, title)]  # remove 10 from here its for testing purpose

        logger.info(f"Metadata created: {len(metadata)}")

        insert_data_to_mongo(args.db_name, metadata, "articles_raw_data")

        # cleaned_data = []
        # # meta_data_to_json(metadata, args.metadata_name)
        # with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        #     # metadata['cleaned_data'] = executor.submit(data_cleaning_with_llm, data['page_content'])
        #     futures = [executor.submit(data_cleaning_with_llm, data)
        #                for data in metadata]
        #     concurrent.futures.wait(futures)
        #     for future in futures:
        #         cleaned_data.append(future.result())

        #     # for data in metadata:
        #     #     executor.submit(insert_raw_data_to_mongo, args.metadata_name, data)

        # insert_data_to_mongo(args.db_name, cleaned_data, "cleaned_data")

    except Exception as e:
        logger.error(f"Error: {e}")


def fast_scraper(json_data: list):
    try:
        # data_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(trafilatura_scraper, data['template_url'], data['template_topic'], args.db_name)
                       for data in json_data]
            concurrent.futures.wait(futures)
            for future in futures:
                # data_list.append(future.result())
                future.result()

        # insert_data_to_mongo(args.db_name, data_list)
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_name", type=str, default="test_metadata")
    parser.add_argument("--urls", type=str, default="https://google.com/")
    parser.add_argument("--tags_to_extract", type=str, default="div, p, li, a")
    parser.add_argument("--class_to_extract", type=str, default="article-body")
    parser.add_argument("--path", type=str, default=None)
    args = parser.parse_args()

    if args.path and args.db_name:
        with open(args.path, "r") as f:
            json_data = json.load(f)
            logger.info(f"The length of json data is: {len(json_data)}")

        # fast_scraper(urls=[url['article_url'] for url in json_data][:10], title=[
        #     url['article_title'] for url in json_data][10], date=[url['article_date'] for url in json_data][:10])
        fast_scraper(json_data)
        # scrape_website(urls=[url['article_url'] for url in json_data], title=[
        #                url['article_title'] for url in json_data], date=[url['article_date'] for url in json_data])

    else:
        # Load urls from command line
        logger.info(f"Scraping urls: {args.urls}")
        scrape_website(urls=[url.strip() for url in args.urls.split(',')], title=[
            url.split("/")[-2] for url in args.urls.split(',')])
