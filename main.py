import os
import json
import difflib
from datetime import datetime, timezone
from typing import Optional, Tuple
import aiohttp
import urllib.parse
from io import BytesIO
from PIL import Image
import asyncio
import re
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service

# =============================
# Configuration and constants
# =============================
VOUCHES_PATH = 'vouches.json'
ARCHIVE_PATH = 'vouch_archive.json'
ITEMS_PATH = 'items.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

# =============================
# Helpers
# =============================




async def fetch_image(url: str) -> Optional[bytes]:
    """Fetch an image from a URL and return its bytes."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' not in content_type:
                        return None
                    data = await response.read()
                    # Verify image size (Discord avatar size limit: 8MB)
                    if len(data) > 8 * 1024 * 1024:
                        return None
                    # Optionally process image with Pillow
                    try:
                        img = Image.open(BytesIO(data))
                        # Convert to PNG or JPEG if needed
                        output = BytesIO()
                        img.save(output, format='PNG')
                        return output.getvalue()
                    except Exception:
                        return data  # Fallback to raw data if processing fails
                return None
        except Exception as e:
            print(f"Error fetching image from {url}: {e}")
            return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # Corrupted JSON or empty file -> safely return empty
        return {}






# Load items database
def load_items_database():
    """Load and validate items database"""
    try:
        items_file = Path('items.json')
        if not items_file.exists():
            logger.warning("items.json not found, creating dummy database")
            # Create a dummy items.json for testing
            dummy_data = {
                "items": [
                    {
                        "name": "Cute Cowboy",
                        "image": "https://example.com/image.webp",
                        "shards": "250,000 Shards",
                        "coins": "3,000,000 Coins",
                        "usd": "$50.00",
                        "stock": 0,
                        "type": "Capes",
                        "category": "Limited"
                    },
                    {
                        "name": "Antler",
                        "image": "https://example.com/antler.webp",
                        "shards": "5,000 Shards",
                        "coins": "60,000 Coins",
                        "usd": "$1.00",
                        "stock": 100,
                        "type": "Artifacts",
                        "category": "Common"
                    }
                ]
            }
            with open('items.json', 'w', encoding='utf-8') as f:
                json.dump(dummy_data, f, indent=2)
            logger.info("Created dummy items.json")
        
        with open('items.json', 'r', encoding='utf-8') as f:
            items_data = json.load(f)
        
        if 'items' not in items_data:
            raise ValueError("Invalid items.json structure: missing 'items' key")
        
        items_lookup = {}
        for item in items_data['items']:
            if 'name' in item:
                # Create multiple lookup keys for robustness
                name_lower = item['name'].lower().strip()
                items_lookup[name_lower] = item
                # Also store without special characters
                name_clean = re.sub(r'[^\w\s]', '', name_lower)
                items_lookup[name_clean] = item
        
        logger.info(f"Loaded {len(items_lookup)} items from database")
        return items_lookup
    except Exception as e:
        logger.error(f"Error loading items database: {e}")
        return {}

items_lookup = load_items_database()

def setup_driver():
    """Setup headless Chrome driver with portable Chrome"""
    import os
    from pathlib import Path
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(5)
    return driver


def parse_currency(value_str):
    """Parse currency string to float with robust handling"""
    if not value_str or value_str == 'N/A' or value_str == '':
        return 0.0
    
    try:
        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[^\d.]', '', str(value_str))
        return float(cleaned) if cleaned else 0.0
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse currency '{value_str}': {e}")
        return 0.0

def find_item_in_database(item_name, items_lookup):
    """Find item in database with fuzzy matching"""
    item_name_lower = item_name.lower().strip()
    
    # Direct match
    if item_name_lower in items_lookup:
        return items_lookup[item_name_lower]
    
    # Clean match (without special characters)
    item_name_clean = re.sub(r'[^\w\s]', '', item_name_lower)
    if item_name_clean in items_lookup:
        return items_lookup[item_name_clean]
    
    # Partial match disabled - too risky for false positives
    # Only do partial matching if the name is at least 80% similar
    for key, value in items_lookup.items():
        if len(item_name_clean) > 4 and len(key) > 4:
            # Check if one is substantially contained in the other (at least 80% overlap)
            shorter = min(len(item_name_clean), len(key))
            longer = max(len(item_name_clean), len(key))
            if shorter / longer >= 0.8:
                if item_name_clean in key or key in item_name_clean:
                    logger.info(f"Fuzzy matched '{item_name}' to '{value.get('name', key)}'")
                    return value
    
    return None

def safe_click(driver, element, max_retries=3):
    """Safely click an element with retries"""
    for attempt in range(max_retries):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", element)
            return True
        except StaleElementReferenceException:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Click attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(0.5)
    return False

def scrape_inventory(ign):
    """Scrape inventory from zeqa.net profile with robust error handling"""
    driver = None
    
    try:
        driver = setup_driver()
        url = f"https://app.zeqa.net/profile?player={ign}"
        
        logger.info(f"Starting inventory scrape for {ign}")
        driver.get(url)
        
        # Wait for page to load completely
        wait = WebDriverWait(driver, 20)
        
        # Wait for body to be present
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        
        # Check if profile exists (look for error messages)
        try:
            error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'not found') or contains(text(), 'does not exist')]")
            if error_elements:
                raise Exception("Player profile not found")
        except:
            pass
        
        # Scroll to cosmetic collection section
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
        time.sleep(2)
        
        # Find all category sections with multiple attempts
        all_categories = []
        for attempt in range(3):
            try:
                all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                if all_categories:
                    break
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} to find categories failed: {e}")
                if attempt == 2:
                    raise
        
        if not all_categories:
            raise Exception("No cosmetic categories found on profile")
        
        logger.info(f"Found {len(all_categories)} total categories")
        
        # Filter to only main cosmetic type categories
        valid_category_names = ["Artifact", "Cape", "Killphrase", "Projectile", "Mount"]
        main_categories = []
        
        for category in all_categories:
            try:
                category_header = category.find_element(By.TAG_NAME, "h6")
                category_name = category_header.text.strip()
                if category_name in valid_category_names:
                    main_categories.append((category, category_name))
                    logger.info(f"Found main category: {category_name}")
            except:
                continue
        
        logger.info(f"Processing {len(main_categories)} main categories")
        
        owned_items = []
        total_usd = 0.0
        total_coins = 0.0
        total_shards = 0.0
        categories_processed = 0
        
        for category_tuple in main_categories:
            try:
                category, category_name = category_tuple
                
                # Re-locate the category in the current page state
                all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                category = None
                for cat in all_categories:
                    try:
                        header = cat.find_element(By.TAG_NAME, "h6")
                        if header.text.strip() == category_name:
                            category = cat
                            break
                    except:
                        continue
                
                if not category:
                    logger.warning(f"Could not relocate category: {category_name}")
                    continue
                
                # Get the count (n/total format)
                try:
                    count_elements = category.find_elements(By.TAG_NAME, "h3")
                    count_text = ""
                    for elem in count_elements:
                        text = elem.text.strip()
                        if text and '/' in text:
                            count_text = text
                            break
                    
                    if not count_text:
                        logger.info(f"No count found for {category_name}, skipping")
                        continue
                except Exception as e:
                    logger.warning(f"Error getting count for {category_name}: {e}")
                    continue
                
                # Parse the count (e.g., "5/295" or "[5/295]" -> owned = 5)
                match = re.match(r'\[?(\d+)/(\d+)\]?', count_text)
                if not match:
                    logger.warning(f"Invalid count format for {category_name}: {count_text}")
                    continue

                owned_count = int(match.group(1))
                total_count = int(match.group(2))

                # Skip if no items owned
                if owned_count == 0:
                    logger.info(f"Skipping {category_name}: 0/{total_count} items")
                    continue

                logger.info(f"Processing {category_name}: {owned_count}/{total_count} items")
                
                # Click on the category to expand it
                dropdown_toggle = category.find_element(By.CSS_SELECTOR, ".black-dropdown-toggle")
                safe_click(driver, dropdown_toggle)
                time.sleep(1.5)
                
                # Find and interact with filter dropdown
                try:
                    # Re-find category after clicking
                    all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                    category = None
                    for cat in all_categories:
                        try:
                            header = cat.find_element(By.TAG_NAME, "h6")
                            if header.text.strip() == category_name:
                                category = cat
                                break
                        except:
                            continue
                    
                    if not category:
                        logger.warning(f"Could not relocate category after expand: {category_name}")
                        continue
                    
                    filter_dropdown = category.find_element(By.CSS_SELECTOR, ".dropdown.zeqa-dropdown select")
                    select = Select(filter_dropdown)
                    
                    # Try different variations of "Show Owned"
                    selected = False
                    for option_text in ["Show Owned", "Owned", "show owned"]:
                        try:
                            select.select_by_visible_text(option_text)
                            selected = True
                            break
                        except:
                            continue
                    
                    if not selected:
                        # Try by value
                        for option in select.options:
                            if 'owned' in option.text.lower():
                                select.select_by_visible_text(option.text)
                                selected = True
                                break
                    
                    if not selected:
                        logger.warning(f"Could not select 'Show Owned' for {category_name}")
                        continue
                    
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error selecting filter for {category_name}: {e}")
                    continue
                
                # Get all cosmetic items with retry logic
                cosmetic_items = []
                for attempt in range(3):
                    try:
                        all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                        category = None
                        for cat in all_categories:
                            try:
                                header = cat.find_element(By.TAG_NAME, "h6")
                                if header.text.strip() == category_name:
                                    category = cat
                                    break
                            except:
                                continue
                        
                        if category:
                            cosmetic_items = category.find_elements(By.CSS_SELECTOR, ".oreuidiv")
                        if cosmetic_items:
                            break
                        time.sleep(1)
                    except:
                        if attempt == 2:
                            logger.error(f"Failed to find items in {category_name}")
                
                logger.info(f"Found {len(cosmetic_items)} items in {category_name}")
                
                for item_element in cosmetic_items:
                    try:
                        # Get item name with multiple selector attempts
                        item_name = None
                        try:
                            item_name_elem = item_element.find_element(By.CSS_SELECTOR, ".oreuitextblock.cosmetics")
                            item_name = item_name_elem.text.strip()
                        except:
                            try:
                                item_name_elem = item_element.find_element(By.CSS_SELECTOR, ".oreuitextblock")
                                item_name = item_name_elem.text.strip()
                            except:
                                logger.warning("Could not extract item name")
                                continue
                        
                        if not item_name:
                            continue
                        
                        # Look up item in database
                        item_data = find_item_in_database(item_name, items_lookup)
                        
                        if item_data:
                            # Parse values
                            usd_value = parse_currency(item_data.get('usd', '0'))
                            coins_value = parse_currency(item_data.get('coins', '0'))
                            shards_value = parse_currency(item_data.get('shards', '0'))
                            
                            total_usd += usd_value
                            total_coins += coins_value
                            total_shards += shards_value
                            
                            owned_items.append({
                                'name': item_name,
                                'category': category_name,
                                'usd': usd_value,
                                'coins': coins_value,
                                'shards': shards_value
                            })
                            
                            logger.info(f"  ✓ {item_name}: ${usd_value:,.2f}")
                        else:
                            logger.warning(f"   {item_name}: NOT FOUND in database")
                            
                    except Exception as e:
                        logger.error(f"Error processing item: {e}")
                        continue
                
                categories_processed += 1
                
                # Collapse the category
                try:
                    all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                    category = None
                    for cat in all_categories:
                        try:
                            header = cat.find_element(By.TAG_NAME, "h6")
                            if header.text.strip() == category_name:
                                category = cat
                                break
                        except:
                            continue
                    
                    if category:
                        dropdown_toggle = category.find_element(By.CSS_SELECTOR, ".black-dropdown-toggle")
                        safe_click(driver, dropdown_toggle)
                        time.sleep(0.8)
                except:
                    pass  # Non-critical if collapse fails
                
            except Exception as e:
                logger.error(f"Error processing category {category_name}: {e}")
                continue
        
        logger.info(f"Scraping complete: {len(owned_items)} items from {categories_processed} categories")
        
        return {
            'success': True,
            'ign': ign,
            'items': owned_items,
            'total_usd': total_usd,
            'total_coins': total_coins,
            'total_shards': total_shards,
            'item_count': len(owned_items),
            'categories_processed': categories_processed
        }
        
    except Exception as e:
        logger.error(f"Fatal error scraping inventory for {ign}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'ign': ign
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

active_evaluations = set()


from fastapi import FastAPI
import uvicorn, os

app = FastAPI()

@app.get("/inventory/{ign}")
def get_inventory(ign: str):
    return scrape_inventory(ign)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("render_scraper:app", host="0.0.0.0", port=port)

