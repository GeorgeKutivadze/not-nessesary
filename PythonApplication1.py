import os
import requests
from bs4 import BeautifulSoup
import re
from io import BytesIO
from zipfile import ZipFile
from tqdm import tqdm
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
from PIL import Image, UnidentifiedImageError

# Base directory for manga storage
base_dir = r"C:\Users\gokag.DESKTOP-Q55650I\OneDrive\Z Mangas"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36",
    "Referer": "",
}

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def clean_title_for_search(title):
    return re.sub(r"[^\w\s]", "", title).strip().replace(" ", "+")

def log_error(manga_dir, error_message):
    error_log_path = os.path.join(manga_dir, "error_log.txt")
    with open(error_log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().isoformat()} - {error_message}\n")
    print(f"Error logged to {error_log_path}")

def save_html_as_txt(manga_dir, html_content):
    html_file_path = os.path.join(manga_dir, "page_content.txt")
    with open(html_file_path, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)
    return html_file_path

def extract_alternative_titles_from_file(manga_dir):
    page_content_path = os.path.join(manga_dir, "page_content.txt")
    
    if not os.path.exists(page_content_path):
        print(f"page_content.txt not found in {manga_dir}")
        return []

    # Read the content of the page_content.txt file
    with open(page_content_path, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Parse the HTML to extract alternative titles
    soup = BeautifulSoup(html_content, 'html.parser')
    alternative_titles_tag = soup.find('td', class_='table-label')
    
    if alternative_titles_tag and 'Alternative' in alternative_titles_tag.text:
        alternative_titles_value = alternative_titles_tag.find_next_sibling('td', class_='table-value')
        
        if alternative_titles_value:
            titles_text = alternative_titles_value.find('h2').text
            alternative_titles = [title.strip() for title in titles_text.split(';')]
            return alternative_titles

    print("No alternative titles found in page_content.txt.")
    return []

def save_url(manga_dir, url):
    url_file_path = os.path.join(manga_dir, "url.txt")
    with open(url_file_path, "w", encoding="utf-8") as url_file:
        url_file.write(url)
    print(f"URL saved to {url_file_path}")

def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")  # Simulate a maximized window
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass Selenium automation detection
    chrome_options.add_argument("--disable-extensions")  # Disable extensions
    chrome_options.add_argument("--disable-gpu")  # Disable GPU for better compatibility
    chrome_options.add_argument("--incognito")  # Use incognito mode to prevent tracking
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # Start Chrome with the necessary options
    chrome_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    # Set a custom user-agent to mimic a real browser
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36"
    })

    return driver

def human_like_interaction(driver):
    time.sleep(random.uniform(2, 5))  # Random delay between 2-5 seconds
    
    # Simulate scrolling
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1, 3))
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(2, 5))

def download_image(img_url, save_dir, save_name, max_retries=3):
    """Download image with retry mechanism."""
    save_path = os.path.join(save_dir, save_name)
    retries = 0

    while retries < max_retries:
        try:
            session = requests.Session()
            # Set default headers, customize as needed
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
            })
            
            with session.get(img_url, stream=True, timeout=10) as img_response:
                img_response.raise_for_status()

                with open(save_path, 'wb') as img_file:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            img_file.write(chunk)
            
            print(f"Image successfully downloaded and saved at: {save_path}")
            return True
        
        except requests.exceptions.RequestException as e:
            retries += 1
            print(f"Attempt {retries} failed: {e}. Retrying...")
            time.sleep(2)
    
    print(f"Failed to download image after {max_retries} attempts.")
    return False

def download_cover_from_mangadex(manga_title, manga_dir):
    """Attempt to download the cover image from MangaDex using Selenium."""
    driver = init_selenium()
    try:
        search_url = f"https://mangadex.org/search?q={manga_title.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(3)  # Allow time for page load

        first_manga_card = driver.find_element(By.CSS_SELECTOR, 'div.grid.gap-2 img.rounded.shadow-md')
        if first_manga_card:
            cover_img_url = first_manga_card.get_attribute('src')
            return download_image(cover_img_url, manga_dir, 'cover.jpg')

        print(f"No cover image found for {manga_title} on MangaDex.")
        return False

    except Exception as e:
        print(f"Error downloading cover from MangaDex: {e}")
        return False

    finally:
        driver.quit()

def search_using_alternative_titles(manga_title, manga_dir, alt_site_url):
    """Search for alternative titles and attempt to download cover image using them."""
    try:
        response = requests.get(alt_site_url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching alternative titles from {alt_site_url}: {e}")
        return False

    alternative_titles = extract_alternative_titles(html_content)

    if alternative_titles:
        print(f"Alternative titles found: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True
    print(f"Failed to download cover image using alternative titles.")
    return False

def extract_alternative_titles(html_content):
    """Extract alternative manga titles from the HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    alternative_titles_tag = soup.find('td', class_='table-label', string='Alternative')

    if alternative_titles_tag:
        alternative_titles_value = alternative_titles_tag.find_next_sibling('td', class_='table-value')
        if alternative_titles_value:
            titles_text = alternative_titles_value.get_text(separator=';')
            alternative_titles = [title.strip() for title in titles_text.split(';') if title.strip()]
            return alternative_titles

    return []

def search_using_alternative_titles(manga_title, manga_dir, alt_site_url):
    # Download and parse the alternative website HTML
    try:
        html_content = requests.get(alt_site_url, headers=headers).text
    except requests.exceptions.RequestException as e:
        print(f"Failed to access {alt_site_url}: {e}")
        return False

    alternative_titles = extract_alternative_titles(html_content)

    if alternative_titles:
        print(f"Alternative titles found: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True

    print("Failed to download cover image using alternative titles.")
    return False

def search_mangadex_and_download_cover_selenium(manga_title, manga_dir, alt_site_url):
    driver = None  # Initialize driver to None for better exception handling
    try:
        driver = init_selenium()  # Initialize Selenium driver
        cleaned_title = clean_title_for_search(manga_title)
        search_url = f"https://mangadex.org/search?q={cleaned_title}"
        print(f"Searching for {manga_title} on MangaDex using Selenium: {search_url}")
        
        driver.get(search_url)
        human_like_interaction(driver)  # Simulate human behavior on the page

        # Try to find the first manga card that has an image
        first_manga_card = driver.find_element(By.CSS_SELECTOR, 'div.grid.gap-2 img.rounded.shadow-md')
        if not first_manga_card:
            print(f"No results found on MangaDex for {manga_title}. Falling back to alternative titles...")
            return search_using_alternative_titles_from_file(manga_title, manga_dir)

        # Get the cover image URL
        cover_img_url = first_manga_card.get_attribute('src')
        print(f"Found cover image via Selenium: {cover_img_url}")

        # Download and save the image using Selenium
        driver.get(cover_img_url)
        time.sleep(2)  # Wait for the image to fully load
        save_path = os.path.join(manga_dir, "cover.jpg")

        # Save the image as a screenshot
        with open(save_path, "wb") as file:
            file.write(driver.find_element(By.TAG_NAME, "img").screenshot_as_png)

        print(f"Image downloaded and saved at: {save_path}")
        return True

    except Exception as e:
        log_error(manga_dir, f"Error searching or downloading cover using Selenium: {e}")
        # Fall back to alternative titles if there was an error
        return search_using_alternative_titles_from_file(manga_title, manga_dir)

    finally:
        if driver:
            driver.quit()  

def search_using_alternative_titles_from_file(manga_title, manga_dir):
    alternative_titles = extract_alternative_titles_from_file(manga_dir)

    if alternative_titles:
        print(f"Alternative titles found in page_content.txt: {alternative_titles}")
        for alt_title in alternative_titles:
            if download_cover_from_mangadex(alt_title, manga_dir):
                print(f"Cover image downloaded using alternative title: {alt_title}")
                return True

    print("Failed to download cover image using alternative titles.")
    return False

def extract_and_download_cover(manga_dir, html_file_path, base_url, manga_title, alt_site_url):
    success = search_mangadex_and_download_cover_selenium(manga_title, manga_dir, alt_site_url)  # Use Selenium-based search
    if success:
        return

    print("Falling back to original method to download cover image.")
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    cover_img_tag = soup.select_one('div.panel-story-info div.story-info-left img.img-loading')
    
    if not cover_img_tag or not cover_img_tag.get('src'):
        log_error(manga_dir, "Cover image tag not found or missing 'src' attribute.")
        return

    cover_img_url = urljoin(base_url, cover_img_tag['src'])
    download_image(cover_img_url, manga_dir, "cover.jpg")







# Switch image server via Selenium
def switch_server(driver, server_number):
    server_buttons = driver.find_elements(By.CLASS_NAME, 'server-image-btn')
    if server_buttons and len(server_buttons) >= server_number:
        server_buttons[server_number - 1].click()
        time.sleep(2)  # Wait for page to load
    else:
        print(f"Failed to switch to server {server_number}")

# Download and convert image to JPG
def download_image_convert(img_url, save_dir, save_name):
    save_path = os.path.join(save_dir, save_name)
    try:
        img_response = requests.get(img_url, headers=headers, stream=True, timeout=10)
        img_response.raise_for_status()  # Ensure the request was successful

        # Check if the response is an image by inspecting the Content-Type header
        content_type = img_response.headers.get('Content-Type')
        if 'image' not in content_type:
            print(f"URL did not return an image: {img_url}, Content-Type: {content_type}")
            return False

        # Try opening the image to check if it's valid
        try:
            img = Image.open(BytesIO(img_response.content))
        except UnidentifiedImageError as e:
            print(f"Failed to identify image at URL: {img_url}, error: {e}")
            return False

        # Convert image to JPG if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(save_path, "JPEG")
        print(f"Image saved as {save_name}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Failed to download/convert image: {img_url}, error: {e}")
        return False

# Validate image content
def validate_image(img_path):
    try:
        img = Image.open(img_path)
        img.verify()  # Verify if image is valid
        return True
    except Exception as e:
        print(f"Image validation failed: {img_path}, error: {e}")
        os.remove(img_path)  # Remove corrupt image
        return False

# Download chapter images and handle retries for server switching
def download_chapter_images(chapter_url, manga_title, chapter_title, manga_dir):
    # Initialize Selenium driver
    driver = init_selenium()
    driver.get(chapter_url)
    
    for server_number in range(1, 3):  # Try both servers
        print(f"Trying server {server_number}...")
        if server_number > 1:
            switch_server(driver, server_number)
        
        # Find images using Selenium (ensure you're only selecting relevant images)
        image_elements = driver.find_elements(By.CSS_SELECTOR, 'div.container-chapter-reader img')
        if not image_elements:
            print(f"No images found on server {server_number}.")
            continue  # Retry with next server if no images found

        chapter_images = []
        for idx, img_elem in enumerate(image_elements, start=1):
            img_url = img_elem.get_attribute('src')
            save_name = f"{idx:03}.jpg"
            save_path = os.path.join(manga_dir, save_name)

            # Download and convert image to JPG
            if download_image_convert(img_url, manga_dir, save_name):
                if validate_image(save_path):
                    chapter_images.append(save_path)

        if chapter_images:
            create_cbz_file(manga_title, chapter_title, manga_dir, chapter_images)
            break

    driver.quit()

# Create CBZ file
def create_cbz_file(manga_title, chapter_title, manga_dir, chapter_images):
    # Fix file name format without extra hyphen
    cbz_name = f"{manga_title} - {chapter_title.replace('-', '').strip()}.cbz"
    cbz_path = os.path.join(manga_dir, cbz_name)
    
    with ZipFile(cbz_path, 'w') as cbz_file:
        for image in chapter_images:
            cbz_file.write(image, os.path.basename(image))
    
    print(f"CBZ file created: {cbz_path}")

    
def delete_images(image_paths):
    for img_path in image_paths:
        if os.path.exists(img_path):
            os.remove(img_path)
    print(f"Deleted {len(image_paths)} images after creating CBZ.")

def download_manga_chapter(manga_url, manga_title, chapter_title, manga_dir):
    os.makedirs(manga_dir, exist_ok=True)
    download_chapter_images(manga_url, manga_title, chapter_title, manga_dir)















def download_manga(url, manga_title=None):
    headers['Referer'] = url
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the manga page. Error: {e}")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    if not manga_title:
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Processing Manga: {manga_title}")
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)
    os.makedirs(manga_dir, exist_ok=True)

    save_url(manga_dir, url)
    html_file_path = save_html_as_txt(manga_dir, html_content)

    # Process and download chapters
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")
        
        # Download and process chapter images with server switching
        download_chapter_images(chapter_url, manga_title, chapter_title, manga_dir)

    update_combined_log()

def download_manga(url, manga_title=None):
    headers['Referer'] = url
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the manga page. Error: {e}")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    if not manga_title:
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Processing Manga: {manga_title}")
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)
    os.makedirs(manga_dir, exist_ok=True)

    save_url(manga_dir, url)
    html_file_path = save_html_as_txt(manga_dir, html_content)

    # Download cover image from both MangaDex and alternative source
    alt_site_url = "https://manganelo.com/manga-hero-x-demon-queen"
    extract_and_download_cover(manga_dir, html_content, url, manga_title, alt_site_url)

    # Process and download chapters
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")
        download_chapter_images(chapter_url, manga_title, chapter_title, manga_dir)

    print(f"Total estimated download size: {total_download_size / (1024 * 1024):.2f} MB")

    update_combined_log()

def update_combined_log():
    combined_log_path = os.path.join(base_dir, "combined_download_log.txt")

    with open(combined_log_path, "w", encoding="utf-8") as combined_log:
        combined_log.write(f"{'Manga Title':<30} {'Total Chapters':<15} {'Last Updated':<25}\n")
        combined_log.write("="*70 + "\n")
        
        for manga_folder in os.listdir(base_dir):
            manga_path = os.path.join(base_dir, manga_folder)
            if os.path.isdir(manga_path):
                log_file = os.path.join(manga_path, "download_log.txt")
                
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as individual_log:
                        chapters = individual_log.readlines()
                        if chapters:
                            last_updated = chapters[-1].strip().split("\t")[-1]
                            combined_log.write(f"{manga_folder:<30} {len(chapters):<15} {last_updated:<25}\n")

def list_manga_folders():
    manga_folders = [folder for folder in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, folder))]
    print("Available Manga Titles:")
    for index, folder in enumerate(manga_folders, 1):
        print(f"{index}. {folder}")
    return manga_folders

def select_and_update_folders():
    manga_folders = list_manga_folders()
    print("Enter 'all' to update all folders.")
    selected_numbers = input("Enter the numbers of the manga folders to update (comma-separated): ").split(',')
    
    if 'all' in selected_numbers:
        selected_numbers = range(1, len(manga_folders) + 1)
    else:
        selected_numbers = [int(num.strip()) for num in selected_numbers]

    for num in selected_numbers:
        if 1 <= num <= len(manga_folders):
            manga_folder = manga_folders[num-1]
            manga_folder_path = os.path.join(base_dir, manga_folder)
            url_file_path = os.path.join(manga_folder_path, "url.txt")

            if os.path.exists(url_file_path):
                with open(url_file_path, "r", encoding="utf-8") as url_file:
                    manga_page_url = url_file.read().strip()
                print(f"Updating folder: {manga_folder}")
                update_manga(manga_page_url, manga_title=manga_folder)
            else:
                print(f"URL file missing for folder '{manga_folder}'. Please enter the URL.")
                new_url = input(f"Enter the URL for '{manga_folder}': ").strip()
                save_url(manga_folder_path, new_url)
                update_manga(new_url, manga_title=manga_folder)
        else:
            print(f"Invalid selection: {num}. Skipping...")

def update_manga(url, manga_title=None):
    headers['Referer'] = url
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html_content = response.text

    if not manga_title:
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Updating Manga: {manga_title}")

    # Sanitize the manga title
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)

    soup = BeautifulSoup(html_content, 'html.parser')
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")

        # Download and process chapter images with server switching
        download_chapter_images(chapter_url, manga_title, chapter_title, manga_dir)

    update_combined_log()


user_input = input("Enter the manga page URL or 'update' to select folders for update: ")

if user_input.lower() == 'update':
    select_and_update_folders()
else:
    download_manga(user_input)

print(f"All selected chapters downloaded and saved in their respective directories.")
print(f"Combined log file updated and saved at {os.path.join(base_dir, 'combined_download_log.txt')}")

input("Press Enter to exit...")